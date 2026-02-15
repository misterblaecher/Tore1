import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import 'music_admin_panel_screen.dart';

class MusicVoteScreen extends ConsumerStatefulWidget {
  const MusicVoteScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<MusicVoteScreen> createState() => _MusicVoteScreenState();
}

class _MusicVoteScreenState extends ConsumerState<MusicVoteScreen> {
  final _titleCtrl = TextEditingController();
  final _artistCtrl = TextEditingController();
  final _urlCtrl = TextEditingController();
  String _provider = 'spotify';
  Map<String, dynamic>? _payload;
  Map<String, dynamic>? _context;
  bool _loading = true;
  bool _posting = false;
  Timer? _pollTimer;
  Timer? _clock;
  NetworkState? _pollingState;

  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    _load();
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _now = DateTime.now());
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _clock?.cancel();
    _titleCtrl.dispose();
    _artistCtrl.dispose();
    _urlCtrl.dispose();
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
      final api = ref.read(apiProvider);
      final music = await api.getMusic(widget.eventId);
      final context = await api.eventContext(widget.eventId);
      if (mounted) {
        setState(() {
          _payload = music;
          _context = context;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _payload = null);
    } finally {
      if (mounted && !silent) setState(() => _loading = false);
    }
  }

  Future<void> _vote(Map<String, dynamic> candidate) async {
    if (_posting) return;
    setState(() => _posting = true);
    try {
      await ref.read(apiProvider).voteMusic(eventId: widget.eventId, candidate: candidate, idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString());
      await _load();
    } on DioException catch (e) {
      if (!mounted) return;
      final msg = (e.response?.data is Map) ? ((e.response?.data['reason'] ?? 'vote_failed').toString()) : 'vote_failed';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } finally {
      if (mounted) setState(() => _posting = false);
    }
  }

  Map<String, dynamic> _composeCandidate() {
    final url = _urlCtrl.text.trim().isNotEmpty ? _urlCtrl.text.trim() : _searchUrl(_provider, _titleCtrl.text.trim(), _artistCtrl.text.trim());
    return {
      'provider': _provider,
      'externalUrl': url,
      'title': _titleCtrl.text.trim().isEmpty ? 'Unknown title' : _titleCtrl.text.trim(),
      'artist': _artistCtrl.text.trim().isEmpty ? 'Unknown artist' : _artistCtrl.text.trim(),
    };
  }

  String _searchUrl(String provider, String title, String artist) {
    final q = Uri.encodeComponent('$title $artist'.trim());
    switch (provider) {
      case 'apple':
        return 'https://music.apple.com/search?term=$q';
      case 'ytmusic':
        return 'https://music.youtube.com/search?q=$q';
      case 'soundcloud':
        return 'https://soundcloud.com/search?q=$q';
      default:
        return 'https://open.spotify.com/search/$q';
    }
  }

  String _countdown(Map<String, dynamic> round) {
    final endsAtRaw = round['endsAt']?.toString();
    if (endsAtRaw == null) return '--:--';
    final endsAt = DateTime.tryParse(endsAtRaw)?.toLocal();
    if (endsAt == null) return '--:--';
    final remaining = endsAt.difference(_now);
    if (remaining.isNegative) return '00:00';
    final min = remaining.inMinutes.toString().padLeft(2, '0');
    final sec = (remaining.inSeconds % 60).toString().padLeft(2, '0');
    return '$min:$sec';
  }

  @override
  Widget build(BuildContext context) {
    final network = ref.watch(networkStatusProvider);
    if (_pollingState != network) {
      _pollingState = network;
      _schedulePolling(network);
    }
    final runtimeState = ((_payload?['runtimeState'] ?? 'LIVE').toString()).toUpperCase();
    final readOnly = isReadOnly(ref);
    final round = Map<String, dynamic>.from((_payload?['round'] as Map?) ?? const {});
    final roundStatus = (round['status'] ?? 'IDLE').toString();
    final writeBlocked = isWriteBlocked(
      readOnly: readOnly,
      runtimeBlocked: isWriteBlockedByEventState(runtimeState),
      degradedBlocked: network == NetworkState.degraded,
    );
    final canVote = !writeBlocked && !_posting && roundStatus == 'OPEN';
    final permissions = Map<String, dynamic>.from((_context?['permissions'] as Map?) ?? const {});
    final canAdminMusic = (permissions['canAdminMusic'] == true) || (permissions['canDjMusic'] == true);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Music vote'),
        actions: [
          if (canAdminMusic)
            IconButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MusicAdminPanelScreen(eventId: widget.eventId))),
              icon: const Icon(Icons.tune),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_payload == null) const Text('Module indisponible.'),
                  if (_payload != null) ...[
                    Card(
                      child: ListTile(
                        title: Text(
                          roundStatus == 'OPEN'
                              ? 'Round OPEN • ${_countdown(round)}'
                              : roundStatus == 'LOCKED'
                                  ? 'Winner locked'
                                  : 'Waiting for next round',
                        ),
                      ),
                    ),
                    if (_payload!['nowPlaying'] is Map)
                      Card(
                        child: ListTile(
                          title: Text('Now Playing: ${_payload!['nowPlaying']['title'] ?? ''}'),
                          subtitle: Text('Open in ${_payload!['nowPlaying']['provider'] ?? ''}: ${_payload!['nowPlaying']['externalUrl'] ?? ''}'),
                        ),
                      ),
                    if (_payload!['winner'] is Map)
                      Card(
                        child: ListTile(
                          title: Text('Next winner: ${_payload!['winner']['candidate']['title'] ?? ''}'),
                          subtitle: Text('Votes: ${_payload!['winner']['votesCount'] ?? 0} • Open in ${_payload!['winner']['candidate']['provider'] ?? ''}'),
                        ),
                      ),
                    const SizedBox(height: 16),
                    DropdownButton<String>(
                      value: _provider,
                      items: const [
                        DropdownMenuItem(value: 'spotify', child: Text('Spotify')),
                        DropdownMenuItem(value: 'apple', child: Text('Apple Music')),
                        DropdownMenuItem(value: 'ytmusic', child: Text('YouTube Music')),
                        DropdownMenuItem(value: 'soundcloud', child: Text('SoundCloud')),
                      ],
                      onChanged: (v) => setState(() => _provider = v ?? 'spotify'),
                    ),
                    TextField(controller: _titleCtrl, decoration: const InputDecoration(labelText: 'Title')),
                    TextField(controller: _artistCtrl, decoration: const InputDecoration(labelText: 'Artist')),
                    TextField(controller: _urlCtrl, decoration: const InputDecoration(labelText: 'Link (optional)')),
                    const SizedBox(height: 8),
                    ElevatedButton(
                      onPressed: canVote ? () => _vote(_composeCandidate()) : null,
                      child: const Text('Vote'),
                    ),
                    const SizedBox(height: 16),
                    const Text('Top tracks', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ...(((_payload!['topCandidates'] as List?) ?? const [])).map((row) {
                      final m = Map<String, dynamic>.from(row as Map);
                      final candidate = Map<String, dynamic>.from((m['candidate'] as Map?) ?? const {});
                      return Card(
                        child: ListTile(
                          title: Text('${candidate['title'] ?? ''} — ${candidate['artist'] ?? ''}'),
                          subtitle: Text('${candidate['provider'] ?? ''} • ${m['votes'] ?? 0} votes'),
                          trailing: TextButton(onPressed: canVote ? () => _vote(candidate) : null, child: const Text('Vote')),
                        ),
                      );
                    }),
                  ],
                ],
              ),
            ),
    );
  }
}
