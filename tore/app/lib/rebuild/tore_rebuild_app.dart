import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum ToreMode { user, orga, bar }
enum EventState { draft, live, paused, readOnly, ended }
enum ModuleState { on, off, frozen, readOnly }
enum ScopeBadge { global, bar, event }
enum ConnectivityState { online, degraded, offline }

class ModuleDefinition {
  const ModuleDefinition({
    required this.id,
    required this.title,
    required this.mode,
    required this.scope,
    this.sensitive = false,
    this.writeAction,
    this.details = const [],
  });

  final String id;
  final String title;
  final ToreMode mode;
  final ScopeBadge scope;
  final bool sensitive;
  final String? writeAction;
  final List<String> details;
}

class UserSnapshot {
  const UserSnapshot({
    required this.roles,
    required this.capabilities,
    required this.globalModules,
    required this.syncedAt,
  });

  final Set<String> roles;
  final Set<String> capabilities;
  final Map<String, ModuleState> globalModules;
  final DateTime syncedAt;

  Map<String, dynamic> toJson() => {
        'roles': roles.toList(growable: false),
        'capabilities': capabilities.toList(growable: false),
        'globalModules': globalModules.map((k, v) => MapEntry(k, v.name)),
        'syncedAt': syncedAt.toIso8601String(),
      };

  static UserSnapshot fromJson(Map<String, dynamic> map) => UserSnapshot(
        roles: (map['roles'] as List<dynamic>).cast<String>().toSet(),
        capabilities: (map['capabilities'] as List<dynamic>).cast<String>().toSet(),
        globalModules: (map['globalModules'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ModuleState.values.byName(v as String)),
        ),
        syncedAt: DateTime.parse(map['syncedAt'] as String),
      );
}

class EventContext {
  const EventContext({
    required this.eventId,
    required this.eventState,
    required this.moduleStates,
    required this.syncedAt,
  });

  final String eventId;
  final EventState eventState;
  final Map<String, ModuleState> moduleStates;
  final DateTime syncedAt;

  Map<String, dynamic> toJson() => {
        'eventId': eventId,
        'eventState': eventState.name,
        'moduleStates': moduleStates.map((k, v) => MapEntry(k, v.name)),
        'syncedAt': syncedAt.toIso8601String(),
      };

  static EventContext fromJson(Map<String, dynamic> map) => EventContext(
        eventId: map['eventId'] as String,
        eventState: EventState.values.byName(map['eventState'] as String),
        moduleStates: (map['moduleStates'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ModuleState.values.byName(v as String)),
        ),
        syncedAt: DateTime.parse(map['syncedAt'] as String),
      );
}

class SnapshotRepository {
  static const _meKey = 'tore_rebuild_me_snapshot_v1';
  static const _eventPrefix = 'tore_rebuild_event_ctx_v1_';

  Future<UserSnapshot?> loadCachedUser() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_meKey);
    if (raw == null) return null;
    return UserSnapshot.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<EventContext?> loadCachedEvent(String eventId) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('$_eventPrefix$eventId');
    if (raw == null) return null;
    return EventContext.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> saveUser(UserSnapshot snapshot) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_meKey, jsonEncode(snapshot.toJson()));
  }

  Future<void> saveEvent(EventContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('$_eventPrefix${context.eventId}', jsonEncode(context.toJson()));
  }

  Future<UserSnapshot> fetchMeSnapshot() async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
    final snapshot = UserSnapshot(
      roles: const {'USER', 'ORGA'},
      capabilities: const {'can_access_orga', 'can_scan_qr'},
      globalModules: const {
        'user_qr_scanner': ModuleState.on,
        'user_polymarket_global': ModuleState.on,
        'bar_dashboard': ModuleState.off,
      },
      syncedAt: DateTime.now(),
    );
    await saveUser(snapshot);
    return snapshot;
  }

  Future<EventContext> fetchEventContext(String eventId, List<ModuleDefinition> defs) async {
    await Future<void>.delayed(const Duration(milliseconds: 220));
    final states = <String, ModuleState>{
      for (final d in defs) d.id: d.scope == ScopeBadge.event || d.scope == ScopeBadge.bar ? ModuleState.on : ModuleState.readOnly,
      'user_hunts': ModuleState.frozen,
      'orga_finance_admin': ModuleState.off,
      'bar_orders_live': ModuleState.on,
    };
    final context = EventContext(
      eventId: eventId,
      eventState: mapBackendStateAlias('RUNNING'),
      moduleStates: states,
      syncedAt: DateTime.now(),
    );
    await saveEvent(context);
    return context;
  }
}

EventState mapBackendStateAlias(String raw) {
  switch (raw.toUpperCase()) {
    case 'RUNNING':
    case 'LIVE':
      return EventState.live;
    case 'PAUSE':
    case 'PAUSED':
      return EventState.paused;
    case 'CLOSED':
    case 'ENDED':
      return EventState.ended;
    case 'READ_ONLY':
      return EventState.readOnly;
    default:
      return EventState.draft;
  }
}

class QrResolveResult {
  const QrResolveResult({
    required this.type,
    required this.eventId,
    this.code,
    this.message,
  });

  final String type;
  final String? eventId;
  final String? code;
  final String? message;

  bool get isError => code != null;
}

class QrResolveService {
  Future<QrResolveResult> resolve(String payload) async {
    await Future<void>.delayed(const Duration(milliseconds: 160));
    final normalized = payload.trim().toLowerCase();
    if (normalized.isEmpty || normalized == 'unknown') {
      return const QrResolveResult(type: 'error', eventId: null, code: 'qr_unknown', message: 'QR non reconnu.');
    }
    if (normalized.contains('expired')) {
      return const QrResolveResult(type: 'error', eventId: null, code: 'qr_expired', message: 'Ce QR est expiré.');
    }
    if (normalized.contains('replay')) {
      return const QrResolveResult(type: 'error', eventId: null, code: 'qr_replay', message: 'Ce QR a déjà été utilisé.');
    }
    if (normalized.contains('module_off')) {
      return const QrResolveResult(type: 'error', eventId: null, code: 'module_off', message: 'Module indisponible.');
    }
    if (normalized.contains('paused')) {
      return const QrResolveResult(type: 'error', eventId: null, code: 'event_paused', message: 'Événement temporairement en pause.');
    }
    if (normalized.contains('down')) {
      return const QrResolveResult(type: 'error', eventId: null, code: 'backend_down', message: 'Backend indisponible.');
    }
    if (normalized.contains('join')) {
      return const QrResolveResult(type: 'event_join', eventId: 'event_42');
    }
    if (normalized.contains('menu')) {
      return const QrResolveResult(type: 'event_menu', eventId: 'event_42');
    }
    return const QrResolveResult(type: 'event_hub', eventId: 'event_42');
  }
}

class IdempotencyStore {
  static const _key = 'tore_rebuild_idempotency_v1';

  Future<Map<String, String>> _loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return {};
    return (jsonDecode(raw) as Map<String, dynamic>).map((k, v) => MapEntry(k, v as String));
  }

  Future<void> _saveAll(Map<String, String> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(data));
  }

  Future<String> keyForIntent(String intent) async {
    final map = await _loadAll();
    final existing = map[intent];
    if (existing != null) return existing;
    final generated = 'idem_${DateTime.now().millisecondsSinceEpoch}_${intent.hashCode.abs()}';
    map[intent] = generated;
    await _saveAll(map);
    return generated;
  }
}

class IdempotentWriter {
  IdempotentWriter({required IdempotencyStore store}) : _store = store;

  final IdempotencyStore _store;

  Future<String> write({
    required String endpoint,
    required Map<String, dynamic> body,
    required String intent,
  }) async {
    final key = await _store.keyForIntent(intent);
    final wireBody = {...body, 'idempotency_key': key};
    await Future<void>.delayed(const Duration(milliseconds: 180));
    return 'POST $endpoint\nX-Idempotency-Key: $key\n${jsonEncode(wireBody)}';
  }
}

class ToreRebuildApp extends StatefulWidget {
  const ToreRebuildApp({super.key});

  @override
  State<ToreRebuildApp> createState() => _ToreRebuildAppState();
}

class _ToreRebuildAppState extends State<ToreRebuildApp> {
  final _repo = SnapshotRepository();
  final _qr = QrResolveService();
  late final IdempotentWriter _writer = IdempotentWriter(store: IdempotencyStore());
  late final List<ModuleDefinition> _defs = _buildDefs();

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
    final cachedMe = await _repo.loadCachedUser();
    final cachedEvent = await _repo.loadCachedEvent('event_42');
    if (cachedMe != null || cachedEvent != null) {
      setState(() {
        _userSnapshot = cachedMe;
        _eventContext = cachedEvent;
        _loading = false;
      });
    }

    if (_network == ConnectivityState.offline) {
      setState(() => _loading = false);
      return;
    }

    final me = await _repo.fetchMeSnapshot();
    final event = await _repo.fetchEventContext('event_42', _defs);
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

  bool _modeAllowed(ToreMode mode) {
    final roles = _userSnapshot?.roles ?? const <String>{};
    final caps = _userSnapshot?.capabilities ?? const <String>{};
    if (mode == ToreMode.user) return true;
    if (mode == ToreMode.orga) return roles.contains('ORGA') || caps.contains('can_access_orga');
    return roles.contains('BAR') || caps.contains('can_access_bar');
  }

  bool _isWriteAllowed(ModuleDefinition def) {
    if (_network == ConnectivityState.offline) return false;
    return _effectiveState(def.id) == ModuleState.on;
  }

  Future<void> _handleQrResolve() async {
    final ctrl = TextEditingController(text: 'join:event_42');
    QrResolveResult? result;
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
              result = await _qr.resolve(ctrl.text);
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

  Future<void> _routeResolvedQr(QrResolveResult resolved) async {
    if (resolved.isError) {
      setState(() {
        _qrLog = 'POST /qr/resolve => ${resolved.code}';
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${resolved.message} (code: ${resolved.code})')),
      );
      return;
    }

    setState(() {
      _qrLog = 'POST /qr/resolve => ${resolved.type}';
    });

    if (resolved.eventId != null) {
      if (_network != ConnectivityState.offline) {
        final context = await _repo.fetchEventContext(resolved.eventId!, _defs);
        if (!mounted) return;
        setState(() => _eventContext = context);
      } else {
        final cached = await _repo.loadCachedEvent(resolved.eventId!);
        if (!mounted) return;
        if (cached != null) {
          setState(() => _eventContext = cached);
        }
      }
    }

    String target = 'user_event_hub';
    switch (resolved.type) {
      case 'event_join':
        target = 'user_join';
        break;
      case 'event_menu':
        target = 'user_menu';
        break;
      case 'event_hub':
      default:
        target = 'user_event_hub';
        break;
    }
    _openScreen(target);
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

    final visible = _defs
        .where((d) => d.mode == _mode)
        .where((d) => _effectiveState(d.id) != ModuleState.off)
        .toList(growable: false);

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: theme,
      home: Scaffold(
        appBar: AppBar(
          title: const Text('TORÈ Night OS'),
          actions: [
            _NetworkChip(
              network: _network,
              onChanged: (value) => setState(() => _network = value),
            ),
            _ModeChip(
              mode: _mode,
              allowed: _modeAllowed,
              onChanged: (mode) => setState(() {
                _mode = mode;
                _navIndex = 0;
              }),
            ),
            IconButton(onPressed: _bootstrap, icon: const Icon(Icons.sync)),
          ],
        ),
        floatingActionButton: _mode == ToreMode.user
            ? FloatingActionButton(
                onPressed: _handleQrResolve,
                backgroundColor: const Color(0xFFF4C430),
                foregroundColor: Colors.black,
                child: const Icon(Icons.qr_code_scanner),
              )
            : null,
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
                  _NetworkBanner(state: _network),
                  _Header(userSnapshot: _userSnapshot, eventContext: _eventContext),
                  if (_qrLog.isNotEmpty) Card(child: Padding(padding: const EdgeInsets.all(10), child: Text(_qrLog))),
                  if (_writeLog.isNotEmpty)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Text(_writeLog, style: const TextStyle(fontFamily: 'monospace')),
                      ),
                    ),
                  for (final def in visible)
                    _ModuleCard(
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

    if (!_modeAllowed(def.mode)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Accès refusé: rôle/capability manquant pour ce mode.')),
      );
      return;
    }

    final state = _effectiveState(id);
    if (state == ModuleState.off) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Route bloquée: module OFF (deep-link guard actif).')),
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _ScreenView(
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
                  if (_network == ConnectivityState.offline) {
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

class SensitiveReason {
  const SensitiveReason({required this.code, required this.text});

  final String code;
  final String text;
}

class _Header extends StatelessWidget {
  const _Header({required this.userSnapshot, required this.eventContext});

  final UserSnapshot? userSnapshot;
  final EventContext? eventContext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Snapshot /me: roles=${userSnapshot?.roles.join(',') ?? '-'} | caps=${userSnapshot?.capabilities.join(',') ?? '-'}'),
            const SizedBox(height: 6),
            Text('Context /events/{id}/context: state=${eventContext?.eventState.name.toUpperCase() ?? 'DRAFT'}'),
            const SizedBox(height: 6),
            Text('Event synced: ${eventContext?.syncedAt.toIso8601String() ?? 'never'}', style: const TextStyle(fontFamily: 'monospace')),
          ],
        ),
      ),
    );
  }
}

class _ModuleCard extends StatelessWidget {
  const _ModuleCard({required this.def, required this.state, required this.onOpen});

  final ModuleDefinition def;
  final ModuleState state;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final frozen = state == ModuleState.frozen || state == ModuleState.readOnly;
    return Card(
      child: ListTile(
        title: Text(def.title),
        subtitle: Text('${def.scope.name.toUpperCase()} • ${state.name.toUpperCase()}'),
        trailing: Wrap(
          spacing: 8,
          children: [
            _Badge(label: def.scope.name.toUpperCase()),
            if (def.sensitive) const _Badge(label: 'SENSITIVE'),
          ],
        ),
        onTap: frozen ? null : onOpen,
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFFBA1733),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: const TextStyle(fontSize: 11)),
    );
  }
}

class _ScreenView extends StatelessWidget {
  const _ScreenView({required this.definition, required this.state, required this.onWrite, required this.writeAllowed});

  final ModuleDefinition definition;
  final ModuleState state;
  final bool writeAllowed;
  final Future<void> Function()? onWrite;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(definition.title)),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Wrap(
            spacing: 8,
            children: [
              _Badge(label: definition.mode.name.toUpperCase()),
              _Badge(label: definition.scope.name.toUpperCase()),
              _Badge(label: state.name.toUpperCase()),
            ],
          ),
          const SizedBox(height: 12),
          for (final line in definition.details)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('• $line'),
            ),
          if (onWrite != null)
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFFF4C430), foregroundColor: Colors.black),
              onPressed: writeAllowed ? onWrite : null,
              child: Text(writeAllowed ? (definition.writeAction ?? 'Write') : 'Write blocked (offline/readonly)'),
            ),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({required this.mode, required this.onChanged, required this.allowed});
  final ToreMode mode;
  final ValueChanged<ToreMode> onChanged;
  final bool Function(ToreMode mode) allowed;

  @override
  Widget build(BuildContext context) {
    return DropdownButton<ToreMode>(
      value: mode,
      dropdownColor: const Color(0xFF111118),
      onChanged: (value) {
        if (value != null && allowed(value)) {
          onChanged(value);
        }
      },
      items: ToreMode.values
          .where(allowed)
          .map((m) => DropdownMenuItem(value: m, child: Text(m.name.toUpperCase())))
          .toList(growable: false),
    );
  }
}

class _NetworkChip extends StatelessWidget {
  const _NetworkChip({required this.network, required this.onChanged});

  final ConnectivityState network;
  final ValueChanged<ConnectivityState> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButton<ConnectivityState>(
      value: network,
      dropdownColor: const Color(0xFF111118),
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
      items: ConnectivityState.values
          .map((n) => DropdownMenuItem(value: n, child: Text(n.name.toUpperCase())))
          .toList(growable: false),
    );
  }
}

class _NetworkBanner extends StatelessWidget {
  const _NetworkBanner({required this.state});

  final ConnectivityState state;

  @override
  Widget build(BuildContext context) {
    if (state == ConnectivityState.online) {
      return const SizedBox.shrink();
    }
    final message = state == ConnectivityState.degraded
        ? 'DEGRADED: lecture cache prioritaire, latence backend possible.'
        : 'OFFLINE: écritures bloquées, lecture via cache uniquement.';
    final color = state == ConnectivityState.degraded ? Colors.orange : Colors.red;
    return Card(
      color: color.withOpacity(0.15),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Text(message),
      ),
    );
  }
}

List<ModuleDefinition> _buildDefs() => const [
      ModuleDefinition(id: 'user_splash', title: 'Splash', mode: ToreMode.user, scope: ScopeBadge.global, details: ['Boot integrity checks', 'Session hydration']),
      ModuleDefinition(id: 'user_consent', title: 'Consent', mode: ToreMode.user, scope: ScopeBadge.global, writeAction: 'accept_consent', details: ['Legal charter signature', 'Reason capture']),
      ModuleDefinition(id: 'user_login_profile', title: 'Login/Profile', mode: ToreMode.user, scope: ScopeBadge.global, writeAction: 'upsert_profile'),
      ModuleDefinition(id: 'user_home', title: 'Home', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_qr_scanner', title: 'QR Scanner', mode: ToreMode.user, scope: ScopeBadge.global, writeAction: 'resolve_qr'),
      ModuleDefinition(id: 'user_bars', title: 'Bars', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_events', title: 'Events', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_join', title: 'Join', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'join_event'),
      ModuleDefinition(id: 'user_event_hub', title: 'Event Hub', mode: ToreMode.user, scope: ScopeBadge.event),
      ModuleDefinition(id: 'user_menu', title: 'Menu', mode: ToreMode.user, scope: ScopeBadge.event),
      ModuleDefinition(id: 'user_wallet', title: 'Wallet', mode: ToreMode.user, scope: ScopeBadge.event),
      ModuleDefinition(id: 'user_orders_lifecycle', title: 'Orders lifecycle', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'submit_order'),
      ModuleDefinition(id: 'user_ticker', title: 'Ticker', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_polymarket_global', title: 'Polymarket Global', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_polymarket_event', title: 'Polymarket Event', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'market_order', sensitive: true),
      ModuleDefinition(id: 'user_ranking', title: 'Ranking', mode: ToreMode.user, scope: ScopeBadge.event),
      ModuleDefinition(id: 'user_battles', title: 'Battles', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'battle_vote'),
      ModuleDefinition(id: 'user_hunts', title: 'Hunts', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'hunt_claim'),
      ModuleDefinition(id: 'user_wifi', title: 'WiFi', mode: ToreMode.user, scope: ScopeBadge.event),
      ModuleDefinition(id: 'user_safe_kit', title: 'Safe Kit', mode: ToreMode.user, scope: ScopeBadge.event, sensitive: true, writeAction: 'urgency_alert'),
      ModuleDefinition(id: 'user_forum', title: 'Forum', mode: ToreMode.user, scope: ScopeBadge.event, writeAction: 'post_message'),
      ModuleDefinition(id: 'user_calendar', title: 'Calendar', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'user_glossary', title: 'Glossary', mode: ToreMode.user, scope: ScopeBadge.global),
      ModuleDefinition(id: 'orga_event_control_hub', title: 'Event Control Hub', mode: ToreMode.orga, scope: ScopeBadge.event),
      ModuleDefinition(id: 'orga_entry_mode', title: 'Entry Mode', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'entry_decision', sensitive: true),
      ModuleDefinition(id: 'orga_menu_admin', title: 'Menu Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'menu_patch'),
      ModuleDefinition(id: 'orga_polymarket_admin', title: 'Polymarket Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'market_suspend', sensitive: true),
      ModuleDefinition(id: 'orga_urgency_actions', title: 'Urgency Actions', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'dispatch_urgency', sensitive: true),
      ModuleDefinition(id: 'orga_music_admin', title: 'Music Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'music_override'),
      ModuleDefinition(id: 'orga_battle_admin', title: 'Battle Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'battle_override'),
      ModuleDefinition(id: 'orga_hunt_admin', title: 'Hunt Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'hunt_override'),
      ModuleDefinition(id: 'orga_finance_admin', title: 'Finance Admin', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'finance_export', sensitive: true),
      ModuleDefinition(id: 'orga_forum_moderation', title: 'Forum moderation', mode: ToreMode.orga, scope: ScopeBadge.event, writeAction: 'moderate_forum', sensitive: true),
      ModuleDefinition(id: 'bar_dashboard', title: 'Dashboard', mode: ToreMode.bar, scope: ScopeBadge.bar),
      ModuleDefinition(id: 'bar_orders_live', title: 'Orders Live', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'order_status_update'),
      ModuleDefinition(id: 'bar_full_menu_admin', title: 'Full Menu Admin', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'bar_menu_patch'),
      ModuleDefinition(id: 'bar_zones_qr', title: 'Zones QR', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'zone_scan'),
      ModuleDefinition(id: 'bar_analytics', title: 'Analytics', mode: ToreMode.bar, scope: ScopeBadge.bar),
    ];
