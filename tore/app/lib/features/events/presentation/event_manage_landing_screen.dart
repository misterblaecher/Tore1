import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../../features/community/community_models.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/utils/share_text.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../state.dart';
import 'event_share_pack_screen.dart';

class EventManageLandingScreen extends ConsumerStatefulWidget {
  const EventManageLandingScreen({super.key, required this.event});

  final MyEventSummary event;

  @override
  ConsumerState<EventManageLandingScreen> createState() => _EventManageLandingScreenState();
}

class _EventManageLandingScreenState extends ConsumerState<EventManageLandingScreen> {
  bool _loading = false;

  String _idem(String action) => '$action-${widget.event.id}-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  Future<void> _publish() async {
    if (!canWrite(ref, intent: WriteIntent.critical)) return;
    setState(() => _loading = true);
    try {
      await ref.read(apiProvider).publishEventV1(eventId: widget.event.id, idempotencyKey: _idem('publish'));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Event publié')));
      setState(() {});
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }


  Future<void> _shareEvent() async {
    final share = await ref.read(apiProvider).getEventShareV1(widget.event.id);
    String? shortUrl;
    if (ref.read(networkStatusProvider) == NetworkState.online) {
      try {
        final short = await ref.read(apiProvider).createShortlink(kind: 'event_share', eventId: widget.event.id, idempotencyKey: _idem('shortlink'));
        shortUrl = (short['shortUrl'] ?? '').toString();
      } catch (_) {}
    }
    final eventCode = (share['event_code'] ?? '').toString();
    final fallback = eventCode.length >= 4 ? eventCode.substring(eventCode.length - 4) : null;
    final url = pickShareUrl(shortUrl: shortUrl, webUrl: (share['webUrl'] ?? '').toString(), openUrl: (share['https_link'] ?? '').toString());
    await Share.share(shareText(url: url, fallbackSuffix: fallback), subject: widget.event.name);
  }

  Future<void> _sharePack() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventSharePackScreen(eventId: widget.event.id)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Manage • ${widget.event.name}')),
      body: FutureBuilder<ManageSnapshot>(
        future: ref.read(apiProvider).eventManageSnapshot(widget.event.id),
        builder: (context, snap) {
          final snapshot = snap.data;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: ListTile(
                  title: Text(widget.event.name),
                  subtitle: Text('${widget.event.roleForMe} • ${widget.event.visibility} • ${snapshot?.runtimeState ?? widget.event.status}'),
                ),
              ),
              const SizedBox(height: 12),
              if ((snapshot?.publicationStatus ?? '').toUpperCase() == 'DRAFT')
                ElevatedButton.icon(
                  onPressed: _loading ? null : _publish,
                  icon: const Icon(Icons.publish_outlined),
                  label: const Text('Publier'),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _loading ? null : _sharePack,
                icon: const Icon(Icons.ios_share_outlined),
                label: const Text('Share pack'),
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _loading ? null : _shareEvent,
                icon: const Icon(Icons.share_outlined),
                label: const Text('Partager'),
              ),
              if (snapshot != null) ...[
                const SizedBox(height: 12),
                Text('Staff invite actuel: ${snapshot.staffInviteCodeCurrent ?? '-'}'),
              ],
            ],
          );
        },
      ),
    );
  }
}
