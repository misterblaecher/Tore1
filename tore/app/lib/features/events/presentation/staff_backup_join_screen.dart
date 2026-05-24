import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import '../../entry/presentation/entry_staff_screen.dart';
import '../../staff/presentation/staff_providers.dart';

class StaffBackupJoinScreen extends ConsumerStatefulWidget {
  const StaffBackupJoinScreen(
      {super.key, this.prefillEventId, this.prefillCode});

  final int? prefillEventId;
  final String? prefillCode;

  @override
  ConsumerState<StaffBackupJoinScreen> createState() =>
      _StaffBackupJoinScreenState();
}

class _StaffBackupJoinScreenState extends ConsumerState<StaffBackupJoinScreen> {
  late final TextEditingController _eventCtrl =
      TextEditingController(text: widget.prefillEventId?.toString() ?? '');
  late final TextEditingController _codeCtrl =
      TextEditingController(text: (widget.prefillCode ?? '').toUpperCase());
  bool _joining = false;
  String? _error;

  String _idem() =>
      'staff-backup-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  Future<void> _join() async {
    final eventId = int.tryParse(_eventCtrl.text.trim());
    final code = _codeCtrl.text.trim().toUpperCase();
    if (eventId == null || code.length < 8) {
      setState(() => _error = 'eventId/code invalide');
      return;
    }
    if (!canWrite(ref, intent: WriteIntent.critical)) return;
    setState(() {
      _joining = true;
      _error = null;
    });
    try {
      final res = await ref.read(apiProvider).joinStaffByBackupCodeV1(
          eventId: eventId, code: code, idempotencyKey: _idem());
      final role = (res['role'] ?? 'HELPER').toString().toUpperCase();
      ref.read(staffSessionProvider.notifier).establish(
            eventId: eventId,
            role: role == 'BAR'
                ? StaffSessionRole.bar
                : role == 'MANAGER'
                    ? StaffSessionRole.manager
                    : StaffSessionRole.entry,
            tokenId: (res['tokenId'] ?? '').toString(),
            expiresAt: DateTime.tryParse((res['expiresAt'] ?? '').toString()),
          );
      if (!mounted) return;
      if (role == 'ENTRY') {
        Navigator.of(context).pushReplacement(MaterialPageRoute(
            builder: (_) => EntryStaffScreen(eventId: eventId)));
      } else {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Session $role établie.')));
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Backup code staff')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
                controller: _eventCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Event ID')),
            const SizedBox(height: 8),
            TextField(
                controller: _codeCtrl,
                decoration: const InputDecoration(labelText: 'Backup code')),
            const SizedBox(height: 12),
            if (_error != null)
              Text(_error!, style: const TextStyle(color: Colors.redAccent)),
            const Spacer(),
            SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                    onPressed: _joining ? null : _join,
                    child: const Text('Rejoindre staff'))),
          ],
        ),
      ),
    );
  }
}
