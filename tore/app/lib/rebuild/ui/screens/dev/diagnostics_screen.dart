import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../models/event_context.dart';
import '../../../models/rebuild_types.dart';
import '../../../models/snapshot.dart';
import '../../../services/api_client.dart';
import '../../../services/cache_store.dart';
import '../../../services/client_log.dart';
import '../../../services/idempotency_store.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class DiagnosticsScreen extends StatefulWidget {
  const DiagnosticsScreen({
    super.key,
    required this.mode,
    required this.snapshot,
    required this.eventContext,
    required this.networkState,
    required this.networkTransitionAt,
    required this.apiClient,
    required this.cacheStore,
    required this.idempotencyStore,
    required this.onSimulatedNetworkChanged,
  });

  final ToreMode mode;
  final UserSnapshot? snapshot;
  final EventContext? eventContext;
  final ConnectivityState networkState;
  final DateTime networkTransitionAt;
  final ApiClient apiClient;
  final CacheStore cacheStore;
  final IdempotencyStore idempotencyStore;
  final ValueChanged<ConnectivityState> onSimulatedNetworkChanged;

  @override
  State<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends State<DiagnosticsScreen> {
  String _filter = '';
  Map<String, Duration?> _cache = const {};
  IdempotencyStats _idStats = const IdempotencyStats(count: 0);

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final cache = await widget.cacheStore.cacheStatusSummary();
    final idStats = await widget.idempotencyStore.stats();
    if (mounted) {
      setState(() {
        _cache = cache;
        _idStats = idStats;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final logs = ClientLog.instance.entries(filter: _filter.isEmpty ? null : _filter);
    final chips = {'', ...ClientLog.instance.eventTypes.toList()};
    final event = widget.eventContext;
    final writeAllowed = event != null ? event.eventState == EventState.live && widget.networkState != ConnectivityState.offline : false;

    return ScreenScaffold(
      title: 'Diagnostics',
      scopeBadges: const ['DEV'],
      body: ListView(
        shrinkWrap: true,
        children: [
          _section('Build', [
            _line('Flavor', kReleaseMode ? 'release' : 'dev'),
            _line('Version', const String.fromEnvironment('APP_VERSION', defaultValue: 'dev-build')),
            _line('Mode', widget.mode.name.toUpperCase()),
          ]),
          _section('Snapshot', [
            _line('Roles', widget.snapshot?.roles.join(', ') ?? '-'),
            _line('Capabilities', widget.snapshot?.capabilities.join(', ') ?? '-'),
          ]),
          _section('Event context', [
            _line('event_id', event?.eventId ?? 'none'),
            _line('event_state', event?.eventState.name ?? 'none'),
            _line('write_allowed', writeAllowed ? 'yes' : 'blocked by network/event'),
          ]),
          _section('Network', [
            _line('state', widget.networkState.name.toUpperCase()),
            _line('last_transition', widget.networkTransitionAt.toIso8601String()),
          ]),
          _section('Cache status (minutes)', _cache.entries.map((e) => _line(e.key, e.value == null ? 'missing' : '${e.value!.inMinutes}m')).toList()),
          _section(
            'API stats',
            [
              ...widget.apiClient.recentRequests().map((r) => _line('${r.method} ${r.path}', '${r.status} / ${r.latencyMs}ms')),
              _line('errors', widget.apiClient.recentErrorCodes().join(', ')),
            ],
          ),
          _section('Idempotency', [
            _line('entries', '${_idStats.count}'),
            _line('latest', '${_idStats.latestIntent ?? '-'} -> ${_idStats.latestKey ?? '-'}'),
          ]),
          Wrap(spacing: 6, children: chips.map((e) => ChoiceChip(label: Text(e.isEmpty ? 'all logs' : e), selected: _filter == e, onSelected: (_) => setState(() => _filter = e))).toList()),
          const SizedBox(height: ToreTokens.s8),
          ...logs.take(80).map((e) => ListTile(title: Text(e.event), subtitle: Text('${e.ts.toIso8601String()}\n${scrubJsonMap(e.fields)}'))),
          const SizedBox(height: ToreTokens.s8),
          FilledButton(onPressed: _copyBlob, child: const Text('Copy diagnostics to clipboard')),
          if (!kReleaseMode) ...[
            OutlinedButton(onPressed: _clearCaches, child: const Text('Clear caches')),
            OutlinedButton(onPressed: _clearIdempotency, child: const Text('Clear idempotency store')),
            DropdownButton<ConnectivityState>(
              value: widget.networkState,
              items: ConnectivityState.values.map((e) => DropdownMenuItem(value: e, child: Text('Simulate ${e.name}'))).toList(),
              onChanged: (v) {
                if (v != null) widget.onSimulatedNetworkChanged(v);
              },
            ),
          ],
        ],
      ),
    );
  }

  Widget _section(String title, List<Widget> children) => Card(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height: ToreTokens.s6), ...children]),
        ),
      );

  Widget _line(String k, String v) => Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('$k: $v'));

  Future<void> _copyBlob() async {
    final scrubbedEvent = widget.eventContext?.eventId == null ? 'none' : scrubJsonMap({'user_id': widget.eventContext!.eventId})['user_id'];
    final blob = StringBuffer()
      ..writeln('mode=${widget.mode.name}')
      ..writeln('network=${widget.networkState.name}')
      ..writeln('event=$scrubbedEvent')
      ..writeln('roles=${widget.snapshot?.roles.join(',') ?? '-'}')
      ..writeln('cache=${scrubJsonMap(_cache.map((key, value) => MapEntry(key, value?.inMinutes.toString() ?? 'missing')))}')
      ..writeln('errors=${widget.apiClient.recentErrorCodes()}')
      ..writeln('logs=${logsBlob()}');
    await Clipboard.setData(ClipboardData(text: blob.toString()));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Diagnostics copied.')));
  }


  String logsBlob() {
    final logs = ClientLog.instance.entries(filter: _filter.isEmpty ? null : _filter).take(50);
    final lines = logs.map((entry) => '${entry.ts.toIso8601String()} ${entry.event} ${scrubJsonMap(entry.fields)}');
    return lines.join(' | ');
  }

  Future<void> _clearCaches() async {
    final ok = await _confirm('Clear caches?');
    if (!ok) return;
    await widget.cacheStore.clearDomainCaches();
    await _refresh();
  }

  Future<void> _clearIdempotency() async {
    final ok = await _confirm('Clear idempotency store?');
    if (!ok) return;
    await widget.idempotencyStore.clear();
    await _refresh();
  }

  Future<bool> _confirm(String text) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Confirm'),
        content: Text(text),
        actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Confirm'))],
      ),
    );
    return result == true;
  }
}
