import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/providers.dart';

class OrgaInviteJoinScreen extends ConsumerStatefulWidget {
  const OrgaInviteJoinScreen({super.key, required this.code});

  final String code;

  @override
  ConsumerState<OrgaInviteJoinScreen> createState() => _OrgaInviteJoinScreenState();
}

class _OrgaInviteJoinScreenState extends ConsumerState<OrgaInviteJoinScreen> {
  late final TextEditingController _codeCtrl;
  bool _loading = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _codeCtrl = TextEditingController(text: widget.code);
  }

  Future<void> _join() async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      final code = _codeCtrl.text.trim();
      final res = await ref.read(apiProvider).orgaJoinByInvite(code: code, idempotencyKey: 'orga-invite-$code');
      setState(() => _message = 'Rejoint comme ${res['role'] ?? 'MEMBER'}');
    } catch (_) {
      setState(() => _message = 'Impossible de rejoindre via ce code.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Invitation organisation')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(controller: _codeCtrl, decoration: const InputDecoration(labelText: 'Code invitation')),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _loading ? null : _join,
              child: _loading ? const CircularProgressIndicator.adaptive() : const Text('Rejoindre'),
            ),
            if (_message != null) ...[
              const SizedBox(height: 12),
              Text(_message!),
            ],
          ],
        ),
      ),
    );
  }
}
