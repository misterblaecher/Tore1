import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

enum ToreMode { user, orga, bar }
enum EventState { draft, live, freeze, readOnly, closed }
enum ModuleState { on, off, frozen, readOnly }
enum ScopeBadge { global, bar, event }

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

class ServerSnapshot {
  const ServerSnapshot({
    required this.eventState,
    required this.moduleStates,
    required this.syncedAt,
  });

  final EventState eventState;
  final Map<String, ModuleState> moduleStates;
  final DateTime syncedAt;

  Map<String, dynamic> toJson() => {
        'eventState': eventState.name,
        'syncedAt': syncedAt.toIso8601String(),
        'moduleStates': moduleStates.map((k, v) => MapEntry(k, v.name)),
      };

  static ServerSnapshot fromJson(Map<String, dynamic> map) => ServerSnapshot(
        eventState: EventState.values.byName(map['eventState'] as String),
        syncedAt: DateTime.parse(map['syncedAt'] as String),
        moduleStates: (map['moduleStates'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ModuleState.values.byName(v as String)),
        ),
      );
}

class SnapshotRepository {
  static const _key = 'tore_rebuild_snapshot_v1';

  Future<ServerSnapshot?> loadCached() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return null;
    return ServerSnapshot.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> save(ServerSnapshot snapshot) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(snapshot.toJson()));
  }

  Future<ServerSnapshot> refreshFromServer(List<ModuleDefinition> defs) async {
    await Future<void>.delayed(const Duration(milliseconds: 420));
    final states = <String, ModuleState>{
      for (final d in defs)
        d.id: d.mode == ToreMode.user && d.scope == ScopeBadge.event
            ? ModuleState.on
            : ModuleState.readOnly,
    };
    states['user_forum'] = ModuleState.on;
    states['user_hunts'] = ModuleState.frozen;
    states['orga_urgency_actions'] = ModuleState.on;
    states['bar_orders_live'] = ModuleState.on;
    final snapshot = ServerSnapshot(
      eventState: EventState.live,
      moduleStates: states,
      syncedAt: DateTime.now(),
    );
    await save(snapshot);
    return snapshot;
  }
}

class IdempotentWriter {
  int _nonce = 0;

  Future<String> write({required String endpoint, required Map<String, dynamic> body}) async {
    _nonce += 1;
    final key = '${DateTime.now().millisecondsSinceEpoch}-$_nonce';
    final wireBody = {...body, 'idempotency_key': key};
    await Future<void>.delayed(const Duration(milliseconds: 260));
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
  final _writer = IdempotentWriter();
  late final List<ModuleDefinition> _defs = _buildDefs();

  ToreMode _mode = ToreMode.user;
  ServerSnapshot? _snapshot;
  bool _loading = true;
  int _navIndex = 0;
  String _writeLog = '';

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final cached = await _repo.loadCached();
    if (cached != null) {
      setState(() {
        _snapshot = cached;
        _loading = false;
      });
    }
    final fresh = await _repo.refreshFromServer(_defs);
    setState(() {
      _snapshot = fresh;
      _loading = false;
    });
  }

  ModuleState _effectiveState(String id) {
    final base = _snapshot?.moduleStates[id] ?? ModuleState.off;
    final event = _snapshot?.eventState ?? EventState.draft;
    if (base == ModuleState.off) return ModuleState.off;
    if (event == EventState.freeze && base == ModuleState.on) return ModuleState.frozen;
    if (event == EventState.readOnly || event == EventState.closed) return ModuleState.readOnly;
    return base;
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
            _ModeChip(
              mode: _mode,
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
                onPressed: () => _openScreen('user_qr_scanner'),
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
                  _Header(snapshot: _snapshot),
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
    final state = _effectiveState(id);
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _ScreenView(
          definition: def,
          state: state,
          onWrite: def.writeAction == null
              ? null
              : () async {
                  if (def.sensitive) {
                    final ok = await _confirmSensitive();
                    if (!ok) return;
                  }
                  final log = await _writer.write(
                    endpoint: '/v1/${def.id}/write',
                    body: {'mode': _mode.name, 'scope': def.scope.name, 'action': def.writeAction},
                  );
                  if (!mounted) return;
                  setState(() => _writeLog = log);
                },
        ),
      ),
    );
  }

  Future<bool> _confirmSensitive() async {
    final ctrl = TextEditingController();
    var accepted = false;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Strong confirmation required'),
        content: TextField(
          controller: ctrl,
          decoration: const InputDecoration(labelText: 'Type CONFIRM'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              accepted = ctrl.text.trim().toUpperCase() == 'CONFIRM';
              Navigator.pop(ctx);
            },
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
    return accepted;
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.snapshot});

  final ServerSnapshot? snapshot;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Server authoritative event state: ${snapshot?.eventState.name.toUpperCase() ?? 'DRAFT'}'),
            const SizedBox(height: 6),
            Text(
              'Offline-first cache sync: ${snapshot?.syncedAt.toIso8601String() ?? 'never'}',
              style: const TextStyle(fontFamily: 'monospace'),
            ),
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
  const _ScreenView({required this.definition, required this.state, required this.onWrite});

  final ModuleDefinition definition;
  final ModuleState state;
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
          if (onWrite != null && state == ModuleState.on)
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFFF4C430), foregroundColor: Colors.black),
              onPressed: onWrite,
              child: Text(definition.writeAction ?? 'Write'),
            ),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({required this.mode, required this.onChanged});
  final ToreMode mode;
  final ValueChanged<ToreMode> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButton<ToreMode>(
      value: mode,
      dropdownColor: const Color(0xFF111118),
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
      items: ToreMode.values
          .map((m) => DropdownMenuItem(value: m, child: Text(m.name.toUpperCase())))
          .toList(growable: false),
    );
  }
}

List<ModuleDefinition> _buildDefs() => const [
      // USER
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

      // ORGA
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

      // BAR
      ModuleDefinition(id: 'bar_dashboard', title: 'Dashboard', mode: ToreMode.bar, scope: ScopeBadge.bar),
      ModuleDefinition(id: 'bar_orders_live', title: 'Orders Live', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'order_status_update'),
      ModuleDefinition(id: 'bar_full_menu_admin', title: 'Full Menu Admin', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'bar_menu_patch'),
      ModuleDefinition(id: 'bar_zones_qr', title: 'Zones QR', mode: ToreMode.bar, scope: ScopeBadge.bar, writeAction: 'zone_scan'),
      ModuleDefinition(id: 'bar_analytics', title: 'Analytics', mode: ToreMode.bar, scope: ScopeBadge.bar),
    ];
