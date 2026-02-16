import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';

class MusicAdminPanelScreen extends ConsumerStatefulWidget {
  const MusicAdminPanelScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<MusicAdminPanelScreen> createState() => _MusicAdminPanelScreenState();
}

class _MusicAdminPanelScreenState extends ConsumerState<MusicAdminPanelScreen> {
  Map<String, dynamic>? _payload;
  bool _loading = true;
  bool _pending = false;
  int _durationSec = 120;
  Timer? _pollTimer;
  NetworkState? _pollingState;

  final _titleCtrl = TextEditingController();
  final _artistCtrl = TextEditingController();
  final _urlCtrl = TextEditingController();
  final _reasonCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _titleCtrl.dispose();
    _artistCtrl.dispose();
    _urlCtrl.dispose();
    _reasonCtrl.dispose();
    super.dispose();
  }

  void _schedulePolling(NetworkState state) {
    _pollTimer?.cancel();
    if (state == NetworkState.offline) return;
    final seconds = state == NetworkState.degraded ? 5 : 2;
    _pollTimer = Timer.periodic(Duration(seconds: seconds), (_) => _load(silent: true));
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent && mounted) setState(() => _loading = true);
    try {
      final res = await ref.read(apiProvider).getMusic(widget.eventId);
      if (mounted) setState(() => _payload = res);
    } catch (_) {
      if (mounted) setState(() => _payload = null);
    } finally {
      if (mounted && !silent) setState(() => _loading = false);
    }
  }

  Future<void> _act(Future<void> Function() fn) async {
    if (_pending) return;
    setState(() => _pending = true);
    try {
      await fn();
      await _load();
    } on DioException catch (e) {
      if (!mounted) return;
      final msg = (e.response?.data is Map) ? ((e.response?.data['reason'] ?? 'action_failed').toString()) : 'action_failed';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  String _idempotency() => DateTime.now().microsecondsSinceEpoch.toString();

  Map<String, dynamic> _candidate() => {
        'provider': 'spotify',
        'externalUrl': _urlCtrl.text.trim().isEmpty ? 'https://open.spotify.com/search/${Uri.encodeComponent('${_titleCtrl.text} ${_artistCtrl.text}')}' : _urlCtrl.text.trim(),
        'title': _titleCtrl.text.trim().isEmpty ? 'Unknown title' : _titleCtrl.text.trim(),
        'artist': _artistCtrl.text.trim().isEmpty ? 'Unknown artist' : _artistCtrl.text.trim(),
      };

  @override
  Widget build(BuildContext context) {
    final network = ref.watch(networkStatusProvider);
    if (_pollingState != network) {
      _pollingState = network;
      _schedulePolling(network);
    }
    final state = ((_payload?['runtimeState'] ?? 'LIVE').toString()).toUpperCase();
    final blocked = isWriteBlocked(readOnly: isReadOnly(ref), runtimeBlocked: isWriteBlockedByEventState(state), degradedBlocked: network == NetworkState.degraded);
    final actionsDisabled = blocked || _pending;

    return Scaffold(
      appBar: AppBar(title: const Text('DJ / Admin panel')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<int>(
                  value: _durationSec,
                  items: const [60, 120, 180, 300].map((v) => DropdownMenuItem(value: v, child: Text('${v}s'))).toList(),
                  onChanged: actionsDisabled ? null : (v) => setState(() => _durationSec = v ?? 120),
                  decoration: const InputDecoration(labelText: 'Round duration'),
                ),
                const SizedBox(height: 8),
                ElevatedButton(
                  onPressed: actionsDisabled
                      ? null
                      : () => _act(() => ref.read(apiProvider).adminMusicRoundStart(eventId: widget.eventId, durationSec: _durationSec, idempotencyKey: _idempotency())),
                  child: const Text('Start round'),
                ),
                ElevatedButton(
                  onPressed: actionsDisabled ? null : () => _act(() => ref.read(apiProvider).adminMusicRoundEnd(eventId: widget.eventId, idempotencyKey: _idempotency())),
                  child: const Text('End round'),
                ),
                const Divider(),
                TextField(controller: _titleCtrl, decoration: const InputDecoration(labelText: 'Now Playing title')),
                TextField(controller: _artistCtrl, decoration: const InputDecoration(labelText: 'Now Playing artist')),
                TextField(controller: _urlCtrl, decoration: const InputDecoration(labelText: 'Now Playing link')),
                const SizedBox(height: 8),
                ElevatedButton(
                  onPressed: actionsDisabled
                      ? null
                      : () => _act(() => ref.read(apiProvider).adminMusicNowPlaying(eventId: widget.eventId, candidate: _candidate(), idempotencyKey: _idempotency(), reason: _reasonCtrl.text.trim().isEmpty ? null : _reasonCtrl.text.trim())),
                  child: const Text('Set now playing'),
                ),
                const Divider(),
                TextField(controller: _reasonCtrl, decoration: const InputDecoration(labelText: 'Reason (skip/clear/force)')),
                ElevatedButton(
                  onPressed: actionsDisabled
                      ? null
                      : () => _act(() => ref.read(apiProvider).adminMusicSkip(eventId: widget.eventId, idempotencyKey: _idempotency(), reason: _reasonCtrl.text.trim().isEmpty ? 'skip' : _reasonCtrl.text.trim())),
                  child: const Text('Skip winner'),
                ),
                ElevatedButton(
                  onPressed: actionsDisabled
                      ? null
                      : () => _act(() => ref.read(apiProvider).adminMusicForce(eventId: widget.eventId, candidate: _candidate(), idempotencyKey: _idempotency(), reason: _reasonCtrl.text.trim())),
                  child: const Text('Force track'),
                ),
                ElevatedButton(
                  onPressed: actionsDisabled
                      ? null
                      : () => _act(() => ref.read(apiProvider).adminMusicClear(eventId: widget.eventId, idempotencyKey: _idempotency(), reason: _reasonCtrl.text.trim())),
                  child: const Text('Clear votes'),
                ),
              ],
            ),
    );
  }
}
