import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../shared/utils/write_gate.dart';

class EventSharePackScreen extends ConsumerStatefulWidget {
  const EventSharePackScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<EventSharePackScreen> createState() => _EventSharePackScreenState();
}

class _EventSharePackScreenState extends ConsumerState<EventSharePackScreen> {
  Map<String, dynamic>? _pack;

  String _idem(String action) => '$action-${widget.eventId}-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    final pack = await ref.read(apiProvider).getEventSharePackV1(widget.eventId);
    if (mounted) setState(() => _pack = pack);
  }

  Future<void> _copy(String value) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copié')));
  }

  Future<void> _createStaffInvite(String role) async {
    if (!canWrite(ref, intent: WriteIntent.critical)) return;
    await ref.read(apiProvider).createStaffInviteCodeV1(eventId: widget.eventId, idempotencyKey: _idem('create-$role'), role: role);
    await _refresh();
  }

  Future<void> _revokeStaffInvite(String code) async {
    if (!canWrite(ref, intent: WriteIntent.critical)) return;
    await ref.read(apiProvider).revokeStaffInviteCodeV1(eventId: widget.eventId, code: code, reason: 'Revoked from share pack', idempotencyKey: _idem('revoke-$code'));
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final pack = _pack;
    final links = Map<String, dynamic>.from((pack?['links'] as Map?) ?? const <String, dynamic>{});
    final staffInvites = ((links['staffInvites'] as List?) ?? const []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    final qr = Map<String, dynamic>.from((pack?['qr'] as Map?) ?? const <String, dynamic>{});

    return Scaffold(
      appBar: AppBar(title: const Text('Share pack')),
      body: pack == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _LinkCard(title: 'Public link', link: links['publicShare'], onCopy: _copy),
                const SizedBox(height: 8),
                _LinkCard(title: 'Join link', link: links['joinPublic'], onCopy: _copy),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('Staff invites', style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Wrap(spacing: 8, children: [for (final role in const ['ENTRY', 'BAR', 'MANAGER', 'HELPER']) OutlinedButton(onPressed: () => _createStaffInvite(role), child: Text('Créer $role'))]),
                      const SizedBox(height: 8),
                      for (final invite in staffInvites)
                        ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text('${invite['role']} · ${invite['code']}'),
                          subtitle: Text('Expire: ${invite['expiresAt'] ?? '-'} · ${invite['status'] ?? '-'}'),
                          trailing: Wrap(spacing: 4, children: [
                            IconButton(onPressed: () => _copy((invite['webUrl'] ?? '').toString()), icon: const Icon(Icons.copy)),
                            IconButton(onPressed: () => _revokeStaffInvite((invite['code'] ?? '').toString()), icon: const Icon(Icons.block)),
                          ]),
                        ),
                    ]),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('QR payloads', style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      for (final e in qr.entries) ListTile(contentPadding: EdgeInsets.zero, title: Text(e.key), subtitle: Text(e.value.toString()), trailing: IconButton(onPressed: () => _copy(e.value.toString()), icon: const Icon(Icons.copy))),
                    ]),
                  ),
                ),
                const SizedBox(height: 8),
                Text(jsonEncode(pack), style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
    );
  }
}

class _LinkCard extends StatelessWidget {
  const _LinkCard({required this.title, required this.link, required this.onCopy});

  final String title;
  final dynamic link;
  final Future<void> Function(String) onCopy;

  @override
  Widget build(BuildContext context) {
    final map = Map<String, dynamic>.from((link as Map?) ?? const <String, dynamic>{});
    final web = (map['webUrl'] ?? '').toString();
    final deep = (map['deeplink'] ?? '').toString();
    return Card(
      child: ListTile(
        title: Text(title),
        subtitle: Text('$web\n$deep'),
        isThreeLine: true,
        trailing: IconButton(onPressed: web.isEmpty ? null : () => onCopy(web), icon: const Icon(Icons.copy)),
      ),
    );
  }
}
