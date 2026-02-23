import 'package:flutter/material.dart';

import 'config/app_environment.dart';
import 'models/event_context.dart';
import 'models/backend_models.dart';
import 'models/qr_resolve.dart';
import 'models/rebuild_types.dart';
import 'models/snapshot.dart';
import 'routing/app_routes.dart';
import 'routing/deep_link_router.dart';
import 'routing/qr_router.dart';
import 'routing/route_guards.dart';
import 'services/api_client.dart';
import 'services/cache_store.dart';
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
  final _api = ApiClient();
  final _cache = CacheStore();
  final _guards = RouteGuards();
  final _router = QrRouter();
  final _deepLinkRouter = DeepLinkRouter();
  final _networkStateResolver = NetworkStateResolver();
  late final IdempotencyStore _writerStore = IdempotencyStore(persistence: SharedPrefsIdempotencyPersistence());
  late final IdempotentWriter _writer = IdempotentWriter(store: _writerStore);
  late final List<ModuleDefinition> _defs = buildModuleDefinitions();
  late final AppEnvironment _environment = appEnvironmentFromDefine();
  late final BuildInfo _buildInfo = BuildInfo.fromEnvironment();
  late final RemoteConfigService _remoteConfigService = RemoteConfigService(apiClient: _api, cacheStore: _cache, environment: _environment);
  static const String _startupUrl = String.fromEnvironment('TORE_STARTUP_URL', defaultValue: '');

  ToreMode _mode = ToreMode.user;
  UserSnapshot? _userSnapshot;
  EventContext? _eventContext;
  ConnectivityState _network = ConnectivityState.online;
  DateTime _networkTransitionAt = DateTime.now();
  bool _loading = true;
  bool _consented = false;
  List<BarDto> _bars = const [];
  List<EventDto> _barEvents = const [];
  List<MenuItemDto> _menuItems = const [];
  WalletDto? _wallet;
  List<TickerItemDto> _ticker = const [];
  List<PolymarketDto> _polyGlobal = const [];
  List<PolymarketDto> _polyEvent = const [];
  EntryStatsDto? _entryStats;
  List<OrderDto> _orders = const [];
  List<ZoneDto> _zones = const [];
  Map<String, dynamic>? _orgaQrPack;
  RemoteConfigPayload? _remoteConfig;

  @override
  void initState() {
    super.initState();
    ClientLog.instance.hydrate();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    if (mounted) setState(() => _loading = true);
    final cachedMe = await _cache.loadCachedUser();
    final cachedEvent = await _cache.loadCachedEvent('event_42');
    _userSnapshot = cachedMe;
    _eventContext = cachedEvent;
    _remoteConfig = await _remoteConfigService.load();

    try {
      if (_networkStateResolver.canReadRemote(_network)) {
        _userSnapshot = await _api.fetchMeSnapshot();
        _eventContext = await _api.fetchEventContext('event_42', _defs);
        if (_userSnapshot != null) await _cache.saveUser(_userSnapshot!);
        if (_eventContext != null) await _cache.saveEvent(_eventContext!);
        await _loadDomainData();
      }
    } catch (_) {
      await ClientLog.instance.log('boot.hydration_fallback', {'reason': 'remote_unavailable'});
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        if (_startupUrl.trim().isNotEmpty) {
          WidgetsBinding.instance.addPostFrameCallback((_) => _openDeepLink(_startupUrl));
        }
      }
    }
  }

  Future<void> _loadDomainData() async {
    _bars = await _safeLoad(() => _api.fetchBars(network: _network), const <BarDto>[]);
    _barEvents = await _safeLoad(() => _api.fetchBarEvents('1', network: _network), const <EventDto>[]);
    _menuItems = await _safeLoad(() => _api.fetchMenu(eventId: '42', network: _network), const <MenuItemDto>[]);
    _wallet = await _safeLoad<WalletDto?>(() => _api.fetchWallet(eventId: '42', network: _network), null);
    _ticker = await _safeLoad(() async => (await _api.fetchTicker('42', network: _network)).items, const <TickerItemDto>[]);
    _polyGlobal = await _safeLoad(() => _api.fetchPolymarketGlobal(network: _network), const <PolymarketDto>[]);
    _polyEvent = await _safeLoad(() => _api.fetchPolymarketEvent('42', network: _network), const <PolymarketDto>[]);
    _entryStats = await _safeLoad(() => _api.fetchEntryStats('42', network: _network), const EntryStatsDto(approvedCount: 0, deniedCount: 0));
    _orders = await _safeLoad(() async => (await _api.fetchOrdersLive('42', network: _network)).items, const <OrderDto>[]);
    _zones = await _safeLoad(() => _api.fetchZones('1', network: _network), const <ZoneDto>[]);
    _orgaQrPack = await _safeLoad<Map<String, dynamic>?>(() => _api.fetchOrgaQrPack(_eventContext?.eventId ?? '42', network: _network), null);
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
    if (base == ModuleState.off) return ModuleState.off;
    if (event == EventState.paused && base == ModuleState.on) return ModuleState.frozen;
    if (event == EventState.readOnly || event == EventState.ended) return ModuleState.readOnly;
    return base;
  }


  bool get _writesDisabledByRemote => _remoteConfig?.disableWritesGlobal == true;

  bool get _belowMinSupportedVersion {
    final minVersion = _remoteConfig?.minSupportedVersion;
    if (minVersion != null && minVersion.isNotEmpty) {
      return isBelowMinVersion(_buildInfo.semver, minVersion);
    }
    final minBuild = _remoteConfig?.minSupportedBuild;
    return minBuild != null && _buildInfo.buildNumber < minBuild;
  }

  bool get _mustShowUpdateRequired => _belowMinSupportedVersion || (_writesDisabledByRemote && (_mode == ToreMode.orga || _belowMinSupportedVersion));

  String get _updateRequiredMessage {
    if (_belowMinSupportedVersion) {
      return 'Please update app to continue. Minimum required: ${_remoteConfig?.minSupportedVersion ?? _remoteConfig?.minSupportedBuild ?? 'latest'}.';
    }
    return _remoteConfig?.disableWritesMessage ?? 'Writes are temporarily frozen.';
  }

  bool get _diagnosticsAllowed => _remoteConfig?.diagnosticsEnabled ?? (_environment != AppEnvironment.prod);

  Color get _environmentColor => ToreTheme.envBadgeColor(_environment);

  bool _writeAllowed(String moduleId) => !_writesDisabledByRemote && _networkStateResolver.canWrite(_network) && _effectiveState(moduleId) == ModuleState.on;

  Future<void> _resolveQrPayload(String payload) async {
    try {
      final resolved = await _api.resolveQr(payload);
      final route = _router.targetFor(resolved);
      if (!mounted) return;
      if (resolved.isError || route == AppRoutes.blocked) {
        final err = resolveUiCopy(resolved.reason ?? 'qr_unknown');
        Navigator.pushNamed(context, AppRoutes.blocked, arguments: {'title': err.title, 'message': err.message, 'cta': err.ctaLabel});
        return;
      }
      Navigator.pushNamed(context, route);
    } catch (_) {
      if (!mounted) return;
      final err = resolveUiCopy('backend_down');
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {'title': err.title, 'message': err.message, 'cta': err.ctaLabel});
    }
  }



  Future<void> _openDeepLink(String url) async {
    final parsed = _deepLinkRouter.parse(url);
    if (parsed == null) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {'title': 'Lien invalide', 'message': 'Le lien n'est pas supporté par cette version de l'app.'});
      return;
    }

    if (parsed.isQr) {
      await _resolveQrPayload(parsed.qrPayload!);
      return;
    }

    final route = parsed.route;
    if (!_guards.routeAllowedForMode(route, _mode)) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {'title': 'Mauvais mode', 'message': 'Ce lien n'est pas autorisé pour le mode actif.'});
      return;
    }

    final moduleId = _moduleForRoute(route);
    if (moduleId != null && !_guards.deepLinkAllowed(_effectiveState(moduleId))) {
      if (!mounted) return;
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: {'title': 'Module indisponible', 'message': 'Le module ciblé est OFF ou temporairement désactivé.'});
      return;
    }

    if (!mounted) return;
    Navigator.pushNamed(context, route);
  }

  Future<void> _sensitiveWrite(String moduleId, String action) async {
    if (!_networkStateResolver.canWrite(_network)) {
      ClientLog.instance.log('write.blocked', {'reason_code': 'offline_write_blocked', 'network_state': _network.name, 'event_state': _eventContext?.eventState.name ?? 'none', 'module_state': _effectiveState(moduleId).name});
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Action impossible hors ligne. Revenez en ligne pour confirmer.')));
      return;
    }
    final reason = await ConfirmDialogWithReason.show(context, title: 'Confirm $action');
    if (reason == null) return;
    await _writer.write(
      endpoint: '/v1/$moduleId/write',
      intent: '$moduleId:$action:${_eventContext?.eventId}',
      body: {'action': action, 'reason_code': reason.code, 'reason_text': reason.text},
    );
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Action sent')));
  }

  List<Widget> _moduleCards(ToreMode mode) {
    final defs = _defs.where((d) => d.mode == mode).where((d) => _effectiveState(d.id) != ModuleState.off).toList();
    return [for (final d in defs) ModuleCard(def: d, state: _effectiveState(d.id), onOpen: () => _openModule(d.id))];
  }

  void _openModule(String moduleId) {
    final route = _mapModuleToRoute(moduleId);
    if (route == null) return;
    if (!_guards.routeAllowedForMode(route, _mode)) {
      Navigator.pushNamed(context, AppRoutes.blocked, arguments: 'Wrong mode for this route');
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
      'user_wallet': AppRoutes.wallet,
      'user_ticker': AppRoutes.ticker,
      'user_polymarket_global': AppRoutes.polymarketGlobal,
      'user_polymarket_event': AppRoutes.polymarketEvent,
      'user_login_profile': AppRoutes.profile,
      'orga_event_control_hub': AppRoutes.orgaHub,
      'orga_entry_mode': AppRoutes.orgaEntry,
      'orga_menu_admin': AppRoutes.orgaMenu,
      'orga_polymarket_admin': AppRoutes.orgaMarket,
      'orga_urgency_actions': AppRoutes.orgaUrgency,
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
      AppRoutes.wallet: 'user_wallet',
      AppRoutes.ticker: 'user_ticker',
      AppRoutes.polymarketGlobal: 'user_polymarket_global',
      AppRoutes.polymarketEvent: 'user_polymarket_event',
      AppRoutes.profile: 'user_login_profile',
      AppRoutes.orgaHub: 'orga_event_control_hub',
      AppRoutes.orgaEntry: 'orga_entry_mode',
      AppRoutes.orgaMenu: 'orga_menu_admin',
      AppRoutes.orgaMarket: 'orga_polymarket_admin',
      AppRoutes.orgaUrgency: 'orga_urgency_actions',
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
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.build(),
      initialRoute: AppRoutes.boot,
      routes: {
        AppRoutes.boot: (_) => _loading ? BootSplashScreen(network: _network, environmentLabel: appEnvironmentLabel(_environment), environmentColor: _environmentColor, onLongPressDiagnostics: _diagnosticsAllowed ? _openDiagnostics : null) : ConsentCharterScreen(onAccept: () { if (!mounted) return; setState(() => _consented = true); }),
        AppRoutes.home: (_) => _mustShowUpdateRequired ? UpdateRequiredScreen(mode: _mode, message: _updateRequiredMessage, blockedByVersion: _belowMinSupportedVersion) : HomeHubScreen(network: _network, cards: [HeaderCard(userSnapshot: _userSnapshot, eventContext: _eventContext), ..._moduleCards(ToreMode.user)]),
        AppRoutes.scanner: (_) => QrScannerScreen(onResolve: _resolveQrPayload, network: _network),
        AppRoutes.bars: (_) => BarsScreen(network: _network, children: _bars.map((b) => ListTile(title: Text(b.name), subtitle: Text(b.city ?? b.id))).toList()),
        AppRoutes.events: (_) => BarEventsScreen(children: _barEvents.map((e) => ListTile(title: Text(e.title), subtitle: Text(e.state ?? 'LIVE'))).toList(), network: _network),
        AppRoutes.join: (_) => JoinEventScreen(writeAllowed: _writeAllowed('user_join'), onJoin: () => _sensitiveWrite('user_join', 'join_event'), network: _network),
        AppRoutes.eventHub: (_) => EventHubScreen(network: _network, modules: _moduleCards(ToreMode.user), eventState: _eventContext?.eventState ?? EventState.draft, writeAllowedReason: _writeAllowed('user_event_hub') ? 'Writes enabled' : 'Writes blocked by network or event state'),
        AppRoutes.menu: (_) => MenuScreen(network: _network, items: _menuItems.map((m) => ListTile(title: Text(m.name), trailing: Text(m.price.toStringAsFixed(2)))).toList()),
        AppRoutes.wallet: (_) => WalletScreen(network: _network, rows: (_wallet?.timeline ?? const []).map((tx) => ListTile(title: Text(tx.type), trailing: Text(tx.delta.toStringAsFixed(2), style: const TextStyle(fontFamily: 'monospace')))).toList()),
        AppRoutes.ticker: (_) => TickerScreen(network: _network, rows: _ticker.map((t) => ListTile(title: Text(t.message))).toList()),
        AppRoutes.polymarketGlobal: (_) => PolymarketGlobalScreen(network: _network, rows: _polyGlobal.map((m) => ListTile(title: Text(m.title))).toList()),
        AppRoutes.polymarketEvent: (_) => PolymarketEventScreen(network: _network, rows: _polyEvent.map((m) => ListTile(title: Text(m.title))).toList()),
        AppRoutes.profile: (_) => ProfileSettingsScreen(network: _network, onOpenDiagnostics: _diagnosticsAllowed ? _openDiagnostics : null, onOpenHelp: () => Navigator.pushNamed(context, AppRoutes.userHelp)),
        AppRoutes.orgaHub: (_) => _mustShowUpdateRequired ? UpdateRequiredScreen(mode: _mode, message: _updateRequiredMessage, blockedByVersion: _belowMinSupportedVersion) : OrgaEventControlHubScreen(network: _network, writeAllowed: _writeAllowed('orga_event_control_hub'), entryApprovedCount: _entryStats?.approvedCount ?? 0, environmentLabel: appEnvironmentLabel(_environment), environmentColor: _environmentColor, onOpenExports: () => Navigator.pushNamed(context, AppRoutes.orgaExports), onOpenRunbook: () => Navigator.pushNamed(context, AppRoutes.orgaRunbook)),
        AppRoutes.orgaEntry: (_) => EntryStaffScreen(network: _network),
        AppRoutes.orgaMenu: (_) => OrgaMenuAdminScreen(network: _network),
        AppRoutes.orgaMarket: (_) => OrgaPolymarketAdminScreen(network: _network, onSensitive: (a) => _sensitiveWrite('orga_polymarket_admin', a)),
        AppRoutes.orgaUrgency: (_) => OrgaUrgencyActionsScreen(network: _network, onSensitive: (a) => _sensitiveWrite('orga_urgency_actions', a)),
        AppRoutes.userHelp: (_) => RunbookScreen(onOpenUrgency: () => Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaRunbook: (_) => RunbookScreen(onOpenUrgency: () => Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaExports: (_) => OrgaExportsScreen(eventId: _eventContext?.eventId ?? '42', environment: _environment, moduleStates: _eventContext?.moduleStates ?? const {}, backendPack: _orgaQrPack, onOpenInApp: _openDeepLink),
        AppRoutes.devDiagnostics: (_) => _diagnosticsAllowed ? DiagnosticsScreen(mode: _mode, snapshot: _userSnapshot, eventContext: _eventContext, networkState: _network, networkTransitionAt: _networkTransitionAt, apiClient: _api, cacheStore: _cache, idempotencyStore: _writerStore, environment: _environment, environmentColor: _environmentColor, buildInfo: _buildInfo, remoteConfig: _remoteConfig ?? RemoteConfigPayload.defaults(_environment), onSimulatedNetworkChanged: (state) { if (!mounted) return; setState(() { _network = state; _networkTransitionAt = DateTime.now(); }); }, onOpenUrl: _openDeepLink) : const ScreenScaffold(title: 'Diagnostics disabled', scopeBadges: ['PROD'], body: BlockedStateView(title: 'Diagnostics hidden', message: 'Diagnostics are disabled by remote config.')),
        AppRoutes.barDashboard: (_) => BarDashboardScreen(network: _network),
        AppRoutes.barOrders: (_) => OrdersLiveScreen(network: _network, rows: _orders.map((o) => ListTile(title: Text('Order ${o.id}'), trailing: Text(o.status))).toList()),
        AppRoutes.barMenu: (_) => FullMenuAdminScreen(network: _network),
        AppRoutes.barZones: (_) => ZonesQrAdminScreen(network: _network, zones: _zones.map((z) => z.name).toList()),
        AppRoutes.barAnalytics: (_) => AnalyticsScreen(network: _network),
        AppRoutes.blocked: (ctx) {
          final args = ModalRoute.of(ctx)?.settings.arguments;
          final mapped = args is Map<String, dynamic> ? args : const <String, dynamic>{};
          final title = mapped['title']?.toString() ?? 'Accès indisponible';
          final message = mapped['message']?.toString() ?? 'Ce module est OFF, en pause ou non autorisé pour votre mode actuel.';
          final cta = mapped['cta']?.toString();
          return ScreenScaffold(title: 'Blocked', scopeBadges: const ['GUARD'], body: BlockedStateView(title: title, message: message, ctaLabel: cta));
        },
      },
      home: !_consented || _loading
          ? (_loading ? BootSplashScreen(network: _network, environmentLabel: appEnvironmentLabel(_environment), environmentColor: _environmentColor, onLongPressDiagnostics: _diagnosticsAllowed ? _openDiagnostics : null) : ConsentCharterScreen(onAccept: () { if (!mounted) return; setState(() => _consented = true); }))
          : Scaffold(
              appBar: AppBar(
                title: const Text('TORÈ Night OS'),
                actions: [
                  DropdownButton<ConnectivityState>(
                    value: _network,
                    onChanged: (v) { if (!mounted) return; setState(() { _network = v ?? _network; _networkTransitionAt = DateTime.now(); }); },
                    items: ConnectivityState.values.map((e) => DropdownMenuItem(value: e, child: Text(e.name))).toList(),
                  ),
                  DropdownButton<ToreMode>(
                    value: _mode,
                    onChanged: (v) { if (!mounted) return; setState(() => _mode = v ?? _mode); },
                    items: ToreMode.values.where((m) => _guards.modeAllowed(m, _userSnapshot)).map((e) => DropdownMenuItem(value: e, child: Text(e.name))).toList(),
                  ),
                ],
              ),
              floatingActionButton: _mode == ToreMode.user ? FloatingActionButton(onPressed: () => Navigator.pushNamed(context, AppRoutes.scanner), child: const Icon(Icons.qr_code_scanner)) : null,
              bottomNavigationBar: _mode == ToreMode.user
                  ? NavigationBar(
                      destinations: const [
                        NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
                        NavigationDestination(icon: Icon(Icons.candlestick_chart), label: 'Ticker'),
                        NavigationDestination(icon: Icon(Icons.qr_code_scanner), label: 'Scanner'),
                        NavigationDestination(icon: Icon(Icons.show_chart), label: 'Polymarket'),
                        NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
                      ],
                      onDestinationSelected: (i) {
                        final route = [AppRoutes.home, AppRoutes.ticker, AppRoutes.scanner, AppRoutes.polymarketGlobal, AppRoutes.profile][i];
                        Navigator.pushNamed(context, route);
                      },
                    )
                  : null,
              body: ListView(padding: const EdgeInsets.all(12), children: [NetworkBanner(state: _network), HeaderCard(userSnapshot: _userSnapshot, eventContext: _eventContext), ..._moduleCards(_mode)]),
            ),
      onGenerateRoute: (settings) {
        final name = settings.name ?? '';
        if (name.startsWith('/orga') && _mode != ToreMode.orga) {
          return MaterialPageRoute(builder: (_) => const ScreenScaffold(title: 'Blocked', scopeBadges: ['GUARD'], body: BlockedStateView(title: 'Mauvais mode', message: 'Passez en mode ORGA pour ouvrir cet écran.')));
        }
        return null;
      },
    );
  }
}
