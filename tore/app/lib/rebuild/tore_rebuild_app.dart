import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

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
import 'ui/screens/access/access_quick_grid.dart';
import 'ui/screens/access/access_scanner_screen.dart';
import 'ui/screens/access/access_screen.dart';
import 'ui/screens/bar/bar_screens.dart';
import 'ui/screens/dev/diagnostics_screen.dart';
import 'ui/screens/forum/forum_cards.dart';
import 'ui/screens/forum/forum_screen.dart';
import 'ui/screens/help/runbook_screens.dart';
import 'ui/screens/home/hero_status_card.dart';
import 'ui/screens/home/home_screen.dart';
import 'ui/screens/home/quick_actions.dart';
import 'ui/screens/home/ticker_preview.dart';
import 'ui/screens/orga/orga_exports_screen.dart';
import 'ui/screens/orga/orga_screens.dart';
import 'ui/screens/showcase/showcase_screens.dart';
import 'ui/screens/system/update_required_screen.dart';
import 'ui/screens/user/user_screens.dart';
import 'ui/shell/tore_app_shell.dart';
import 'ui/theme/tore_theme.dart';
import 'ui/widgets/primitives.dart';
import 'ui/widgets/section_header.dart';

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
  HomeQuickAction? _activeHomeAction;
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

  Future<void> _openExternalUrl(String url) async {
    final uri = Uri.parse(url);
    final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!launched && mounted) {
      ToreFeedback.error(context, 'Lien impossible à ouvrir pour le moment.');
    }
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

  OrderDto? get _activeOrder {
    const activeStatuses = {'NEW', 'IN_PROGRESS', 'READY'};
    for (final order in _orders) {
      if (activeStatuses.contains(order.status)) return order;
    }
    return null;
  }

  List<AccessQuickAction> _accessQuickActions() {
    final actions = <AccessQuickAction>[
      const AccessQuickAction(
        label: 'Join',
        subtitle: 'Entrer avec un code event',
        icon: Icons.group_add,
        route: AppRoutes.join,
      ),
      const AccessQuickAction(
        label: 'Menu',
        subtitle: 'Commander et montrer le QR',
        icon: Icons.local_bar,
        route: AppRoutes.menu,
      ),
      const AccessQuickAction(
        label: 'Wallet',
        subtitle: 'Solde et tickets',
        icon: Icons.account_balance_wallet,
        route: AppRoutes.wallet,
      ),
      const AccessQuickAction(
        label: 'Events',
        subtitle: 'Soirées et accès live',
        icon: Icons.event,
        route: AppRoutes.events,
      ),
      const AccessQuickAction(
        label: 'Bars',
        subtitle: 'Trouver les spots proches',
        icon: Icons.storefront,
        route: AppRoutes.bars,
      ),
      const AccessQuickAction(
        label: 'Aide',
        subtitle: 'Safe kit et support',
        icon: Icons.health_and_safety,
        route: AppRoutes.safeKit,
      ),
    ];
    return actions;
  }

  void _openAccessScanner() {
    Navigator.pushNamed(context, AppRoutes.scanner);
  }

  Widget _userTabContent(BuildContext context) {
    switch (_selectedUserTab) {
      case 1:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            SectionHeader(
              title: 'Ticker live',
              actionLabel: 'Filtres',
              onTap: () => ToreFeedback.success(
                context,
                'Filtres ticker: annonces, commandes, bets.',
              ),
            ),
            TickerPreview(items: _ticker),
          ],
        );
      case 2:
        return AccessScreen(
          onOpenScanner: _openAccessScanner,
          onTorch: _openAccessScanner,
          onManualCode: _openAccessScanner,
          onHelp: _openAccessScanner,
          onOpenRoute: (route) => Navigator.pushNamed(context, route),
          quickActions: _accessQuickActions(),
          activeOrder: _activeOrder,
          zones: _zones,
        );
      case 3:
        return MarketsTab(
          global: _polyGlobal,
          event: _polyEvent,
          onGlobal: () =>
              Navigator.pushNamed(context, AppRoutes.polymarketGlobal),
          onEvent: () =>
              Navigator.pushNamed(context, AppRoutes.polymarketEvent),
        );
      case 4:
        return _isConnectedAccount
            ? ForumScreen(
                onOpenForum: () =>
                    Navigator.pushNamed(context, AppRoutes.forum),
                onSubmitRequest: () => ToreFeedback.success(
                  context,
                  'Demande de forum envoyée à la modération TORÈ.',
                ),
              )
            : const ConnectedOnlyForumPrompt();
      default:
        return HomeScreen(
          activeAction: _activeHomeAction,
          onOpenAction: (action) {
            if (action.tabIndex != null) {
              setState(() {
                _activeHomeAction = null;
                _selectedUserTab = action.tabIndex!;
              });
              return;
            }
            setState(() => _activeHomeAction = action);
          },
          onCloseAction: () => setState(() => _activeHomeAction = null),
          eventName: _mobileBootstrap.eventName ?? 'Afond Night',
          barName: _mobileBootstrap.barName ?? 'TORÈ Test Bar',
          onOpenEventHub: () =>
              Navigator.pushNamed(context, AppRoutes.eventHub),
          onOpenEvents: () => Navigator.pushNamed(context, AppRoutes.events),
          onOpenBars: () => Navigator.pushNamed(context, AppRoutes.bars),
          onOpenExternalUrl: _openExternalUrl,
        );
    }
  }

  Widget _shellBody(BuildContext context) {
    final currentEventState =
        _useShowcaseFixtures ? EventState.live : _eventContext?.eventState;
    final content = switch (_mode) {
      ToreMode.user => _userTabContent(context),
      ToreMode.orga => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: _modeCards(
            title: 'Command Center',
            subtitle:
                'Pilotage orga live pour ${_mobileBootstrap.eventName ?? _mobileBootstrap.eventKey}',
            mode: ToreMode.orga,
            metric: '${_entryStats?.approvedCount ?? 0}',
            metricLabel: 'entrées validées',
          ),
        ),
      ToreMode.bar => Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: _modeCards(
            title: 'Bar Ops',
            subtitle: 'Commandes, zones et analytics du bar actif',
            mode: ToreMode.bar,
            metric: '${_orders.length}',
            metricLabel: 'commandes live',
          ),
        ),
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
          HeroStatusCard(
            mode: _mode,
            eventName: _mobileBootstrap.eventName ?? _mobileBootstrap.eventKey,
            barName: _mobileBootstrap.barName ?? 'Bar actif',
            eventState: currentEventState ?? EventState.draft,
            syncedAt: _eventContext?.syncedAt,
            walletBalance: _wallet?.balance ?? 0,
            checkInCount: _entryStats?.approvedCount ?? 0,
            orderCount: _orders.length,
          ),
          const SizedBox(height: ToreTokens.s16),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            child: KeyedSubtree(
              key: ValueKey(
                  '${_mode.name}-$_selectedUserTab-${_activeHomeAction?.route ?? ''}'),
              child: content,
            ),
          ),
        ],
      ),
    );
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
        AppRoutes.scanner: (_) => AccessScannerScreen(
            onResolve: _resolveQrPayload, network: _network),
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
                body: ForumScreen(
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
          : ToreAppShell(
              mode: _mode,
              network: _network,
              walletBalance: _wallet?.balance,
              selectedUserTab: _selectedUserTab,
              isConnectedAccount: _isConnectedAccount,
              onOpenProfile: () =>
                  _navigatorKey.currentState?.pushNamed(AppRoutes.profile),
              onOpenNotifications: () => ToreFeedback.success(
                context,
                'Centre notifications TORÈ bientôt synchronisé.',
              ),
              onOpenWallet: () =>
                  _navigatorKey.currentState?.pushNamed(AppRoutes.wallet),
              onOpenAccess: () => setState(() => _selectedUserTab = 2),
              onSelectUserTab: (i) {
                if (!mounted) return;
                setState(() => _selectedUserTab = i);
              },
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
