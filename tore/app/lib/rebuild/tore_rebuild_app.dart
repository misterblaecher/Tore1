import 'package:flutter/material.dart';

import 'models/event_context.dart';
import 'models/qr_resolve.dart';
import 'models/rebuild_types.dart';
import 'models/snapshot.dart';
import 'routing/app_routes.dart';
import 'routing/qr_router.dart';
import 'routing/route_guards.dart';
import 'services/api_client.dart';
import 'services/cache_store.dart';
import 'services/idempotency_store.dart';
import 'services/network_state_resolver.dart';
import 'ui/module_catalog.dart';
import 'ui/screens/bar/bar_screens.dart';
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
  late final IdempotentWriter _writer = IdempotentWriter(store: IdempotencyStore(persistence: SharedPrefsIdempotencyPersistence()));
  late final List<ModuleDefinition> _defs = buildModuleDefinitions();

  ToreMode _mode = ToreMode.user;
  UserSnapshot? _userSnapshot;
  EventContext? _eventContext;
  ConnectivityState _network = ConnectivityState.online;
  bool _loading = true;
  bool _consented = false;

  @override
  void initState() {
    super.initState();
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
    }
    if (mounted) setState(() => _loading = false);
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
      'bar_dashboard': AppRoutes.barDashboard,
      'bar_orders_live': AppRoutes.barOrders,
      'bar_full_menu_admin': AppRoutes.barMenu,
      'bar_zones_qr': AppRoutes.barZones,
      'bar_analytics': AppRoutes.barAnalytics,
    };
    return map[moduleId];
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.build(),
      initialRoute: AppRoutes.boot,
      routes: {
        AppRoutes.boot: (_) => _loading ? BootSplashScreen(network: _network) : ConsentCharterScreen(onAccept: () => setState(() => _consented = true)),
        AppRoutes.home: (_) => HomeHubScreen(network: _network, cards: [HeaderCard(userSnapshot: _userSnapshot, eventContext: _eventContext), ..._moduleCards(ToreMode.user)]),
        AppRoutes.scanner: (_) => QrScannerScreen(onResolve: _resolveQrPayload),
        AppRoutes.bars: (_) => BarsScreen(network: _network, children: _moduleCards(ToreMode.user)),
        AppRoutes.events: (_) => BarEventsScreen(children: _moduleCards(ToreMode.user)),
        AppRoutes.join: (_) => JoinEventScreen(writeAllowed: _writeAllowed('user_join'), onJoin: () => _sensitiveWrite('user_join', 'join_event')),
        AppRoutes.eventHub: (_) => EventHubScreen(network: _network, modules: _moduleCards(ToreMode.user)),
        AppRoutes.menu: (_) => MenuScreen(network: _network, items: [for (var i = 0; i < 6; i++) const ListTile(title: Text('Drink'), trailing: Text('9.50', style: TextStyle(fontFamily: 'monospace')))]),
        AppRoutes.wallet: (_) => WalletScreen(rows: [for (var i = 0; i < 5; i++) ListTile(title: Text('TX $i'), trailing: const Text('-5.00', style: TextStyle(fontFamily: 'monospace')))]),
        AppRoutes.ticker: (_) => TickerScreen(rows: [for (var i = 0; i < 7; i++) ListTile(title: Text('Feed item $i'))]),
        AppRoutes.polymarketGlobal: (_) => PolymarketGlobalScreen(rows: [for (var i = 0; i < 4; i++) ListTile(title: Text('Market #$i'))]),
        AppRoutes.polymarketEvent: (_) => PolymarketEventScreen(rows: [for (var i = 0; i < 4; i++) ListTile(title: Text('Event market #$i'))]),
        AppRoutes.profile: (_) => const ProfileSettingsScreen(),
        AppRoutes.orgaHub: (_) => const OrgaEventControlHubScreen(),
        AppRoutes.orgaEntry: (_) => const EntryStaffScreen(),
        AppRoutes.orgaMenu: (_) => const OrgaMenuAdminScreen(),
        AppRoutes.orgaMarket: (_) => OrgaPolymarketAdminScreen(onSensitive: (a) => _sensitiveWrite('orga_polymarket_admin', a)),
        AppRoutes.orgaUrgency: (_) => OrgaUrgencyActionsScreen(onSensitive: (a) => _sensitiveWrite('orga_urgency_actions', a)),
        AppRoutes.barDashboard: (_) => const BarDashboardScreen(),
        AppRoutes.barOrders: (_) => const OrdersLiveScreen(),
        AppRoutes.barMenu: (_) => const FullMenuAdminScreen(),
        AppRoutes.barZones: (_) => const ZonesQrAdminScreen(),
        AppRoutes.barAnalytics: (_) => const AnalyticsScreen(),
        AppRoutes.blocked: (_) => const Scaffold(body: Center(child: Text('Route blocked: module OFF or unauthorized mode'))),
      },
      home: !_consented || _loading
          ? (_loading ? BootSplashScreen(network: _network) : ConsentCharterScreen(onAccept: () => setState(() => _consented = true)))
          : Scaffold(
              appBar: AppBar(
                title: const Text('TORÈ Night OS'),
                actions: [
                  DropdownButton<ConnectivityState>(
                    value: _network,
                    onChanged: (v) => setState(() => _network = v ?? _network),
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
          return MaterialPageRoute(builder: (_) => const Scaffold(body: Center(child: Text('Blocked by mode guard'))));
        }
        return null;
      },
    );
  }
}
