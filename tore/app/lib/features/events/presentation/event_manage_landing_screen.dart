import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../features/community/community_models.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';

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

  Future<void> _sharePack() async {
    if (!canWrite(ref, intent: WriteIntent.nonCritical)) return;
    setState(() => _loading = true);
    try {
      final api = ref.read(apiProvider);
      final share = await api.getEventShareV1(widget.event.id);
      final code = await api.createStaffInviteCodeV1(eventId: widget.event.id, idempotencyKey: _idem('staff-invite'));
      final text = '${share['webUrl'] ?? share['https_link'] ?? ''}\n${share['deeplink'] ?? ''}\nstaff code: ${code['code'] ?? '-'}';
      await Clipboard.setData(ClipboardData(text: text));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Share pack copié')));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
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
                label: const Text('Partager le lien'),
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
