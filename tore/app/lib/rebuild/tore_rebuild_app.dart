import 'package:flutter/material.dart';

import 'config/app_environment.dart';
import 'models/event_context.dart';
import 'models/backend_models.dart';
import 'models/qr_resolve.dart';
import 'models/rebuild_types.dart';
import 'models/snapshot.dart';
import 'routing/adapter_routes.dart';
import 'routing/app_routes.dart';
import 'routing/deep_link_router.dart';
import 'routing/qr_router.dart';
import 'routing/route_guards.dart';
import 'services/api_client.dart';
import 'services/cache_store.dart';
import 'services/contract_api.dart';
import 'services/client_log.dart';
import 'services/idempotency_store.dart';
import 'services/network_state_resolver.dart';
import 'services/remote_config.dart';
import 'ui/module_catalog.dart';
import 'ui/screens/bar/bar_screens.dart';
import 'ui/screens/dev/diagnostics_screen.dart';
import 'ui/screens/help/runbook_screens.dart';
import 'ui/screens/orga/orga_exports_screen.dart';
import 'ui/screens/orga/orga_screens.dart';
import 'ui/screens/showcase/showcase_screens.dart';
import 'ui/screens/system/update_required_screen.dart';
import 'ui/screens/user/user_screens.dart';
import 'ui/theme/tore_theme.dart';
import 'ui/widgets/primitives.dart';

class ToreRebuildApp extends StatefulWidget {
  const ToreRebuildApp({super.key});

  @override
  State<ToreRebuildApp> createState() => _ToreRebuildAppState();
}

class _ToreRebuildAppState extends State<ToreRebuildApp> {
  final _navigatorKey = GlobalKey<NavigatorState>();
  final _api = ApiClient();
  late final ContractApi _contractApi = RebuildContractApi(_api);
  final _cache = CacheStore();
  final _guards = RouteGuards();
  final _router = QrRouter();
  final _deepLinkRouter = DeepLinkRouter();
  final _networkStateResolver = NetworkStateResolver();
  late final IdempotencyStore _writerStore =
      IdempotencyStore(persistence: SharedPrefsIdempotencyPersistence());
  late final IdempotentWriter _writer = IdempotentWriter(store: _writerStore);
  late final List<ModuleDefinition> _defs = buildModuleDefinitions();
  late final AppEnvironment _environment = appEnvironmentFromDefine();
  late final BuildInfo _buildInfo = BuildInfo.fromEnvironment();
  late final RemoteConfigService _remoteConfigService = RemoteConfigService(
      apiClient: _api, cacheStore: _cache, environment: _environment);
  static const String _startupUrl =
      String.fromEnvironment('TORE_STARTUP_URL', defaultValue: '');

  final ToreMode _mode = ToreMode.user;
  UserSnapshot? _userSnapshot;
  EventContext? _eventContext;
  ConnectivityState _network = ConnectivityState.online;
  DateTime _networkTransitionAt = DateTime.now();
  bool _loading = true;
  bool _consented = false;
  int _selectedUserTab = 0;
  _QuickAction? _activeHomeAction;
  List<BarDto> _bars = const [];
  List<EventDto> _barEvents = const [];
  WalletDto? _wallet;
  List<TickerItemDto> _ticker = const [];
  List<PolymarketDto> _polyGlobal = const [];
  List<PolymarketDto> _polyEvent = const [];
  EntryStatsDto? _entryStats;
  List<OrderDto> _orders = const [];
  List<ZoneDto> _zones = const [];
  Map<String, dynamic>? _orgaQrPack;
  RemoteConfigPayload? _remoteConfig;
  MobileBootstrapDto _mobileBootstrap = MobileBootstrapDto.fallback;

  @override
  void initState() {
    super.initState();
    ClientLog.instance.hydrate();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    if (mounted) setState(() => _loading = true);
    final cachedMe = await _cache.loadCachedUser();
    final cachedEvent = await _cache.loadCachedEvent(_mobileBootstrap.eventKey);
    _userSnapshot = cachedMe;
    _eventContext = cachedEvent;
    _remoteConfig = await _remoteConfigService.load();

    try {
      if (_networkStateResolver.canReadRemote(_network)) {
        _mobileBootstrap = await _api.fetchMobileBootstrap();
        _eventContext =
            await _cache.loadCachedEvent(_mobileBootstrap.eventKey) ??
                _eventContext;
        _userSnapshot = await _api.fetchMeSnapshot();
        _eventContext =
            await _api.fetchEventContext(_mobileBootstrap.eventKey, _defs);
        if (_userSnapshot != null) await _cache.saveUser(_userSnapshot!);
        if (_eventContext != null) await _cache.saveEvent(_eventContext!);
        await _loadDomainData();
      }
    } catch (_) {
      await ClientLog.instance
          .log('boot.hydration_fallback', {'reason': 'remote_unavailable'});
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        if (_startupUrl.trim().isNotEmpty) {
          WidgetsBinding.instance
              .addPostFrameCallback((_) => _openDeepLink(_startupUrl));
        }
      }
    }
  }

  Future<void> _loadDomainData() async {
    final barId = _mobileBootstrap.barId ?? '1';
    final eventApiId = _mobileBootstrap.eventApiId;
    _bars = await _safeLoad(
        () => _api.fetchBars(network: _network), const <BarDto>[]);
    _barEvents = await _safeLoad(
        () => _api.fetchBarEvents(barId, network: _network),
        const <EventDto>[]);
    if (!_useShowcaseFixtures) {
      _wallet = await _safeLoad<WalletDto?>(
          () => _api.fetchWallet(eventId: eventApiId, network: _network), null);
    }
    _ticker = await _safeLoad(
        () async =>
            (await _api.fetchTicker(eventApiId, network: _network)).items,
        const <TickerItemDto>[]);
    _polyGlobal = await _safeLoad(
        () => _api.fetchPolymarketGlobal(network: _network),
        const <PolymarketDto>[]);
    if (!_useShowcaseFixtures) {
      _polyEvent = await _safeLoad(
          () => _api.fetchPolymarketEvent(eventApiId, network: _network),
          const <PolymarketDto>[]);
      _entryStats = await _safeLoad(
          () => _api.fetchEntryStats(eventApiId, network: _network),
          const EntryStatsDto(approvedCount: 0, deniedCount: 0));
    }
    _orders = await _safeLoad(
        () async =>
            (await _api.fetchOrdersLive(eventApiId, network: _network)).items,
        const <OrderDto>[]);
    if (!_useShowcaseFixtures) {
      _zones = await _safeLoad(
          () => _api.fetchZones(barId, network: _network), const <ZoneDto>[]);
      _orgaQrPack = await _safeLoad<Map<String, dynamic>?>(
          () => _api.fetchOrgaQrPack(eventApiId, network: _network), null);
    }
    _applyShowcaseDefaults();
  }

  void _applyShowcaseDefaults() {
    _wallet ??= const WalletDto(balance: 129.20, timeline: [
      WalletTxDto(id: 'demo_wallet_1', type: 'Recharge cashless', delta: 50),
      WalletTxDto(id: 'demo_wallet_2', type: 'Commande bar', delta: -12.5),
      WalletTxDto(id: 'demo_wallet_3', type: 'Bonus event', delta: 5),
    ]);
    if (_ticker.isEmpty) {
      _ticker = const [
        TickerItemDto(
            id: 'demo_ticker_1', message: '22:00 - Battle DJ ouverte'),
        TickerItemDto(
            id: 'demo_ticker_2', message: '22:30 - Happy hour au bar B'),
        TickerItemDto(
            id: 'demo_ticker_3', message: '23:00 - Hunt campus: indice 2'),
      ];
    }
    if (_polyGlobal.isEmpty) {
      _polyGlobal = const [
        PolymarketDto(
            id: 'demo_global_1', title: 'La soirée passe 500 check-ins'),
        PolymarketDto(id: 'demo_global_2', title: 'Le bar B finit premier'),
      ];
    }
    if (_polyEvent.isEmpty) {
      _polyEvent = const [
        PolymarketDto(id: 'demo_event_1', title: 'Le prochain son sera techno'),
        PolymarketDto(id: 'demo_event_2', title: 'File entrée sous 5 minutes'),
      ];
    }
    if (_entryStats == null ||
        (_entryStats!.approvedCount == 0 && _entryStats!.deniedCount == 0)) {
      _entryStats = const EntryStatsDto(approvedCount: 244, deniedCount: 17);
    }
    if (_orders.isEmpty) {
      _orders = const [
        OrderDto(id: '501', status: 'NEW'),
        OrderDto(id: '502', status: 'IN_PROGRESS'),
        OrderDto(id: '503', status: 'READY'),
      ];
    }
    if (_zones.isEmpty) {
      _zones = const [
        ZoneDto(id: 'vip', name: 'VIP', enabled: true),
        ZoneDto(id: 'staff', name: 'Staff', enabled: true),
        ZoneDto(id: 'terrace', name: 'Terrasse', enabled: true),
      ];
    }
    _orgaQrPack ??= {
      'links': {
        'Join QR (tore://)': 'tore://event/${_mobileBootstrap.eventApiId}',
        'Entry Staff QR (tore://)':
            'tore://qr/entry:${_mobileBootstrap.eventApiId}',
        'Menu QR (tore://)': 'tore://menu/event/${_mobileBootstrap.eventApiId}',
      }
    };
  }

  Future<T> _safeLoad<T>(Future<T> Function() loader, T fallback) async {
    try {
      return await loader();
    } catch (_) {
      return fallback;
    }
  }

  ModuleState _effectiveState(String id) {
    final fromMe = _userSnapshot?.globalModules[id];
    final base = _eventContext?.moduleStates[id] ?? fromMe ?? ModuleState.off;
    final event = _eventContext?.eventState ?? EventState.draft;
    if (base == ModuleState.off) {
      return ModuleState.off;
    }
    if (event == EventState.paused && base == ModuleState.on) {
      return ModuleState.frozen;
    }
    if (event == EventState.readOnly || event == EventState.ended) {
      return ModuleState.readOnly;
    }
    return base;
  }

  bool get _writesDisabledByRemote =>
      _remoteConfig?.disableWritesGlobal == true;

  bool get _belowMinSupportedVersion {
    final minVersion = _remoteConfig?.minSupportedVersion;
    if (minVersion != null && minVersion.isNotEmpty) {
      return isBelowMinVersion(_buildInfo.semver, minVersion);
    }
    final minBuild = _remoteConfig?.minSupportedBuild;
    return minBuild != null && _buildInfo.buildNumber < minBuild;
  }

  bool get _mustShowUpdateRequired =>
      _belowMinSupportedVersion ||
      (_writesDisabledByRemote &&
          (_mode == ToreMode.orga || _belowMinSupportedVersion));

  String get _updateRequiredMessage {
    if (_belowMinSupportedVersion) {
      return 'Please update app to continue. Minimum required: ${_remoteConfig?.minSupportedVersion ?? _remoteConfig?.minSupportedBuild ?? 'latest'}.';
    }
    return _remoteConfig?.disableWritesMessage ??
        'Writes are temporarily frozen.';
  }

  bool get _diagnosticsAllowed =>
      _remoteConfig?.diagnosticsEnabled ??
      (_environment != AppEnvironment.prod);

  bool get _useShowcaseFixtures => _environment != AppEnvironment.prod;

  bool get _isConnectedAccount =>
      _userSnapshot != null && !_userSnapshot!.roles.contains('GUEST');

  Color get _environmentColor => ToreTheme.envBadgeColor(_environment);

  bool _writeAllowed(String moduleId) =>
      !_writesDisabledByRemote &&
      _networkStateResolver.canWrite(_network) &&
      _effectiveState(moduleId) == ModuleState.on;

  Future<void> _resolveQrPayload(String payload) async {
    try {
      final resolved = await _contractApi.resolveQr(payload);
      final route = _router.targetFor(resolved);
      if (!mounted) return;
      if (resolved.isError || route == AppRoutes.blocked) {
        final err = resolveUiCopy(resolved.reason ?? 'qr_unknown');
        Navigator.pushNamed(context, AppRoutes.blocked, arguments: {
          'title': err.title,
          'message': err.message,
          'cta': err.ctaLabel
        });
        return;
      }
      Navigator.pushNamed(context, route);
    } catch (_) {
      if (!mounted) return;
      final err = resolveUiCopy('backend_down');
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {
        'title': err.title,
        'message': err.message,
        'cta': err.ctaLabel
      });
    }
  }

  Future<void> _openDeepLink(String url) async {
    final parsed = _deepLinkRouter.parse(url);
    if (parsed == null) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {
        'title': 'Lien invalide',
        'message': "Le lien n'est pas supporté par cette version de l'app."
      });
      return;
    }

    if (parsed.isQr) {
      await _resolveQrPayload(parsed.qrPayload!);
      return;
    }

    final route = parsed.route;
    if (!_guards.routeAllowedForMode(route, _mode)) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {
        'title': 'Mauvais mode',
        'message': "Ce lien n'est pas autorisé pour le mode actif."
      });
      return;
    }

    final moduleId = _moduleForRoute(route);
    if (moduleId != null &&
        !_guards.deepLinkAllowed(_effectiveState(moduleId))) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {
        'title': 'Module indisponible',
        'message': 'Le module ciblé est OFF ou temporairement désactivé.'
      });
      return;
    }

    if (!mounted) return;
    Navigator.pushNamed(context, route);
  }

  Future<void> _sensitiveWrite(String moduleId, String action) async {
    if (!_networkStateResolver.canWrite(_network)) {
      ClientLog.instance.log('write.blocked', {
        'reason_code': 'offline_write_blocked',
        'network_state': _network.name,
        'event_state': _eventContext?.eventState.name ?? 'none',
        'module_state': _effectiveState(moduleId).name
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
              'Action impossible hors ligne. Revenez en ligne pour confirmer.')));
      return;
    }
    final reason =
        await ConfirmDialogWithReason.show(context, title: 'Confirm $action');
    if (reason == null) return;
    await _writer.write(
      endpoint: '/v1/$moduleId/write',
      intent: '$moduleId:$action:${_eventContext?.eventId}',
      body: {
        'action': action,
        'reason_code': reason.code,
        'reason_text': reason.text
      },
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Action sent')));
  }

  List<Widget> _moduleCards(ToreMode mode) {
    final visibleModuleIds = _visibleModuleIdsForMode(mode);
    final defs = _defs
        .where((d) => d.mode == mode)
        .where((d) => !_hiddenShellModuleIds.contains(d.id))
        .where((d) => _effectiveState(d.id) != ModuleState.off)
        .where(
            (d) => visibleModuleIds == null || visibleModuleIds.contains(d.id))
        .toList();
    return [
      for (final d in defs)
        ModuleCard(
            def: d,
            state: _effectiveState(d.id),
            onOpen: () => _openModule(d.id))
    ];
  }

  static const Set<String> _hiddenShellModuleIds = {
    'user_splash',
    'user_consent',
    'user_home',
    'user_login_profile',
    'user_qr_scanner',
  };

  Set<String>? _visibleModuleIdsForMode(ToreMode mode) {
    if (_environment != AppEnvironment.prod) return null;
    if (mode != ToreMode.user) return null;
    return const {
      'user_home',
      'user_event_hub',
      'user_join',
      'user_menu',
      'user_wallet',
      'user_ticker',
      'user_polymarket_global',
      'user_login_profile',
      'user_qr_scanner',
    };
  }

  void _openModule(String moduleId) {
    final route = _mapModuleToRoute(moduleId);
    if (route == null) return;
    if (!_guards.routeAllowedForMode(route, _mode)) {
      Navigator.pushNamed(context, AppRoutes.blocked,
          arguments: 'Wrong mode for this route');
      return;
    }
    Navigator.pushNamed(context, route);
  }

  String? _mapModuleToRoute(String moduleId) {
    const map = {
      'user_home': AppRoutes.home,
      'user_qr_scanner': AppRoutes.scanner,
      'user_bars': AppRoutes.bars,
      'user_events': AppRoutes.events,
      'user_join': AppRoutes.join,
      'user_event_hub': AppRoutes.eventHub,
      'user_menu': AppRoutes.menu,
      'user_orders_lifecycle': AppRoutes.orders,
      'user_wallet': AppRoutes.wallet,
      'user_ticker': AppRoutes.ticker,
      'user_polymarket_global': AppRoutes.polymarketGlobal,
      'user_polymarket_event': AppRoutes.polymarketEvent,
      'user_ranking': AppRoutes.ranking,
      'user_battles': AppRoutes.battles,
      'user_hunts': AppRoutes.hunts,
      'user_wifi': AppRoutes.wifi,
      'user_safe_kit': AppRoutes.safeKit,
      'user_forum': AppRoutes.forum,
      'user_calendar': AppRoutes.calendar,
      'user_glossary': AppRoutes.glossary,
      'user_login_profile': AppRoutes.profile,
      'orga_event_control_hub': AppRoutes.orgaHub,
      'orga_entry_mode': AppRoutes.orgaEntry,
      'orga_menu_admin': AppRoutes.orgaMenu,
      'orga_polymarket_admin': AppRoutes.orgaMarket,
      'orga_urgency_actions': AppRoutes.orgaUrgency,
      'orga_music_admin': AppRoutes.orgaMusic,
      'orga_battle_admin': AppRoutes.orgaBattle,
      'orga_hunt_admin': AppRoutes.orgaHunt,
      'orga_forum_moderation': AppRoutes.orgaForum,
      'orga_finance_admin': AppRoutes.orgaExports,
      'bar_dashboard': AppRoutes.barDashboard,
      'bar_orders_live': AppRoutes.barOrders,
      'bar_full_menu_admin': AppRoutes.barMenu,
      'bar_zones_qr': AppRoutes.barZones,
      'bar_analytics': AppRoutes.barAnalytics,
    };
    return map[moduleId];
  }

  String? _moduleForRoute(String route) {
    const map = {
      AppRoutes.home: 'user_home',
      AppRoutes.scanner: 'user_qr_scanner',
      AppRoutes.bars: 'user_bars',
      AppRoutes.events: 'user_events',
      AppRoutes.join: 'user_join',
      AppRoutes.eventHub: 'user_event_hub',
      AppRoutes.menu: 'user_menu',
      AppRoutes.orders: 'user_orders_lifecycle',
      AppRoutes.wallet: 'user_wallet',
      AppRoutes.ticker: 'user_ticker',
      AppRoutes.polymarketGlobal: 'user_polymarket_global',
      AppRoutes.polymarketEvent: 'user_polymarket_event',
      AppRoutes.ranking: 'user_ranking',
      AppRoutes.battles: 'user_battles',
      AppRoutes.hunts: 'user_hunts',
      AppRoutes.wifi: 'user_wifi',
      AppRoutes.safeKit: 'user_safe_kit',
      AppRoutes.forum: 'user_forum',
      AppRoutes.calendar: 'user_calendar',
      AppRoutes.glossary: 'user_glossary',
      AppRoutes.profile: 'user_login_profile',
      AppRoutes.orgaHub: 'orga_event_control_hub',
      AppRoutes.orgaEntry: 'orga_entry_mode',
      AppRoutes.orgaMenu: 'orga_menu_admin',
      AppRoutes.orgaMarket: 'orga_polymarket_admin',
      AppRoutes.orgaUrgency: 'orga_urgency_actions',
      AppRoutes.orgaMusic: 'orga_music_admin',
      AppRoutes.orgaBattle: 'orga_battle_admin',
      AppRoutes.orgaHunt: 'orga_hunt_admin',
      AppRoutes.orgaForum: 'orga_forum_moderation',
      AppRoutes.orgaExports: 'orga_finance_admin',
      AppRoutes.barDashboard: 'bar_dashboard',
      AppRoutes.barOrders: 'bar_orders_live',
      AppRoutes.barMenu: 'bar_full_menu_admin',
      AppRoutes.barZones: 'bar_zones_qr',
      AppRoutes.barAnalytics: 'bar_analytics',
    };
    return map[route];
  }

  void _openDiagnostics() {
    if (!_diagnosticsAllowed) return;
    Navigator.pushNamed(context, AppRoutes.devDiagnostics);
  }

  Widget _showcaseUserFeature({
    required String title,
    required String metric,
    required String label,
    required List<ShowcaseItem> items,
    List<ShowcaseAction> actions = const [],
  }) =>
      ShowcaseFeatureScreen(
        title: title,
        badges: const ['USER', 'SHOWCASE'],
        heroMetric: metric,
        heroLabel: label,
        items: items,
        actions: actions,
        network: _network,
      );

  Widget _showcaseOrgaFeature({
    required String title,
    required String metric,
    required String label,
    required List<ShowcaseItem> items,
    List<ShowcaseAction> actions = const [],
  }) =>
      ShowcaseFeatureScreen(
        title: title,
        badges: const ['ORGA', 'SHOWCASE'],
        heroMetric: metric,
        heroLabel: label,
        items: items,
        actions: actions,
        network: _network,
      );

  Widget _shellBody(BuildContext context) {
    final currentEventState =
        _useShowcaseFixtures ? EventState.live : _eventContext?.eventState;
    final cards = switch (_mode) {
      ToreMode.user => _userTabCards(context),
      ToreMode.orga => _modeCards(
          title: 'Command Center',
          subtitle:
              'Pilotage orga live pour ${_mobileBootstrap.eventName ?? _mobileBootstrap.eventKey}',
          mode: ToreMode.orga,
          metric: '${_entryStats?.approvedCount ?? 0}',
          metricLabel: 'entrées validées'),
      ToreMode.bar => _modeCards(
          title: 'Bar Ops',
          subtitle: 'Commandes, zones et analytics du bar actif',
          mode: ToreMode.bar,
          metric: '${_orders.length}',
          metricLabel: 'commandes live'),
    };
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF120609), ToreTokens.black],
        ),
      ),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 108),
        children: [
          NetworkBanner(state: _network),
          _HeroStatusCard(
            mode: _mode,
            eventName: _mobileBootstrap.eventName ?? _mobileBootstrap.eventKey,
            barName: _mobileBootstrap.barName ?? 'Bar actif',
            eventState: currentEventState ?? EventState.draft,
            syncedAt: _eventContext?.syncedAt,
          ),
          const SizedBox(height: ToreTokens.s16),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            child: Column(
              key: ValueKey(
                  '${_mode.name}-$_selectedUserTab-${_activeHomeAction?.route ?? ''}'),
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: cards,
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _userTabCards(BuildContext context) {
    switch (_selectedUserTab) {
      case 1:
        return [
          _SectionHeader(
              title: 'Ticker live',
              actionLabel: 'Filtres',
              onTap: () => ToreFeedback.success(
                  context, 'Filtres ticker: annonces, commandes, bets.')),
          _TickerPreview(items: _ticker),
        ];
      case 2:
        return [
          _ScannerTabCard(
              onOpen: () => Navigator.pushNamed(context, AppRoutes.scanner)),
        ];
      case 3:
        return [
          _MarketsTab(
              global: _polyGlobal,
              event: _polyEvent,
              onGlobal: () =>
                  Navigator.pushNamed(context, AppRoutes.polymarketGlobal),
              onEvent: () =>
                  Navigator.pushNamed(context, AppRoutes.polymarketEvent)),
        ];
      case 4:
        return [
          if (_isConnectedAccount)
            _ForumCommunitySurface(
              onOpenForum: () => Navigator.pushNamed(context, AppRoutes.forum),
              onSubmitRequest: () => ToreFeedback.success(
                  context, 'Demande de forum envoyée à la modération TORÈ.'),
            )
          else
            const _ConnectedOnlyForumPrompt(),
        ];
      default:
        return [
          _QuickActions(
            onOpen: (action) {
              if (action.tabIndex != null) {
                setState(() {
                  _activeHomeAction = null;
                  _selectedUserTab = action.tabIndex!;
                });
                return;
              }
              setState(() => _activeHomeAction = action);
            },
          ),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            transitionBuilder: (child, animation) {
              final offset = Tween<Offset>(
                begin: const Offset(0, -0.06),
                end: Offset.zero,
              ).animate(CurvedAnimation(
                  parent: animation, curve: Curves.easeOutCubic));
              return FadeTransition(
                opacity: animation,
                child: SlideTransition(position: offset, child: child),
              );
            },
            child: _activeHomeAction == null
                ? const SizedBox.shrink()
                : Padding(
                    key: ValueKey(_activeHomeAction!.route),
                    padding: const EdgeInsets.only(top: ToreTokens.s12),
                    child: _HomeActionPanel(
                      action: _activeHomeAction!,
                      onOpenFull: () => Navigator.pushNamed(
                          context, _activeHomeAction!.route),
                      onClose: () => setState(() => _activeHomeAction = null),
                    ),
                  ),
          ),
          const SizedBox(height: ToreTokens.s16),
          _SectionHeader(
              title: 'Live maintenant',
              actionLabel: 'Events',
              onTap: () {
                Navigator.pushNamed(context, AppRoutes.events);
              }),
          _HomeEventCard(
            title: _mobileBootstrap.eventName ?? 'Afond Night',
            bar: _mobileBootstrap.barName ?? 'TORÈ Test Bar',
            meta: 'Live maintenant · entrée gratuite',
            onTap: () => Navigator.pushNamed(context, AppRoutes.eventHub),
          ),
          const SizedBox(height: ToreTokens.s16),
          const _SectionHeader(title: 'Bars partenaires'),
          _BarsPreview(
            onBarTap: () => Navigator.pushNamed(context, AppRoutes.bars),
          ),
        ];
    }
  }

  List<Widget> _modeCards({
    required String title,
    required String subtitle,
    required ToreMode mode,
    required String metric,
    required String metricLabel,
  }) {
    return [
      Card(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Row(children: [
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: ToreTokens.s4),
                    Text(subtitle),
                  ]),
            ),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(metric, style: ToreTypography.monoNumber(context, size: 30)),
              Text(metricLabel),
            ]),
          ]),
        ),
      ),
      const SizedBox(height: ToreTokens.s12),
      ..._moduleCards(mode),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: _navigatorKey,
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.build(),
      routes: {
        AppRoutes.boot: (_) => _loading
            ? BootSplashScreen(
                network: _network,
                environmentLabel: appEnvironmentLabel(_environment),
                environmentColor: _environmentColor,
                onLongPressDiagnostics:
                    _diagnosticsAllowed ? _openDiagnostics : null)
            : ConsentCharterScreen(onAccept: () {
                if (!mounted) return;
                setState(() {
                  _consented = true;
                  _selectedUserTab = 0;
                });
              }),
        AppRoutes.home: (_) => _mustShowUpdateRequired
            ? UpdateRequiredScreen(
                mode: _mode,
                message: _updateRequiredMessage,
                blockedByVersion: _belowMinSupportedVersion)
            : HomeHubScreen(network: _network, cards: [
                HeaderCard(
                    userSnapshot: _userSnapshot, eventContext: _eventContext),
                ..._moduleCards(ToreMode.user)
              ]),
        AppRoutes.scanner: (_) =>
            QrScannerScreen(onResolve: _resolveQrPayload, network: _network),
        AppRoutes.bars: (_) => BarsScreen(
            network: _network,
            children: _bars
                .map((b) => ListTile(
                    title: Text(b.name), subtitle: Text(b.city ?? b.id)))
                .toList()),
        AppRoutes.events: (_) => BarEventsScreen(
            network: _network,
            children: _barEvents
                .map((e) => ListTile(
                    title: Text(e.title), subtitle: Text(e.state ?? 'LIVE')))
                .toList()),
        AppRoutes.join: (_) => JoinEventScreen(
            writeAllowed: _writeAllowed('user_join'),
            onJoin: () => _sensitiveWrite('user_join', 'join_event'),
            network: _network),
        AppRoutes.eventHub: (_) => EventHubScreen(
            network: _network,
            modules: _moduleCards(ToreMode.user),
            eventState: _eventContext?.eventState ?? EventState.draft,
            writeAllowedReason: _writeAllowed('user_event_hub')
                ? 'Writes enabled'
                : 'Writes blocked by network or event state'),
        ...buildAdapterRoutes(
            network: _network,
            eventId: int.tryParse(_mobileBootstrap.eventApiId) ?? 42,
            orderId: _orders.isEmpty ? 1 : int.tryParse(_orders.first.id) ?? 1,
            eventState: _eventContext?.eventState ?? EventState.draft),
        AppRoutes.wallet: (_) => WalletScreen(
            network: _network,
            rows: (_wallet?.timeline ?? const [])
                .map((tx) => ListTile(
                    title: Text(tx.type),
                    trailing: Text(tx.delta.toStringAsFixed(2),
                        style: const TextStyle(fontFamily: 'monospace'))))
                .toList()),
        AppRoutes.ticker: (_) => TickerScreen(
            network: _network,
            rows:
                _ticker.map((t) => ListTile(title: Text(t.message))).toList()),
        AppRoutes.polymarketGlobal: (_) => PolymarketGlobalScreen(
            network: _network,
            rows: _polyGlobal
                .map((m) => ListTile(title: Text(m.title)))
                .toList()),
        AppRoutes.polymarketEvent: (_) => PolymarketEventScreen(
            network: _network,
            rows:
                _polyEvent.map((m) => ListTile(title: Text(m.title))).toList()),
        AppRoutes.ranking: (_) => _showcaseUserFeature(
              title: 'Ranking',
              metric: '#12',
              label: 'Position équipe',
              items: const [
                ShowcaseItem(
                    title: 'Les Rubis', subtitle: '1 240 pts', status: 'TOP 1'),
                ShowcaseItem(
                    title: 'La Terrasse',
                    subtitle: '1 080 pts',
                    status: 'TOP 2'),
                ShowcaseItem(
                    title: 'TON équipe',
                    subtitle: '940 pts • +3 places',
                    status: 'LIVE'),
              ],
            ),
        AppRoutes.battles: (_) => _showcaseUserFeature(
              title: 'Battles',
              metric: '68%',
              label: 'Vote A en tête',
              items: const [
                ShowcaseItem(
                    title: 'DJ Set: Techno vs Afro',
                    subtitle: 'Vote ouvert encore 06:42',
                    status: 'OPEN'),
                ShowcaseItem(
                    title: 'Battle chants',
                    subtitle: 'Finale prête côté orga',
                    status: 'NEXT'),
              ],
              actions: const [
                ShowcaseAction(label: 'Voter A', icon: Icons.how_to_vote),
                ShowcaseAction(label: 'Voter B', icon: Icons.how_to_vote),
              ],
            ),
        AppRoutes.hunts: (_) => _showcaseUserFeature(
              title: 'Hunts',
              metric: '3/7',
              label: 'Indices trouvés',
              items: const [
                ShowcaseItem(
                    title: 'Indice #4',
                    subtitle: 'Près du bar B • QR à scanner',
                    status: 'ACTIVE'),
                ShowcaseItem(
                    title: 'Bonus équipe',
                    subtitle: '+120 pts si trouvé avant 23h',
                    status: 'BOOST'),
              ],
              actions: const [
                ShowcaseAction(label: 'Scanner indice', icon: Icons.qr_code),
              ],
            ),
        AppRoutes.wifi: (_) => _showcaseUserFeature(
              title: 'WiFi',
              metric: 'TORÈ-GUEST',
              label: 'Réseau événement',
              items: const [
                ShowcaseItem(
                    title: 'QR WiFi',
                    subtitle: 'Connexion invitée sans mot de passe visible',
                    status: 'READY'),
                ShowcaseItem(
                    title: 'Rotation sécurité',
                    subtitle: 'Token renouvelé après la soirée',
                    status: 'SAFE'),
              ],
            ),
        AppRoutes.safeKit: (_) => _showcaseUserFeature(
              title: 'Safe Kit',
              metric: '2 min',
              label: 'Temps réponse staff',
              items: const [
                ShowcaseItem(
                    title: 'Buddy check',
                    subtitle: 'Prévenir un contact de confiance',
                    status: 'ON'),
                ShowcaseItem(
                    title: 'Alerte discrète',
                    subtitle: 'Remonte au hub orga sans exposer le message',
                    status: 'ARMED'),
              ],
              actions: const [
                ShowcaseAction(
                    label: 'Check-in OK', icon: Icons.health_and_safety),
                ShowcaseAction(label: 'Demander aide', icon: Icons.warning),
              ],
            ),
        AppRoutes.forum: (_) => _isConnectedAccount
            ? ScreenScaffold(
                title: 'Forum',
                connectivity: _network,
                body: _ForumCommunitySurface(
                  fullPage: true,
                  onOpenForum: () => ToreFeedback.success(
                      context, 'Page publique du forum ouverte.'),
                  onSubmitRequest: () => ToreFeedback.success(context,
                      'Demande de forum envoyée à la modération TORÈ.'),
                ),
              )
            : const ScreenScaffold(
                title: 'Forum',
                body: BlockedStateView(
                    title: 'Connexion requise',
                    message:
                        'Le Forum TORÈ est réservé aux comptes connectés pour protéger les rôles et permissions.')),
        AppRoutes.calendar: (_) => _showcaseUserFeature(
              title: 'Calendar',
              metric: '23:00',
              label: 'Prochain temps fort',
              items: const [
                ShowcaseItem(
                    title: 'Battle DJ',
                    subtitle: 'Scène principale • rappel activé',
                    status: 'NEXT'),
                ShowcaseItem(
                    title: 'Dernier service bar',
                    subtitle: 'Notification 15 min avant',
                    status: 'SYNC'),
              ],
            ),
        AppRoutes.glossary: (_) => _showcaseUserFeature(
              title: 'Glossary',
              metric: '18',
              label: 'Termes comité',
              items: const [
                ShowcaseItem(
                    title: 'Baptême',
                    subtitle: 'Définition publique et règles de contexte',
                    status: 'PUBLIC'),
                ShowcaseItem(
                    title: 'Comité',
                    subtitle: 'Contacts utiles et responsabilités',
                    status: 'OK'),
              ],
            ),
        AppRoutes.profile: (_) => ProfileSettingsScreen(
            network: _network,
            onOpenDiagnostics: _diagnosticsAllowed ? _openDiagnostics : null,
            onOpenHelp: () => Navigator.pushNamed(context, AppRoutes.userHelp)),
        AppRoutes.orgaHub: (_) => _mustShowUpdateRequired
            ? UpdateRequiredScreen(
                mode: _mode,
                message: _updateRequiredMessage,
                blockedByVersion: _belowMinSupportedVersion)
            : OrgaEventControlHubScreen(
                network: _network,
                writeAllowed: _writeAllowed('orga_event_control_hub'),
                entryApprovedCount: _entryStats?.approvedCount ?? 0,
                environmentLabel: appEnvironmentLabel(_environment),
                environmentColor: _environmentColor,
                onOpenExports: () =>
                    Navigator.pushNamed(context, AppRoutes.orgaExports),
                onOpenRunbook: () =>
                    Navigator.pushNamed(context, AppRoutes.orgaRunbook)),
        AppRoutes.orgaEntry: (_) => EntryStaffScreen(network: _network),
        AppRoutes.orgaMenu: (_) => OrgaMenuAdminScreen(network: _network),
        AppRoutes.orgaMarket: (_) => OrgaPolymarketAdminScreen(
            network: _network,
            onSensitive: (a) => _sensitiveWrite('orga_polymarket_admin', a)),
        AppRoutes.orgaUrgency: (_) => OrgaUrgencyActionsScreen(
            network: _network,
            onSensitive: (a) => _sensitiveWrite('orga_urgency_actions', a)),
        AppRoutes.orgaMusic: (_) => _showcaseOrgaFeature(
              title: 'Music Admin',
              metric: 'OPEN',
              label: 'Round de vote',
              items: const [
                ShowcaseItem(
                    title: 'Playlist prioritaire',
                    subtitle: '3 sons en file, override staff possible',
                    status: 'LIVE'),
                ShowcaseItem(
                    title: 'Suggestion publique',
                    subtitle: 'Filtrage doublons et votes par compte',
                    status: 'ON'),
              ],
              actions: const [
                ShowcaseAction(label: 'Forcer morceau', icon: Icons.music_note),
                ShowcaseAction(
                    label: 'Clôturer round', icon: Icons.stop_circle),
              ],
            ),
        AppRoutes.orgaBattle: (_) => _showcaseOrgaFeature(
              title: 'Battle Admin',
              metric: '2',
              label: 'Battles actives',
              items: const [
                ShowcaseItem(
                    title: 'DJ Set',
                    subtitle: '68% option A • clôture manuelle disponible',
                    status: 'OPEN'),
                ShowcaseItem(
                    title: 'Chants',
                    subtitle: 'Finale préparée, publication en attente',
                    status: 'DRAFT'),
              ],
            ),
        AppRoutes.orgaHunt: (_) => _showcaseOrgaFeature(
              title: 'Hunt Admin',
              metric: '7',
              label: 'QR indices',
              items: const [
                ShowcaseItem(
                    title: 'Indice terrasse',
                    subtitle: 'Non découvert • bonus +120 pts',
                    status: 'HIDDEN'),
                ShowcaseItem(
                    title: 'Indice bar B',
                    subtitle: 'Découvert par Les Rubis',
                    status: 'FOUND'),
              ],
            ),
        AppRoutes.orgaForum: (_) => _showcaseOrgaFeature(
              title: 'Forum Moderation',
              metric: '3',
              label: 'À relire',
              items: const [
                ShowcaseItem(
                    title: 'Signalement',
                    subtitle: 'Message masqué automatiquement',
                    status: 'REVIEW'),
                ShowcaseItem(
                    title: 'Annonce épinglée',
                    subtitle: 'Visible sur le hub utilisateur',
                    status: 'PIN'),
              ],
            ),
        AppRoutes.userHelp: (_) => RunbookScreen(
            onOpenUrgency: () =>
                Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaRunbook: (_) => RunbookScreen(
            onOpenUrgency: () =>
                Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaExports: (_) => OrgaExportsScreen(
            eventId: _mobileBootstrap.eventApiId,
            environment: _environment,
            moduleStates: _eventContext?.moduleStates ?? const {},
            backendPack: _orgaQrPack,
            onOpenInApp: _openDeepLink),
        AppRoutes.devDiagnostics: (_) => _diagnosticsAllowed
            ? DiagnosticsScreen(
                mode: _mode,
                snapshot: _userSnapshot,
                eventContext: _eventContext,
                networkState: _network,
                networkTransitionAt: _networkTransitionAt,
                apiClient: _api,
                cacheStore: _cache,
                idempotencyStore: _writerStore,
                environment: _environment,
                environmentColor: _environmentColor,
                buildInfo: _buildInfo,
                remoteConfig:
                    _remoteConfig ?? RemoteConfigPayload.defaults(_environment),
                onSimulatedNetworkChanged: (state) {
                  if (!mounted) return;
                  setState(() {
                    _network = state;
                    _networkTransitionAt = DateTime.now();
                  });
                },
                onOpenUrl: _openDeepLink)
            : const ScreenScaffold(
                title: 'Diagnostics disabled',
                scopeBadges: ['PROD'],
                body: BlockedStateView(
                    title: 'Diagnostics hidden',
                    message: 'Diagnostics are disabled by remote config.')),
        AppRoutes.barDashboard: (_) => BarDashboardScreen(network: _network),
        AppRoutes.barMenu: (_) => FullMenuAdminScreen(network: _network),
        AppRoutes.barZones: (_) => ZonesQrAdminScreen(
            network: _network, zones: _zones.map((z) => z.name).toList()),
        AppRoutes.barAnalytics: (_) => AnalyticsScreen(network: _network),
        AppRoutes.blocked: (ctx) {
          final args = ModalRoute.of(ctx)?.settings.arguments;
          final mapped =
              args is Map<String, dynamic> ? args : const <String, dynamic>{};
          final title = mapped['title']?.toString() ?? 'Accès indisponible';
          final message = mapped['message']?.toString() ??
              'Ce module est OFF, en pause ou non autorisé pour votre mode actuel.';
          final cta = mapped['cta']?.toString();
          return ScreenScaffold(
              title: 'Blocked',
              scopeBadges: const ['GUARD'],
              body: BlockedStateView(
                  title: title, message: message, ctaLabel: cta));
        },
      },
      home: !_consented || _loading
          ? (_loading
              ? BootSplashScreen(
                  network: _network,
                  environmentLabel: appEnvironmentLabel(_environment),
                  environmentColor: _environmentColor,
                  onLongPressDiagnostics:
                      _diagnosticsAllowed ? _openDiagnostics : null)
              : ConsentCharterScreen(onAccept: () {
                  if (!mounted) return;
                  setState(() {
                    _consented = true;
                    _selectedUserTab = 0;
                  });
                }))
          : Scaffold(
              appBar: AppBar(
                title: Row(children: [
                  Image.asset('assets/branding/logo_minimal.png',
                      width: 32, height: 32),
                  const SizedBox(width: ToreTokens.s8),
                  const Text('TORÈ'),
                ]),
                actions: [
                  Padding(
                    padding: const EdgeInsets.only(right: ToreTokens.s8),
                    child: Center(
                      child: ToreBadge(
                          label: 'LIVE',
                          color: _network == ConnectivityState.online
                              ? ToreTokens.ruby
                              : ToreTokens.warning),
                    ),
                  ),
                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => _navigatorKey.currentState
                        ?.pushNamed(AppRoutes.profile),
                    child: const SizedBox(
                      width: 56,
                      height: 56,
                      child: Icon(Icons.person_outline),
                    ),
                  ),
                ],
              ),
              floatingActionButton: _mode == ToreMode.user
                  ? FloatingActionButton(
                      onPressed: () => setState(() => _selectedUserTab = 2),
                      child: const Icon(Icons.qr_code_scanner))
                  : null,
              bottomNavigationBar: _mode == ToreMode.user
                  ? NavigationBar(
                      selectedIndex: _isConnectedAccount
                          ? _selectedUserTab
                          : _selectedUserTab.clamp(0, 3),
                      destinations: [
                        const NavigationDestination(
                            icon: Icon(Icons.home), label: 'Hub'),
                        const NavigationDestination(
                            icon: Icon(Icons.candlestick_chart),
                            label: 'Ticker'),
                        const NavigationDestination(
                            icon: Icon(Icons.qr_code_scanner),
                            label: 'Scanner'),
                        const NavigationDestination(
                            icon: Icon(Icons.show_chart), label: 'Bets'),
                        if (_isConnectedAccount)
                          const NavigationDestination(
                              icon: Icon(Icons.forum), label: 'Forum'),
                      ],
                      onDestinationSelected: (i) {
                        if (!mounted) return;
                        setState(() => _selectedUserTab = i);
                      },
                    )
                  : null,
              body: _shellBody(context),
            ),
      onGenerateRoute: (settings) {
        final name = settings.name ?? '';
        if (_guards.isLegacyRoute(name)) {
          return MaterialPageRoute(
            builder: (_) => const ScreenScaffold(
              title: 'Blocked',
              scopeBadges: ['GUARD'],
              body: BlockedStateView(
                title: 'Surface legacy désactivée',
                message:
                    'Cette surface legacy est masquée pendant la convergence rebuild.',
              ),
            ),
          );
        }
        if (name.startsWith('/orga') && _mode != ToreMode.orga) {
          return MaterialPageRoute(
              builder: (_) => const ScreenScaffold(
                  title: 'Blocked',
                  scopeBadges: ['GUARD'],
                  body: BlockedStateView(
                      title: 'Mauvais mode',
                      message: 'Passez en mode ORGA pour ouvrir cet écran.')));
        }
        return null;
      },
    );
  }
}

class _HeroStatusCard extends StatelessWidget {
  const _HeroStatusCard({
    required this.mode,
    required this.eventName,
    required this.barName,
    required this.eventState,
    this.syncedAt,
  });

  final ToreMode mode;
  final String eventName;
  final String barName;
  final EventState eventState;
  final DateTime? syncedAt;

  @override
  Widget build(BuildContext context) {
    final stateLabel = eventState.name.toUpperCase();
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF261018), ToreTokens.surface],
        ),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: ToreTokens.black,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: ToreTokens.ruby),
              ),
              child: const Icon(Icons.local_fire_department,
                  color: ToreTokens.yellowCta),
            ),
            const SizedBox(width: ToreTokens.s12),
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(eventName,
                        style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: ToreTokens.s4),
                    Text('$barName · pass actif'),
                  ]),
            ),
            ToreBadge(
                label: stateLabel == 'LIVE' ? 'LIVE' : 'BETA',
                color: eventState.isLive ? ToreTokens.ruby : Colors.orange),
          ]),
          const SizedBox(height: ToreTokens.s16),
          Row(children: const [
            Expanded(child: _HeroMetric(value: '€129', label: 'wallet')),
            SizedBox(width: ToreTokens.s8),
            Expanded(child: _HeroMetric(value: '244', label: 'check-ins')),
            SizedBox(width: ToreTokens.s8),
            Expanded(child: _HeroMetric(value: '03', label: 'orders')),
          ]),
        ]),
      ),
    );
  }
}

class _HeroMetric extends StatelessWidget {
  const _HeroMetric({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(ToreTokens.s8),
      decoration: BoxDecoration(
        color: ToreTokens.black.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: ToreTypography.monoNumber(context, size: 18)),
        Text(label,
            style: const TextStyle(color: Colors.white54, fontSize: 11)),
      ]),
    );
  }
}

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.onOpen});

  final void Function(_QuickAction action) onOpen;

  @override
  Widget build(BuildContext context) {
    final actions = const [
      _QuickAction('Scanner', Icons.qr_code_scanner, AppRoutes.scanner,
          tabIndex: 2),
      _QuickAction('Join', Icons.group_add, AppRoutes.join),
      _QuickAction('Menu', Icons.local_bar, AppRoutes.menu),
      _QuickAction('Wallet', Icons.account_balance_wallet, AppRoutes.wallet),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: actions.length,
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 180,
        mainAxisSpacing: ToreTokens.s8,
        crossAxisSpacing: ToreTokens.s8,
        childAspectRatio: 2.35,
      ),
      itemBuilder: (context, index) {
        final action = actions[index];
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: Duration(milliseconds: 180 + index * 45),
          curve: Curves.easeOutBack,
          builder: (context, value, child) {
            return Opacity(
              opacity: value.clamp(0.0, 1.0),
              child: Transform.translate(
                offset: Offset(0, (1 - value) * 10),
                child:
                    Transform.scale(scale: 0.94 + value * 0.06, child: child),
              ),
            );
          },
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => onOpen(action),
            child: Container(
              decoration: BoxDecoration(
                color: ToreTokens.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: ToreTokens.border),
              ),
              child: Padding(
                padding: const EdgeInsets.all(ToreTokens.s12),
                child: Row(children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: BoxDecoration(
                      color: ToreTokens.ruby,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(action.icon, color: Colors.white, size: 19),
                  ),
                  const SizedBox(width: ToreTokens.s8),
                  Expanded(
                    child: Text(
                      action.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _TickerPreview extends StatelessWidget {
  const _TickerPreview({required this.items});

  final List<TickerItemDto> items;

  @override
  Widget build(BuildContext context) {
    final visible = items.take(4).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s12),
        child: Column(children: [
          for (var i = 0; i < visible.length; i++) ...[
            Row(children: [
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(
                  color: ToreTokens.yellowCta,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: ToreTokens.s12),
              Expanded(child: Text(visible[i].message)),
              const Icon(Icons.chevron_right, color: Colors.white38, size: 18),
            ]),
            if (i != visible.length - 1)
              const Divider(color: ToreTokens.border, height: 22),
          ],
        ]),
      ),
    );
  }
}

class _ScannerTabCard extends StatelessWidget {
  const _ScannerTabCard({required this.onOpen});

  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            height: 220,
            decoration: BoxDecoration(
              color: ToreTokens.black,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: ToreTokens.yellowCta, width: 1.4),
            ),
            child: Stack(alignment: Alignment.center, children: const [
              Icon(Icons.qr_code_scanner,
                  size: 92, color: ToreTokens.yellowCta),
              Positioned(
                bottom: 18,
                child: Text('QR event · menu · WiFi · invitation'),
              ),
            ]),
          ),
          const SizedBox(height: ToreTokens.s12),
          FilledButton.icon(
            onPressed: onOpen,
            icon: const Icon(Icons.center_focus_strong),
            label: const Text('Ouvrir le scanner'),
          ),
        ]),
      ),
    );
  }
}

class _MarketsTab extends StatelessWidget {
  const _MarketsTab({
    required this.global,
    required this.event,
    required this.onGlobal,
    required this.onEvent,
  });

  final List<PolymarketDto> global;
  final List<PolymarketDto> event;
  final VoidCallback onGlobal;
  final VoidCallback onEvent;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _SectionHeader(
          title: 'Bets globaux', actionLabel: 'Ouvrir', onTap: onGlobal),
      for (final item in global)
        _BetCard(title: item.title, odds: '62%', onTap: onGlobal),
      const SizedBox(height: ToreTokens.s12),
      _SectionHeader(title: 'Bets soirée', actionLabel: 'Live', onTap: onEvent),
      for (final item in event)
        _BetCard(title: item.title, odds: '1.8x', onTap: onEvent),
    ]);
  }
}

class _BetCard extends StatelessWidget {
  const _BetCard(
      {required this.title, required this.odds, required this.onTap});

  final String title;
  final String odds;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: ToreTokens.s8),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Row(children: [
              const Icon(Icons.show_chart, color: ToreTokens.yellowCta),
              const SizedBox(width: ToreTokens.s12),
              Expanded(
                  child: Text(title,
                      style: Theme.of(context).textTheme.titleMedium)),
              ToreBadge(label: odds, color: ToreTokens.rubyDeep),
            ]),
          ),
        ),
      ),
    );
  }
}

class _HomeActionPanel extends StatelessWidget {
  const _HomeActionPanel({
    required this.action,
    required this.onOpenFull,
    required this.onClose,
  });

  final _QuickAction action;
  final VoidCallback onOpenFull;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final copy = _HomeActionCopy.forRoute(action.route);
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onOpenFull,
      child: Card(
        color: ToreTokens.surfaceAlt,
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: ToreTokens.ruby.withValues(alpha: 0.22),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(action.icon, color: ToreTokens.yellowCta),
              ),
              const SizedBox(width: ToreTokens.s12),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(copy.title,
                          style: Theme.of(context).textTheme.titleMedium),
                      Text(copy.subtitle),
                    ]),
              ),
              IconButton(
                tooltip: 'Fermer',
                onPressed: onClose,
                icon: const Icon(Icons.close),
              ),
            ]),
            const SizedBox(height: ToreTokens.s12),
            Wrap(
              spacing: ToreTokens.s8,
              runSpacing: ToreTokens.s8,
              children: [
                for (final chip in copy.chips)
                  Chip(
                    label: Text(chip),
                    backgroundColor: ToreTokens.black,
                    side: const BorderSide(color: ToreTokens.ruby),
                  ),
              ],
            ),
            const SizedBox(height: ToreTokens.s12),
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: onOpenFull,
              child: Container(
                constraints: const BoxConstraints(minHeight: 46),
                decoration: BoxDecoration(
                  color: ToreTokens.ruby,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(copy.ctaIcon, color: Colors.white),
                    const SizedBox(width: ToreTokens.s8),
                    Text(
                      copy.cta,
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w800),
                    ),
                  ],
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _HomeActionCopy {
  const _HomeActionCopy({
    required this.title,
    required this.subtitle,
    required this.chips,
    required this.cta,
    required this.ctaIcon,
  });

  final String title;
  final String subtitle;
  final List<String> chips;
  final String cta;
  final IconData ctaIcon;

  static _HomeActionCopy forRoute(String route) {
    switch (route) {
      case AppRoutes.join:
        return const _HomeActionCopy(
          title: 'Rejoindre la soirée',
          subtitle: 'QR valide ou code manuel. Accès en un geste.',
          chips: ['Afond Night', 'Entrée gratuite', 'Pass actif'],
          cta: 'Ouvrir le join',
          ctaIcon: Icons.group_add,
        );
      case AppRoutes.menu:
        return const _HomeActionCopy(
          title: 'Menu express',
          subtitle: 'Ajoute au panier, confirme, puis montre le QR au bar.',
          chips: ['2 taps max', 'Panier inline', 'QR commande'],
          cta: 'Commander',
          ctaIcon: Icons.local_bar,
        );
      case AppRoutes.wallet:
        return const _HomeActionCopy(
          title: 'Wallet',
          subtitle: 'Solde, tickets et historique de la soirée.',
          chips: ['€129.20', 'Tickets prêts', 'Top-up'],
          cta: 'Voir le wallet',
          ctaIcon: Icons.account_balance_wallet,
        );
      case AppRoutes.safeKit:
        return const _HomeActionCopy(
          title: 'Safe Kit',
          subtitle: 'Aide discrète, buddy check et contact staff.',
          chips: ['Alerte discrète', 'Buddy OK', 'Staff 2 min'],
          cta: 'Ouvrir Safe Kit',
          ctaIcon: Icons.health_and_safety,
        );
      case AppRoutes.ranking:
        return const _HomeActionCopy(
          title: 'Ranking live',
          subtitle: 'Classement de la soirée et progression équipe.',
          chips: ['#12', '+3 places', '940 pts'],
          cta: 'Voir le classement',
          ctaIcon: Icons.leaderboard,
        );
      default:
        return const _HomeActionCopy(
          title: 'Action TORÈ',
          subtitle: 'Module prêt pour la soirée.',
          chips: ['LIVE', 'BETA'],
          cta: 'Ouvrir',
          ctaIcon: Icons.arrow_forward,
        );
    }
  }
}

class _HomeEventCard extends StatelessWidget {
  const _HomeEventCard({
    required this.title,
    required this.bar,
    required this.meta,
    required this.onTap,
  });

  final String title;
  final String bar;
  final String meta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Row(children: [
            Container(
              width: 52,
              height: 52,
              decoration: BoxDecoration(
                color: ToreTokens.rubyDeep,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.local_fire_department,
                  color: ToreTokens.yellowCta),
            ),
            const SizedBox(width: ToreTokens.s12),
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s4),
                    Text(bar, style: const TextStyle(color: Colors.white70)),
                    Text(meta,
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 12)),
                  ]),
            ),
            const Icon(Icons.arrow_forward_ios,
                color: ToreTokens.yellowCta, size: 16),
          ]),
        ),
      ),
    );
  }
}

class _BarsPreview extends StatelessWidget {
  const _BarsPreview({required this.onBarTap});

  final VoidCallback onBarTap;

  @override
  Widget build(BuildContext context) {
    final bars = const [
      ('TORÈ Test Bar', 'Live · 2 events'),
      ('Bar B', 'Happy hour · 1 event'),
    ];
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: bars.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: ToreTokens.s8,
        crossAxisSpacing: ToreTokens.s8,
        childAspectRatio: 1.5,
      ),
      itemBuilder: (context, index) {
        final bar = bars[index];
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: onBarTap,
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: ToreTokens.ruby.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Icon(Icons.storefront,
                          color: ToreTokens.yellowCta, size: 20),
                    ),
                    Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(bar.$1,
                              style: Theme.of(context).textTheme.titleMedium),
                          Text(bar.$2,
                              style: const TextStyle(
                                  color: Colors.white54, fontSize: 12)),
                        ]),
                  ]),
            ),
          ),
        );
      },
    );
  }
}

class _ForumCommunitySurface extends StatefulWidget {
  const _ForumCommunitySurface({
    required this.onOpenForum,
    required this.onSubmitRequest,
    this.fullPage = false,
  });

  final VoidCallback onOpenForum;
  final VoidCallback onSubmitRequest;
  final bool fullPage;

  @override
  State<_ForumCommunitySurface> createState() => _ForumCommunitySurfaceState();
}

class _ForumCommunitySurfaceState extends State<_ForumCommunitySurface> {
  late final TextEditingController _nameController;
  late final TextEditingController _descriptionController;
  late final TextEditingController _eventNameController;
  late final TextEditingController _eventPlaceController;
  late final TextEditingController _eventDateController;

  String _spaceType = 'Comité';
  String _forumName = 'Comité Saint-Torè';
  String _forumDescription = 'Espace public · Liège · folklore étudiant';
  bool _spaceCreated = true;
  int _selectedPanel = 0;

  final List<({String title, String detail})> _events = [
    (
      title: 'Afond Night',
      detail: 'Live · 244 entrées · menu + bets + safe kit'
    ),
    (title: 'Saint-Torè warmup', detail: 'Vendredi 22:30 · QR join activé'),
  ];

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: _forumName);
    _descriptionController = TextEditingController(
        text:
            'Accueil officiel du comité : description, bannière, événements, liens utiles et membres visibles.');
    _eventNameController = TextEditingController(text: 'TD Outremeuse');
    _eventPlaceController =
        TextEditingController(text: 'Liège · salle à confirmer');
    _eventDateController = TextEditingController(text: 'Vendredi · 22:30');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _descriptionController.dispose();
    _eventNameController.dispose();
    _eventPlaceController.dispose();
    _eventDateController.dispose();
    super.dispose();
  }

  void _submitRequest() {
    final name = _nameController.text.trim();
    setState(() {
      _spaceCreated = true;
      _forumName = name.isEmpty ? 'Nouveau $_spaceType TORÈ' : name;
      _forumDescription = '$_spaceType · demande acceptée · espace officiel';
      _selectedPanel = 1;
    });
    widget.onSubmitRequest();
    ToreFeedback.success(context, 'Espace créé : $_forumName');
  }

  void _createEvent() {
    final title = _eventNameController.text.trim();
    if (title.isEmpty) {
      ToreFeedback.error(context, 'Ajoute un nom d’événement.');
      return;
    }
    final place = _eventPlaceController.text.trim();
    final date = _eventDateController.text.trim();
    setState(() {
      _events.insert(0, (
        title: title,
        detail:
            '${date.isEmpty ? 'Date à confirmer' : date} · ${place.isEmpty ? 'Lieu à confirmer' : place} · brouillon TORÈ'
      ));
      _selectedPanel = 2;
    });
    ToreFeedback.success(context, 'Event créé dans le forum.');
  }

  @override
  Widget build(BuildContext context) {
    final panels = ['Créer', 'Gérer', 'Events', 'Salons'];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _SectionHeader(
          title: 'Forum TORÈ',
          actionLabel: widget.fullPage ? null : 'Page publique',
          onTap: widget.onOpenForum),
      Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: ToreTokens.border),
          color: ToreTokens.surface,
        ),
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  color: ToreTokens.rubyDeep,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: ToreTokens.yellowCta),
                ),
                child: const Icon(Icons.forum, color: ToreTokens.yellowCta),
              ),
              const SizedBox(width: ToreTokens.s12),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(_forumName,
                          style: Theme.of(context).textTheme.titleLarge),
                      Text(_forumDescription),
                    ]),
              ),
              ToreBadge(
                  label: _spaceCreated ? 'ACTIF' : 'BROUILLON',
                  color: _spaceCreated ? ToreTokens.ruby : ToreTokens.border),
            ]),
            const SizedBox(height: ToreTokens.s12),
            Text(_descriptionController.text.trim().isEmpty
                ? 'Page publique du forum : description, bannière, événements, liens utiles et membres publics.'
                : _descriptionController.text.trim()),
            const SizedBox(height: ToreTokens.s12),
            Row(children: [
              Expanded(
                  child:
                      _ForumStat(value: '${_events.length}', label: 'events')),
              const SizedBox(width: ToreTokens.s8),
              Expanded(
                  child: _ForumStat(
                      value: _spaceCreated ? '18' : '0', label: 'membres')),
              const SizedBox(width: ToreTokens.s8),
              Expanded(
                  child: _ForumStat(
                      value: _spaceCreated ? '4' : '0', label: 'salons')),
            ]),
            const SizedBox(height: ToreTokens.s12),
            Row(children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: widget.onOpenForum,
                  icon: const Icon(Icons.open_in_new),
                  label: const Text('Page publique'),
                ),
              ),
              const SizedBox(width: ToreTokens.s8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => setState(() => _selectedPanel = 1),
                  icon: const Icon(Icons.settings),
                  label: const Text('Gérer'),
                ),
              ),
            ]),
          ]),
        ),
      ),
      const SizedBox(height: ToreTokens.s12),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(children: [
          for (var i = 0; i < panels.length; i++) ...[
            ChoiceChip(
              label: Text(panels[i]),
              selected: _selectedPanel == i,
              onSelected: (_) => setState(() => _selectedPanel = i),
            ),
            const SizedBox(width: ToreTokens.s8),
          ],
        ]),
      ),
      const SizedBox(height: ToreTokens.s12),
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: switch (_selectedPanel) {
          0 => _ForumRequestCard(
              key: const ValueKey('create'),
              nameController: _nameController,
              descriptionController: _descriptionController,
              selectedType: _spaceType,
              onTypeChanged: (value) => setState(() => _spaceType = value),
              onSubmit: _submitRequest,
            ),
          1 => _ForumAdminCard(
              key: const ValueKey('admin'), forumName: _forumName),
          2 => _ForumEventsManagerCard(
              key: const ValueKey('events'),
              events: _events,
              eventNameController: _eventNameController,
              eventPlaceController: _eventPlaceController,
              eventDateController: _eventDateController,
              onCreateEvent: _createEvent,
            ),
          _ => const _ForumPrivateChannelsCard(key: ValueKey('channels')),
        },
      ),
      const SizedBox(height: ToreTokens.s12),
      _ForumFeedCard(events: _events),
      const SizedBox(height: ToreTokens.s12),
      const _ForumStatsCard(),
    ]);
  }
}

class _ForumStat extends StatelessWidget {
  const _ForumStat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(ToreTokens.s8),
      decoration: BoxDecoration(
        color: ToreTokens.black.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: ToreTokens.border),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: ToreTypography.monoNumber(context, size: 18)),
        Text(label,
            style: const TextStyle(color: Colors.white54, fontSize: 11)),
      ]),
    );
  }
}

class _ForumFeedCard extends StatelessWidget {
  const _ForumFeedCard({required this.events});

  final List<({String title, String detail})> events;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Fil public', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          const Text(
              'Comme une page communautaire : annonces, events, souvenirs et liens utiles.'),
          const SizedBox(height: ToreTokens.s12),
          for (final event in events.take(3))
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event, color: ToreTokens.yellowCta),
              title: Text(event.title),
              subtitle: Text(event.detail),
              trailing: const Icon(Icons.chevron_right),
            ),
          const ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.campaign, color: ToreTokens.yellowCta),
            title: Text('Annonce comité'),
            subtitle: Text('Les inscriptions staff sont ouvertes.'),
            trailing: Icon(Icons.chevron_right),
          ),
        ]),
      ),
    );
  }
}

class _ForumRequestCard extends StatelessWidget {
  const _ForumRequestCard({
    super.key,
    required this.nameController,
    required this.descriptionController,
    required this.selectedType,
    required this.onTypeChanged,
    required this.onSubmit,
  });

  final TextEditingController nameController;
  final TextEditingController descriptionController;
  final String selectedType;
  final ValueChanged<String> onTypeChanged;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    final types = const [
      'Comité',
      'Cercle',
      'Ordre',
      'Régionale',
      'Rivageoise',
      'Autre',
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Demander un espace',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          const Text(
              'Comité, ordre, régionale ou rivageoise : la demande est modérée avant création.'),
          const SizedBox(height: ToreTokens.s12),
          FilledButton.icon(
              onPressed: onSubmit,
              icon: const Icon(Icons.add_circle),
              label: const Text('Créer l’espace')),
          const SizedBox(height: ToreTokens.s12),
          Wrap(spacing: ToreTokens.s8, runSpacing: ToreTokens.s8, children: [
            for (final type in types)
              ChoiceChip(
                label: Text(type),
                selected: selectedType == type,
                onSelected: (_) => onTypeChanged(type),
              ),
          ]),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: nameController,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
                labelText: 'Nom du $selectedType',
                prefixIcon: const Icon(Icons.badge)),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: descriptionController,
            style: const TextStyle(color: Colors.white),
            minLines: 2,
            maxLines: 3,
            decoration: const InputDecoration(
                labelText: 'Description / justification',
                prefixIcon: Icon(Icons.description)),
          ),
        ]),
      ),
    );
  }
}

class _ForumEventsManagerCard extends StatelessWidget {
  const _ForumEventsManagerCard({
    super.key,
    required this.events,
    required this.eventNameController,
    required this.eventPlaceController,
    required this.eventDateController,
    required this.onCreateEvent,
  });

  final List<({String title, String detail})> events;
  final TextEditingController eventNameController;
  final TextEditingController eventPlaceController;
  final TextEditingController eventDateController;
  final VoidCallback onCreateEvent;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Créer un event TORÈ',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          const Text(
              'L’event est ajouté au forum, prêt pour QR join, menu, staff, bets et recap.'),
          const SizedBox(height: ToreTokens.s12),
          FilledButton.icon(
              onPressed: onCreateEvent,
              icon: const Icon(Icons.add),
              label: const Text('Créer l’event')),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: eventNameController,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(
                labelText: 'Nom de l’event', prefixIcon: Icon(Icons.event)),
          ),
          const SizedBox(height: ToreTokens.s8),
          TextField(
            controller: eventDateController,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(
                labelText: 'Date / heure', prefixIcon: Icon(Icons.schedule)),
          ),
          const SizedBox(height: ToreTokens.s8),
          TextField(
            controller: eventPlaceController,
            style: const TextStyle(color: Colors.white),
            decoration: const InputDecoration(
                labelText: 'Lieu', prefixIcon: Icon(Icons.place)),
          ),
          const SizedBox(height: ToreTokens.s12),
          for (final event in events)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading:
                  const Icon(Icons.local_activity, color: ToreTokens.yellowCta),
              title: Text(event.title),
              subtitle: Text(event.detail),
              trailing: const ToreBadge(label: 'TORÈ'),
            ),
        ]),
      ),
    );
  }
}

class _ForumPrivateChannelsCard extends StatelessWidget {
  const _ForumPrivateChannelsCard({super.key});

  @override
  Widget build(BuildContext context) {
    final channels = const [
      ('# annonces', 'Lecture publique, écriture responsables'),
      ('# staff-event', 'Préparation, QR pack, rôles terrain'),
      ('# comité-privé', 'Discussion interne et passation'),
      ('# modération', 'Signalements, permissions, accès'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Salons privés', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          const Text(
              'Des groupes de discussion type Discord, reliés aux rôles TORÈ et aux events.'),
          const SizedBox(height: ToreTokens.s12),
          for (final channel in channels)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.tag, color: ToreTokens.yellowCta),
              title: Text(channel.$1),
              subtitle: Text(channel.$2),
              trailing: const ToreBadge(label: 'PRIVÉ'),
            ),
        ]),
      ),
    );
  }
}

class _ForumAdminCard extends StatelessWidget {
  const _ForumAdminCard({super.key, required this.forumName});

  final String forumName;

  @override
  Widget build(BuildContext context) {
    final rows = const [
      ('Infos forum', 'Description, bannière, liens utiles'),
      ('Membres', 'Invitations, visibilité publique'),
      ('Fonctions & grades', 'Rôles, permissions, accès'),
      ('Accès', 'Lecture, écriture, modération'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Gestion responsable',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s4),
          Text(forumName, style: const TextStyle(color: Colors.white70)),
          const SizedBox(height: ToreTokens.s8),
          for (final row in rows)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.admin_panel_settings,
                  color: ToreTokens.yellowCta),
              title: Text(row.$1),
              subtitle: Text(row.$2),
              trailing: const Icon(Icons.chevron_right),
            ),
        ]),
      ),
    );
  }
}

class _ForumStatsCard extends StatelessWidget {
  const _ForumStatsCard();

  @override
  Widget build(BuildContext context) {
    final rows = const [
      ('Afond Night', '244 entrées · menu + bets + safe kit'),
      ('Rooftop After', '128 entrées · tickets + hunts'),
      ('Saint-Torè warmup', 'Post-event exporté'),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Statistiques TORÈ',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          const Text(
              'Résumé post-event, modules activés, tickets, ventes et participation aux bets/hunts/battles.'),
          const SizedBox(height: ToreTokens.s12),
          for (final row in rows)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.insights, color: ToreTokens.yellowCta),
              title: Text(row.$1),
              subtitle: Text(row.$2),
            ),
        ]),
      ),
    );
  }
}

class _ConnectedOnlyForumPrompt extends StatelessWidget {
  const _ConnectedOnlyForumPrompt();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(ToreTokens.s16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.lock, color: ToreTokens.yellowCta),
          SizedBox(height: ToreTokens.s12),
          Text('Forum disponible après connexion',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          SizedBox(height: ToreTokens.s8),
          Text(
              'Connecte-toi pour rejoindre un comité, demander un espace ou gérer les rôles folkloriques.'),
        ]),
      ),
    );
  }
}

class _QuickAction {
  const _QuickAction(this.label, this.icon, this.route, {this.tabIndex});

  final String label;
  final IconData icon;
  final String route;
  final int? tabIndex;
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.actionLabel, this.onTap});

  final String title;
  final String? actionLabel;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(
          top: ToreTokens.s8, bottom: ToreTokens.s8, left: ToreTokens.s4),
      child: Row(children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        if (actionLabel != null)
          TextButton(onPressed: onTap, child: Text(actionLabel!)),
      ]),
    );
  }
}
