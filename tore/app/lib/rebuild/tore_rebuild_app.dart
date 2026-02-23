import 'package:flutter/material.dart';

import 'models/event_context.dart';
import 'models/backend_models.dart';
import 'models/qr_resolve.dart';
import 'models/rebuild_types.dart';
import 'models/snapshot.dart';
import 'routing/app_routes.dart';
import 'routing/qr_router.dart';
import 'routing/route_guards.dart';
import 'services/api_client.dart';
import 'services/cache_store.dart';
import 'services/client_log.dart';
import 'services/idempotency_store.dart';
import 'services/network_state_resolver.dart';
import 'ui/module_catalog.dart';
import 'ui/screens/bar/bar_screens.dart';
import 'ui/screens/dev/diagnostics_screen.dart';
import 'ui/screens/help/runbook_screens.dart';
import 'ui/screens/orga/orga_exports_screen.dart';
import 'ui/screens/orga/orga_screens.dart';
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
  final _networkStateResolver = NetworkStateResolver();
  late final IdempotencyStore _writerStore = IdempotencyStore(persistence: SharedPrefsIdempotencyPersistence());
  late final IdempotentWriter _writer = IdempotentWriter(store: _writerStore);
  late final List<ModuleDefinition> _defs = buildModuleDefinitions();

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

  @override
  void initState() {
    super.initState();
    ClientLog.instance.hydrate();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    setState(() => _loading = true);
    final cachedMe = await _cache.loadCachedUser();
    final cachedEvent = await _cache.loadCachedEvent('event_42');
    _userSnapshot = cachedMe;
    _eventContext = cachedEvent;

    if (_networkStateResolver.canReadRemote(_network)) {
      _userSnapshot = await _api.fetchMeSnapshot();
      _eventContext = await _api.fetchEventContext('event_42', _defs);
      await _cache.saveUser(_userSnapshot!);
      await _cache.saveEvent(_eventContext!);
      await _loadDomainData();
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadDomainData() async {
    _bars = await _api.fetchBars(network: _network);
    _barEvents = await _api.fetchBarEvents('1', network: _network);
    _menuItems = await _api.fetchMenu(eventId: '42', network: _network);
    _wallet = await _api.fetchWallet(eventId: '42', network: _network);
    _ticker = (await _api.fetchTicker('42', network: _network)).items;
    _polyGlobal = await _api.fetchPolymarketGlobal(network: _network);
    _polyEvent = await _api.fetchPolymarketEvent('42', network: _network);
    _entryStats = await _api.fetchEntryStats('42', network: _network);
    _orders = (await _api.fetchOrdersLive('42', network: _network)).items;
    _zones = await _api.fetchZones('1', network: _network);
    _orgaQrPack = await _api.fetchOrgaQrPack(_eventContext?.eventId ?? '42', network: _network);
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

  bool _writeAllowed(String moduleId) => _networkStateResolver.canWrite(_network) && _effectiveState(moduleId) == ModuleState.on;

  Future<void> _resolveQrPayload(String payload) async {
    final resolved = await _api.resolveQr(payload);
    if (resolved.isError || !mounted) {
      if (!mounted) return;
      final err = mapQrReasonToError(resolved.reason);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err.message)));
      return;
    }
    final route = _router.targetFor(resolved);
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


  void _openDiagnostics() {
    Navigator.pushNamed(context, AppRoutes.devDiagnostics);
  }
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.build(),
      initialRoute: AppRoutes.boot,
      routes: {
        AppRoutes.boot: (_) => _loading ? BootSplashScreen(network: _network, onLongPressDiagnostics: _openDiagnostics) : ConsentCharterScreen(onAccept: () => setState(() => _consented = true)),
        AppRoutes.home: (_) => HomeHubScreen(network: _network, cards: [HeaderCard(userSnapshot: _userSnapshot, eventContext: _eventContext), ..._moduleCards(ToreMode.user)]),
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
        AppRoutes.profile: (_) => ProfileSettingsScreen(network: _network, onOpenDiagnostics: _openDiagnostics, onOpenHelp: () => Navigator.pushNamed(context, AppRoutes.userHelp)),
        AppRoutes.orgaHub: (_) => OrgaEventControlHubScreen(network: _network, writeAllowed: _writeAllowed('orga_event_control_hub'), entryApprovedCount: _entryStats?.approvedCount ?? 0, onOpenExports: () => Navigator.pushNamed(context, AppRoutes.orgaExports), onOpenRunbook: () => Navigator.pushNamed(context, AppRoutes.orgaRunbook)),
        AppRoutes.orgaEntry: (_) => EntryStaffScreen(network: _network),
        AppRoutes.orgaMenu: (_) => OrgaMenuAdminScreen(network: _network),
        AppRoutes.orgaMarket: (_) => OrgaPolymarketAdminScreen(network: _network, onSensitive: (a) => _sensitiveWrite('orga_polymarket_admin', a)),
        AppRoutes.orgaUrgency: (_) => OrgaUrgencyActionsScreen(network: _network, onSensitive: (a) => _sensitiveWrite('orga_urgency_actions', a)),
        AppRoutes.userHelp: (_) => RunbookScreen(onOpenUrgency: () => Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaRunbook: (_) => RunbookScreen(onOpenUrgency: () => Navigator.pushNamed(context, AppRoutes.orgaUrgency)),
        AppRoutes.orgaExports: (_) => OrgaExportsScreen(eventId: _eventContext?.eventId ?? '42', moduleStates: _eventContext?.moduleStates ?? const {}, backendPack: _orgaQrPack),
        AppRoutes.devDiagnostics: (_) => DiagnosticsScreen(mode: _mode, snapshot: _userSnapshot, eventContext: _eventContext, networkState: _network, networkTransitionAt: _networkTransitionAt, apiClient: _api, cacheStore: _cache, idempotencyStore: _writerStore, onSimulatedNetworkChanged: (state) => setState(() { _network = state; _networkTransitionAt = DateTime.now(); })),
        AppRoutes.barDashboard: (_) => BarDashboardScreen(network: _network),
        AppRoutes.barOrders: (_) => OrdersLiveScreen(network: _network, rows: _orders.map((o) => ListTile(title: Text('Order ${o.id}'), trailing: Text(o.status))).toList()),
        AppRoutes.barMenu: (_) => FullMenuAdminScreen(network: _network),
        AppRoutes.barZones: (_) => ZonesQrAdminScreen(network: _network, zones: _zones.map((z) => z.name).toList()),
        AppRoutes.barAnalytics: (_) => AnalyticsScreen(network: _network),
        AppRoutes.blocked: (_) => const ScreenScaffold(title: 'Blocked', scopeBadges: ['GUARD'], body: BlockedStateView(title: 'Accès indisponible', message: 'Ce module est OFF, en pause ou non autorisé pour votre mode actuel.')),
      },
      home: !_consented || _loading
          ? (_loading ? BootSplashScreen(network: _network, onLongPressDiagnostics: _openDiagnostics) : ConsentCharterScreen(onAccept: () => setState(() => _consented = true)))
          : Scaffold(
              appBar: AppBar(
                title: const Text('TORÈ Night OS'),
                actions: [
                  DropdownButton<ConnectivityState>(
                    value: _network,
                    onChanged: (v) => setState(() { _network = v ?? _network; _networkTransitionAt = DateTime.now(); }),
                    items: ConnectivityState.values.map((e) => DropdownMenuItem(value: e, child: Text(e.name))).toList(),
                  ),
                  DropdownButton<ToreMode>(
                    value: _mode,
                    onChanged: (v) => setState(() => _mode = v ?? _mode),
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
