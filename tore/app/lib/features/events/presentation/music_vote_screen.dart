import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../state.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import 'music_admin_panel_screen.dart';
import 'music_vote_models.dart';

class MusicVoteScreen extends ConsumerStatefulWidget {
  const MusicVoteScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<MusicVoteScreen> createState() => _MusicVoteScreenState();
}

class _MusicVoteScreenState extends ConsumerState<MusicVoteScreen> {
  final _urlCtrl = TextEditingController();
  final _titleHintCtrl = TextEditingController();
  MusicProvider _provider = MusicProvider.spotify;
  Map<String, dynamic>? _payload;
  Map<String, dynamic>? _context;
  Map<String, dynamic>? _preEventPayload;
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
    _titleHintCtrl.dispose();
    _urlCtrl.dispose();
    super.dispose();
  }

  void _schedulePolling(NetworkState state) {
    _pollTimer?.cancel();
    if (state == NetworkState.offline) return;
    final seconds = state == NetworkState.degraded ? 5 : 2;
    _pollTimer =
        Timer.periodic(Duration(seconds: seconds), (_) => _load(silent: true));
  }

  Future<void> _load({bool silent = false}) async {
    if (!silent && mounted) setState(() => _loading = true);
    try {
      final api = ref.read(apiProvider);
      final music = await api.getMusic(widget.eventId);
      final context = await api.eventContext(widget.eventId);
      final preEvent = await api.getMusicPreEvent(widget.eventId);
      if (mounted) {
        setState(() {
          _payload = music;
          _context = context;
          _preEventPayload = preEvent;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _payload = null);
    } finally {
      if (mounted && !silent) setState(() => _loading = false);
    }
  }

  Future<void> _addCandidate() async {
    final raw = _urlCtrl.text.trim();
    if (!isLocallyValidCandidateLink(raw, _provider)) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Lien invalide pour ce provider.')));
      return;
    }
    if (_posting) return;
    setState(() => _posting = true);
    try {
      final res = await ref.read(apiProvider).addMusicCandidate(
            eventId: widget.eventId,
            provider: musicProviderApiValue(_provider),
            externalUrl: raw,
            titleHint: _titleHintCtrl.text,
            idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString(),
          );
      final status = (res['status'] ?? '').toString();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(status == 'already_exists'
                ? 'Déjà dans la liste'
                : 'Candidat ajouté')),
      );
      await _load();
    } on DioException catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Ajout impossible')));
    } finally {
      if (mounted) setState(() => _posting = false);
    }
  }

  Future<void> _suggestPreEvent() async {
    final raw = _urlCtrl.text.trim();
    if (!isLocallyValidCandidateLink(raw, _provider) || _posting) return;
    setState(() => _posting = true);
    try {
      await ref.read(apiProvider).suggestMusicPreEvent(
            eventId: widget.eventId,
            provider: musicProviderApiValue(_provider),
            externalUrl: raw,
            title: _titleHintCtrl.text.trim(),
            idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString(),
          );
      await _load();
    } finally {
      if (mounted) setState(() => _posting = false);
    }
  }

  Future<void> _votePreEvent(int suggestionId) async {
    if (_posting) return;
    setState(() => _posting = true);
    try {
      await ref.read(apiProvider).voteMusicPreEvent(
            eventId: widget.eventId,
            suggestionId: suggestionId,
            idempotencyKey: DateTime.now().microsecondsSinceEpoch.toString(),
          );
      await _load();
    } finally {
      if (mounted) setState(() => _posting = false);
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
    final runtimeState =
        ((_payload?['runtimeState'] ?? 'LIVE').toString()).toUpperCase();
    final readOnly = isReadOnly(ref);
    final round =
        Map<String, dynamic>.from((_payload?['round'] as Map?) ?? const {});
    final roundStatus = (round['status'] ?? 'IDLE').toString();
    final writeBlocked = isWriteBlocked(
      readOnly: readOnly,
      runtimeBlocked: isWriteBlockedByEventState(runtimeState),
      degradedBlocked: network == NetworkState.degraded,
    );
    final canVote = !writeBlocked && !_posting && roundStatus == 'OPEN';
    final permissions = Map<String, dynamic>.from(
        (_context?['permissions'] as Map?) ?? const {});
    final canAdminMusic = (permissions['canAdminMusic'] == true) ||
        (permissions['canDjMusic'] == true);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Music vote'),
        actions: [
          if (canAdminMusic)
            IconButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) =>
                      MusicAdminPanelScreen(eventId: widget.eventId))),
              icon: const Icon(Icons.tune),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : DefaultTabController(
              length: 2,
              child: Column(
                children: [
                  const TabBar(
                      tabs: [Tab(text: 'Pré-event'), Tab(text: 'Live')]),
                  Expanded(
                    child: RefreshIndicator(
                      onRefresh: _load,
                      child: TabBarView(children: [
                        ListView(
                          padding: const EdgeInsets.all(16),
                          children: [
                            DropdownButton<MusicProvider>(
                              value: _provider,
                              items: MusicProvider.values
                                  .map((provider) => DropdownMenuItem(
                                      value: provider,
                                      child:
                                          Text(musicProviderLabel(provider))))
                                  .toList(),
                              onChanged: (v) => setState(
                                  () => _provider = v ?? MusicProvider.spotify),
                            ),
                            TextField(
                                controller: _urlCtrl,
                                decoration:
                                    const InputDecoration(labelText: 'Lien')),
                            TextField(
                                controller: _titleHintCtrl,
                                decoration: const InputDecoration(
                                    labelText: 'Titre (optionnel)')),
                            const SizedBox(height: 8),
                            ElevatedButton(
                                onPressed: writeBlocked || _posting
                                    ? null
                                    : _suggestPreEvent,
                                child: const Text('Suggérer un son')),
                            const SizedBox(height: 12),
                            if (((_preEventPayload?['items'] as List?) ??
                                    const [])
                                .isEmpty)
                              const Card(
                                  child: ListTile(
                                      title: Text(
                                          'Aucune suggestion pour le moment'),
                                      subtitle: Text(
                                          'Sois le premier à proposer un son.'))),
                            ...(((_preEventPayload?['items'] as List?) ??
                                    const []))
                                .map((row) {
                              final item =
                                  Map<String, dynamic>.from(row as Map);
                              return Card(
                                  child: ListTile(
                                title: Text(
                                    '${item['title'] ?? 'Track'} - ${item['artist'] ?? ''}'),
                                subtitle: Text('Votes: ${item['votes'] ?? 0}'),
                                trailing: IconButton(
                                    icon:
                                        const Icon(Icons.thumb_up_alt_outlined),
                                    onPressed: writeBlocked || _posting
                                        ? null
                                        : () => _votePreEvent(
                                            (item['id'] ?? 0) as int)),
                              ));
                            }),
                          ],
                        ),
                        ListView(
                          padding: const EdgeInsets.all(16),
                          children: [
                            if (_payload == null)
                              const Text('Module indisponible.'),
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
                                    title: Text(
                                        'Now Playing: ${_payload!['nowPlaying']['title'] ?? ''}'),
                                    subtitle: Text(
                                        'Open in ${_payload!['nowPlaying']['provider'] ?? ''}: ${_payload!['nowPlaying']['externalUrl'] ?? ''}'),
                                  ),
                                ),
                              if (_payload!['winner'] is Map)
                                Card(
                                  child: ListTile(
                                    title: Text(
                                        'Next winner: ${_payload!['winner']['candidate']['title'] ?? ''}'),
                                    subtitle: Text(
                                        'Votes: ${_payload!['winner']['votesCount'] ?? 0} • Open in ${_payload!['winner']['candidate']['provider'] ?? ''}'),
                                  ),
                                ),
                              const SizedBox(height: 16),
                              DropdownButton<MusicProvider>(
                                value: _provider,
                                items: MusicProvider.values
                                    .map((provider) => DropdownMenuItem(
                                        value: provider,
                                        child:
                                            Text(musicProviderLabel(provider))))
                                    .toList(),
                                onChanged: (v) => setState(() =>
                                    _provider = v ?? MusicProvider.spotify),
                              ),
                              TextField(
                                  controller: _urlCtrl,
                                  decoration:
                                      const InputDecoration(labelText: 'Lien')),
                              TextField(
                                  controller: _titleHintCtrl,
                                  decoration: const InputDecoration(
                                      labelText: 'Titre (optionnel)')),
                              const SizedBox(height: 8),
                              ElevatedButton(
                                onPressed: canVote ? _addCandidate : null,
                                child: const Text('Ajouter'),
                              ),
                              const SizedBox(height: 16),
                              const Text('Candidats',
                                  style:
                                      TextStyle(fontWeight: FontWeight.bold)),
                              const SizedBox(height: 8),
                              if (((_payload!['candidates'] as List?) ??
                                      const [])
                                  .isEmpty)
                                const Card(
                                    child: ListTile(
                                        title: Text('Aucun candidat live'),
                                        subtitle: Text(
                                            'Ajoute un morceau quand un round est ouvert.'))),
                              ...(((_payload!['candidates'] as List?) ??
                                      const []))
                                  .map((row) {
                                final candidate =
                                    Map<String, dynamic>.from(row as Map);
                                final provider = musicProviderFromApi(
                                    '${candidate['provider'] ?? ''}');
                                final url = (candidate['urlOriginal'] ??
                                        candidate['externalUrl'] ??
                                        '')
                                    .toString();
                                return Card(
                                  child: ListTile(
                                    title: Text((candidate['titleHint'] ?? '')
                                            .toString()
                                            .isNotEmpty
                                        ? '${candidate['titleHint']}'
                                        : 'Lien'),
                                    subtitle: Text(candidateShortLink(url)),
                                    leading: Chip(
                                        label: Text(provider == null
                                            ? '${candidate['provider'] ?? ''}'
                                            : musicProviderLabel(provider))),
                                    trailing: IconButton(
                                      icon: const Icon(Icons.open_in_new),
                                      onPressed: () async {
                                        final uri = Uri.tryParse(url);
                                        if (uri != null) {
                                          await launchUrl(uri,
                                              mode: LaunchMode
                                                  .externalApplication);
                                        }
                                      },
                                    ),
                                  ),
                                );
                              }),
                            ],
                          ],
                        ),
                      ]),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
