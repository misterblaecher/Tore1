import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../shared/utils/write_gate.dart';
import '../../community/community_models.dart';
import '../../entry/presentation/entry_staff_screen.dart';
import '../../staff/presentation/staff_providers.dart';
import 'event_manage_landing_screen.dart';

class StaffInviteJoinScreen extends ConsumerStatefulWidget {
  const StaffInviteJoinScreen({super.key, required this.code});

  final String code;

  @override
  ConsumerState<StaffInviteJoinScreen> createState() =>
      _StaffInviteJoinScreenState();
}

class _StaffInviteJoinScreenState extends ConsumerState<StaffInviteJoinScreen> {
  bool _loading = true;
  bool _joining = false;
  int? _eventId;
  String _role = 'HELPER';
  String _eventName = 'Événement';

  String _idem(String action) =>
      '$action-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final open = await ref
          .read(apiProvider)
          .resolveOpenLink(type: 'staff_invite', code: widget.code);
      final target = Map<String, dynamic>.from(
          (open['target'] as Map?) ?? const <String, dynamic>{});
      final eventId = (target['event_id'] as num?)?.toInt();
      final role = (target['role'] ?? 'HELPER').toString().toUpperCase();
      String eventName = 'Événement';
      if (eventId != null) {
        final sharePack =
            await ref.read(apiProvider).getEventSharePackV1(eventId);
        final event = Map<String, dynamic>.from(
            (sharePack['event'] as Map?) ?? const <String, dynamic>{});
        eventName = (event['name'] ?? 'Événement').toString();
      }
      if (mounted) {
        setState(() {
          _eventId = eventId;
          _role = role;
          _eventName = eventName;
        });
      }
    } catch (_) {
      // Keep fallback UI.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _join() async {
    final eventId = _eventId;
    if (eventId == null || !canWrite(ref, intent: WriteIntent.critical)) return;
    setState(() => _joining = true);
    try {
      final result = await ref.read(apiProvider).joinStaffByInviteV1(
          eventId: eventId,
          code: widget.code,
          idempotencyKey: _idem('staff-join'));
      final role = (result['role'] ?? _role).toString().toUpperCase();
      ref.read(staffSessionProvider.notifier).establish(
            eventId: eventId,
            role: role == 'BAR'
                ? StaffSessionRole.bar
                : role == 'MANAGER'
                    ? StaffSessionRole.manager
                    : StaffSessionRole.entry,
            expiresAt:
                DateTime.tryParse((result['expiresAt'] ?? '').toString()),
          );
      if (!mounted) return;
      if (role == 'ENTRY') {
        Navigator.of(context).pushReplacement(MaterialPageRoute(
            builder: (_) => EntryStaffScreen(eventId: eventId)));
      } else if (role == 'MANAGER') {
        final now = DateTime.now();
        final event = MyEventSummary(
          id: eventId,
          name: _eventName,
          startAt: now,
          endAt: now.add(const Duration(hours: 6)),
          venue: null,
          visibility: 'PRIVATE',
          publicationStatus: 'PUBLISHED',
          status: 'LIVE',
          modulesOn: const <String, dynamic>{},
          hostType: 'user',
          hostId: null,
          roleForMe: 'MANAGER',
          canManage: true,
          joined: true,
        );
        Navigator.of(context).pushReplacement(MaterialPageRoute(
            builder: (_) => EventManageLandingScreen(event: event)));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(role == 'BAR'
                ? 'Bar staff prêt (BAR MODE portail)'
                : 'Helper staff prêt')));
      }
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Invitation staff')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_eventName,
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  Text('Rôle: $_role'),
                  const SizedBox(height: 8),
                  Text('Code: ${widget.code.toUpperCase()}'),
                  const Spacer(),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _joining ? null : _join,
                      child: const Text('Rejoindre le staff'),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}
