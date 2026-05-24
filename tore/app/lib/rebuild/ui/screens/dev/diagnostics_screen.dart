import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../config/app_environment.dart';
import '../../../models/event_context.dart';
import '../../../models/rebuild_types.dart';
import '../../../models/snapshot.dart';
import '../../../services/api_client.dart';
import '../../../services/cache_store.dart';
import '../../../services/client_log.dart';
import '../../../services/idempotency_store.dart';
import '../../../services/remote_config.dart';
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
    required this.environment,
    required this.environmentColor,
    required this.buildInfo,
    required this.remoteConfig,
    required this.onSimulatedNetworkChanged,
    required this.onOpenUrl,
  });

  final ToreMode mode;
  final UserSnapshot? snapshot;
  final EventContext? eventContext;
  final ConnectivityState networkState;
  final DateTime networkTransitionAt;
  final ApiClient apiClient;
  final CacheStore cacheStore;
  final IdempotencyStore idempotencyStore;
  final AppEnvironment environment;
  final Color environmentColor;
  final BuildInfo buildInfo;
  final RemoteConfigPayload remoteConfig;
  final ValueChanged<ConnectivityState> onSimulatedNetworkChanged;
  final Future<void> Function(String url) onOpenUrl;

  @override
  State<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends State<DiagnosticsScreen> {
  String _filter = '';
  final _urlController = TextEditingController();
  Map<String, Duration?> _cache = const {};
  IdempotencyStats _idStats = const IdempotencyStats(count: 0);

  @override
  void initState() {
    super.initState();
    _urlController.text =
        'tore://event/${widget.eventContext?.eventId ?? 'event_42'}';
    _refresh();
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
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
    final logs =
        ClientLog.instance.entries(filter: _filter.isEmpty ? null : _filter);
    final chips = {'', ...ClientLog.instance.eventTypes};
    final event = widget.eventContext;
    final writeAllowed = event != null
        ? event.eventState.isLive &&
            widget.networkState != ConnectivityState.offline
        : false;

    return ScreenScaffold(
      title: 'Diagnostics',
      scopeBadges: ['DEV', appEnvironmentLabel(widget.environment)],
      body: ListView(
        shrinkWrap: true,
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Environment'),
            subtitle: Text(
                'Current channel: ${appEnvironmentLabel(widget.environment)}'),
            trailing: ToreBadge(
                label: appEnvironmentLabel(widget.environment),
                color: widget.environmentColor),
          ),
          _section('Build info', [
            _line('Flavor', kReleaseMode ? 'release' : 'dev'),
            _line('Version', widget.buildInfo.semver),
            _line('Build number', '${widget.buildInfo.buildNumber}'),
            _line('Git SHA', widget.buildInfo.gitSha),
            _line('Build time', widget.buildInfo.buildTime),
            _line('Mode', widget.mode.name.toUpperCase()),
          ]),
          _section('Remote config', [
            _line('source', widget.remoteConfig.source),
            _line('disable_writes_global',
                widget.remoteConfig.disableWritesGlobal ? 'true' : 'false'),
            _line('diagnostics_enabled',
                widget.remoteConfig.diagnosticsEnabled ? 'true' : 'false'),
            _line('min_supported_build',
                '${widget.remoteConfig.minSupportedBuild ?? '-'}'),
            _line('min_supported_version',
                widget.remoteConfig.minSupportedVersion ?? '-'),
            _line(
                'fetched_at', widget.remoteConfig.fetchedAt.toIso8601String()),
          ]),
          _section('Snapshot', [
            _line('Roles', widget.snapshot?.roles.join(', ') ?? '-'),
            _line('Capabilities',
                widget.snapshot?.capabilities.join(', ') ?? '-'),
          ]),
          _section('Event context', [
            _line('event_id', event?.eventId ?? 'none'),
            _line('event_state', event?.eventState.name ?? 'none'),
            _line('write_allowed',
                writeAllowed ? 'yes' : 'blocked by network/event'),
          ]),
          _section('Network', [
            _line('state', widget.networkState.name.toUpperCase()),
            _line('last_transition',
                widget.networkTransitionAt.toIso8601String()),
          ]),
          _section(
              'Cache status (minutes)',
              _cache.entries
                  .map((e) => _line(e.key,
                      e.value == null ? 'missing' : '${e.value!.inMinutes}m'))
                  .toList()),
          _section(
            'API stats',
            [
              ...widget.apiClient.recentRequests().map((r) => _line(
                  '${r.method} ${r.path}', '${r.status} / ${r.latencyMs}ms')),
              _line('errors', widget.apiClient.recentErrorCodes().join(', ')),
            ],
          ),
          _section('Idempotency', [
            _line('entries', '${_idStats.count}'),
            _line('latest',
                '${_idStats.latestIntent ?? '-'} -> ${_idStats.latestKey ?? '-'}'),
          ]),
          Wrap(
              spacing: 6,
              children: chips
                  .map((e) => ChoiceChip(
                      label: Text(e.isEmpty ? 'all logs' : e),
                      selected: _filter == e,
                      onSelected: (_) => setState(() => _filter = e)))
                  .toList()),
          const SizedBox(height: ToreTokens.s8),
          ...logs.take(80).map((e) => ListTile(
              title: Text(e.event),
              subtitle: Text(
                  '${e.ts.toIso8601String()}\n${scrubJsonMap(e.fields)}'))),
          const SizedBox(height: ToreTokens.s8),
          FilledButton(
              onPressed: _copyBuildInfo, child: const Text('Copy build info')),
          TextField(
              controller: _urlController,
              decoration: const InputDecoration(
                  labelText: 'Open URL in app',
                  hintText: 'tore://event/event_42')),
          FilledButton(onPressed: _openUrlInApp, child: const Text('Open URL')),
          FilledButton(
              onPressed: _copyTelemetry,
              child: const Text('Export telemetry (scrubbed)')),
          FilledButton(
              onPressed: _copyBlob,
              child: const Text('Copy diagnostics to clipboard')),
          if (!kReleaseMode) ...[
            OutlinedButton(
                onPressed: _clearCaches, child: const Text('Clear caches')),
            OutlinedButton(
                onPressed: _clearIdempotency,
                child: const Text('Clear idempotency store')),
            DropdownButton<ConnectivityState>(
              value: widget.networkState,
              items: ConnectivityState.values
                  .map((e) => DropdownMenuItem(
                      value: e, child: Text('Simulate ${e.name}')))
                  .toList(),
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
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: ToreTokens.s12),
            ...children
          ]),
        ),
      );

  Widget _line(String k, String v) =>
      Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('$k: $v'));

  Future<void> _copyBuildInfo() async {
    final info = {
      'version': widget.buildInfo.semver,
      'build_number': widget.buildInfo.buildNumber,
      'git_sha': widget.buildInfo.gitSha,
      'build_time': widget.buildInfo.buildTime,
      'environment': appEnvironmentLabel(widget.environment),
    };
    await Clipboard.setData(
        ClipboardData(text: const JsonEncoder.withIndent('  ').convert(info)));
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Build info copied.')));
  }

  Future<void> _openUrlInApp() async {
    await widget.onOpenUrl(_urlController.text);
  }

  Future<void> _copyTelemetry() async {
    final logs = ClientLog.instance
        .entries(filter: _filter.isEmpty ? null : _filter)
        .take(120);
    final lines = logs.map((entry) => jsonEncode({
          'ts': entry.ts.toIso8601String(),
          'event': entry.event,
          'fields': scrubJsonMap(entry.fields),
        }));
    await Clipboard.setData(ClipboardData(text: lines.join('\n')));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Telemetry export copied (scrubbed).')));
  }

  Future<void> _copyBlob() async {
    final scrubbedEvent = widget.eventContext?.eventId == null
        ? 'none'
        : scrubJsonMap({'user_id': widget.eventContext!.eventId})['user_id'];
    final blob = StringBuffer()
      ..writeln('mode=${widget.mode.name}')
      ..writeln('network=${widget.networkState.name}')
      ..writeln('event=$scrubbedEvent')
      ..writeln(
          'build=${widget.buildInfo.semver}+${widget.buildInfo.buildNumber}')
      ..writeln('environment=${appEnvironmentLabel(widget.environment)}')
      ..writeln('roles=${widget.snapshot?.roles.join(',') ?? '-'}')
      ..writeln(
          'cache=${scrubJsonMap(_cache.map((key, value) => MapEntry(key, value?.inMinutes.toString() ?? 'missing')))}')
      ..writeln('errors=${widget.apiClient.recentErrorCodes()}')
      ..writeln('logs=${logsBlob()}');
    await Clipboard.setData(ClipboardData(text: blob.toString()));
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Diagnostics copied.')));
  }

  String logsBlob() {
    final logs = ClientLog.instance
        .entries(filter: _filter.isEmpty ? null : _filter)
        .take(50);
    final lines = logs.map((entry) =>
        '${entry.ts.toIso8601String()} ${entry.event} ${scrubJsonMap(entry.fields)}');
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
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirm'))
        ],
      ),
    );
    return result == true;
  }
}
