import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';

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
  bool _loading = true;
  bool _posting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final res = await ref.read(apiProvider).getMusic(widget.eventId);
      if (mounted) setState(() => _payload = res);
    } catch (_) {
      if (mounted) setState(() => _payload = null);
    } finally {
      if (mounted) setState(() => _loading = false);
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

  @override
  Widget build(BuildContext context) {
    final state = ((_payload?['runtimeState'] ?? 'LIVE').toString()).toUpperCase();
    final readOnly = isReadOnly(ref);
    final network = ref.watch(networkStatusProvider);
    final writeBlocked = isWriteBlocked(
      readOnly: readOnly,
      runtimeBlocked: isWriteBlockedByEventState(state),
      degradedBlocked: network == NetworkState.degraded,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Music vote')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_payload == null) const Text('Module indisponible.'),
                  if (_payload != null) ...[
                    Text('Winner: ${((_payload!['winner']?['candidate']?['title']) ?? '—').toString()}'),
                    const SizedBox(height: 8),
                    Text('Open: ${((_payload!['winner']?['candidate']?['externalUrl']) ?? '—').toString()}'),
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
                      onPressed: writeBlocked ? null : () => _vote(_composeCandidate()),
                      child: const Text('Vote'),
                    ),
                    const SizedBox(height: 16),
                    const Text('Top tracks', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    ...((( _payload!['topCandidates'] as List?) ?? const [])).map((row) {
                      final m = Map<String, dynamic>.from(row as Map);
                      final candidate = Map<String, dynamic>.from((m['candidate'] as Map?) ?? const {});
                      return Card(
                        child: ListTile(
                          title: Text('${candidate['title'] ?? ''} — ${candidate['artist'] ?? ''}'),
                          subtitle: Text('${candidate['provider'] ?? ''} • ${m['votes'] ?? 0} votes'),
                          trailing: TextButton(onPressed: writeBlocked ? null : () => _vote(candidate), child: const Text('Vote')),
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
