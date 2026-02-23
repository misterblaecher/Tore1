import 'package:flutter/material.dart';

import 'models/event_context.dart';
import 'models/qr_resolve.dart';
import 'models/rebuild_types.dart';
import 'models/snapshot.dart';
import 'routing/qr_router.dart';
import 'routing/route_guards.dart';
import 'services/api_client.dart';
import 'services/cache_store.dart';
import 'services/idempotency_store.dart';
import 'services/network_state_resolver.dart';
import 'ui/module_catalog.dart';
import 'ui/screens/screen_view.dart';
import 'ui/widgets/common_widgets.dart';

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
  late final IdempotentWriter _writer = IdempotentWriter(
    store: IdempotencyStore(persistence: SharedPrefsIdempotencyPersistence()),
  );
  late final List<ModuleDefinition> _defs = buildModuleDefinitions();

  ToreMode _mode = ToreMode.user;
  UserSnapshot? _userSnapshot;
  EventContext? _eventContext;
  ConnectivityState _network = ConnectivityState.online;
  bool _loading = true;
  int _navIndex = 0;
  String _writeLog = '';
  String _qrLog = '';

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final cachedMe = await _cache.loadCachedUser();
    final cachedEvent = await _cache.loadCachedEvent('event_42');
    if (cachedMe != null || cachedEvent != null) {
      setState(() {
        _userSnapshot = cachedMe;
        _eventContext = cachedEvent;
        _loading = false;
      });
    }

    if (!_networkStateResolver.canReadRemote(_network)) {
      setState(() => _loading = false);
      return;
    }

    final me = await _api.fetchMeSnapshot();
    final event = await _api.fetchEventContext('event_42', _defs);
    await _cache.saveUser(me);
    await _cache.saveEvent(event);
    setState(() {
      _userSnapshot = me;
      _eventContext = event;
      _loading = false;
    });
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

  bool _isWriteAllowed(ModuleDefinition def) {
    if (!_networkStateResolver.canWrite(_network)) return false;
    return _effectiveState(def.id) == ModuleState.on;
  }

  Future<void> _handleQrResolve() async {
    final ctrl = TextEditingController(text: 'join:event_42');
    QrResolve? result;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Scanner QR'),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(labelText: 'Payload brut du QR'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          FilledButton(
            onPressed: () async {
              result = await _api.resolveQr(ctrl.text);
              if (!mounted) return;
              Navigator.pop(ctx);
            },
            child: const Text('Résoudre'),
          ),
        ],
      ),
    );
    if (result == null || !mounted) return;
    await _routeResolvedQr(result!);
  }

  Future<void> _routeResolvedQr(QrResolve resolved) async {
    if (resolved.isError) {
      final err = mapQrReasonToError(resolved.reason);
      setState(() {
        _qrLog = 'POST /qr/resolve => ${err.code}';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${err.message} (code: ${err.code})')),
      );
      return;
    }

    setState(() {
      _qrLog = 'POST /qr/resolve => ${resolved.type}';
    });

    if (resolved.eventId != null) {
      final targetId = 'event_${resolved.eventId}';
      if (_networkStateResolver.canReadRemote(_network)) {
        final context = await _api.fetchEventContext(targetId, _defs);
        await _cache.saveEvent(context);
        if (!mounted) return;
        setState(() => _eventContext = context);
      } else {
        final cached = await _cache.loadCachedEvent(targetId);
        if (!mounted) return;
        if (cached != null) {
          setState(() => _eventContext = cached);
        }
      }
    }

    _openScreen(_router.targetFor(resolved));
  }

  @override
  Widget build(BuildContext context) {
    final theme = ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: const Color(0xFF050506),
      colorScheme: const ColorScheme.dark(
        primary: Color(0xFFBA1733),
        secondary: Color(0xFFF4C430),
        surface: Color(0xFF111118),
      ),
      cardTheme: const CardThemeData(color: Color(0xFF121218)),
    );

    final visible = _defs.where((d) => d.mode == _mode).where((d) => _effectiveState(d.id) != ModuleState.off).toList(growable: false);

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: theme,
      home: Scaffold(
        appBar: AppBar(
          title: const Text('TORÈ Night OS'),
          actions: [
            NetworkChip(network: _network, onChanged: (value) => setState(() => _network = value)),
            ModeChip(
              mode: _mode,
              allowed: (mode) => _guards.modeAllowed(mode, _userSnapshot),
              onChanged: (mode) => setState(() {
                _mode = mode;
                _navIndex = 0;
              }),
            ),
            IconButton(onPressed: _bootstrap, icon: const Icon(Icons.sync)),
            if (_mode == ToreMode.user)
              IconButton(
                onPressed: _handleQrResolve,
                tooltip: 'Résoudre QR',
                icon: const Icon(Icons.qr_code_scanner),
              )
          ],
        ),
        bottomNavigationBar: _mode == ToreMode.user
            ? NavigationBar(
                selectedIndex: _navIndex,
                onDestinationSelected: (i) => setState(() => _navIndex = i),
                destinations: const [
                  NavigationDestination(icon: Icon(Icons.home), label: 'Home'),
                  NavigationDestination(icon: Icon(Icons.candlestick_chart), label: 'Ticker'),
                  NavigationDestination(icon: Icon(Icons.qr_code), label: 'Scanner'),
                  NavigationDestination(icon: Icon(Icons.show_chart), label: 'Polymarket'),
                  NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
                ],
              )
            : null,
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  NetworkBanner(state: _network),
                  HeaderCard(userSnapshot: _userSnapshot, eventContext: _eventContext),
                  if (_qrLog.isNotEmpty) Card(child: Padding(padding: const EdgeInsets.all(10), child: Text(_qrLog))),
                  if (_writeLog.isNotEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Text(_writeLog, style: const TextStyle(fontFamily: 'monospace')),
                      ),
                    ),
                  for (final def in visible)
                    ModuleCard(
                      def: def,
                      state: _effectiveState(def.id),
                      onOpen: () => _openScreen(def.id),
                    ),
                ],
              ),
      ),
    );
  }

  void _openScreen(String id) {
    final def = _defs.firstWhere((e) => e.id == id);

    if (!_guards.modeAllowed(def.mode, _userSnapshot)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Accès refusé: rôle/capability manquant pour ce mode.')),
      );
      return;
    }

    final state = _effectiveState(id);
    if (!_guards.deepLinkAllowed(state)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Route bloquée: module OFF (deep-link guard actif).')),
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ScreenView(
          definition: def,
          state: state,
          writeAllowed: _isWriteAllowed(def),
          onWrite: def.writeAction == null
              ? null
              : () async {
                  SensitiveReason? reason;
                  if (def.sensitive) {
                    reason = await _confirmSensitive();
                    if (reason == null) return;
                  }
                  if (!_networkStateResolver.canWrite(_network)) {
                    if (!mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Écriture bloquée offline. Repassez ONLINE/DEGRADED pour envoyer.')),
                    );
                    return;
                  }
                  final endpoint = '/v1/${def.id}/write';
                  final intent = '$endpoint:${def.writeAction}:${_eventContext?.eventId ?? 'global'}';
                  final log = await _writer.write(
                    endpoint: endpoint,
                    intent: intent,
                    body: {
                      'mode': _mode.name,
                      'scope': def.scope.name,
                      'action': def.writeAction,
                      if (reason != null) 'reason_code': reason.code,
                      if (reason != null) 'reason_text': reason.text,
                    },
                  );
                  if (!mounted) return;
                  setState(() => _writeLog = log);
                },
        ),
      ),
    );
  }

  Future<SensitiveReason?> _confirmSensitive() async {
    final reasonCode = TextEditingController();
    final reasonText = TextEditingController();
    SensitiveReason? value;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmation sensible obligatoire'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: reasonCode,
              decoration: const InputDecoration(labelText: 'reason_code (obligatoire)'),
            ),
            TextField(
              controller: reasonText,
              decoration: const InputDecoration(labelText: 'reason_text (obligatoire)'),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              if (reasonCode.text.trim().isEmpty || reasonText.text.trim().isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Blocage sécurité: reason_code + reason_text sont requis.')),
                );
                return;
              }
              value = SensitiveReason(code: reasonCode.text.trim(), text: reasonText.text.trim());
              Navigator.pop(ctx);
            },
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    return value;
  }
}
