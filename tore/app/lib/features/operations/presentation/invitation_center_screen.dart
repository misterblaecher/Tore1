import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'operational_providers.dart';

class InvitationCenterScreen extends ConsumerStatefulWidget {
  const InvitationCenterScreen({super.key, this.initialToken});

  final String? initialToken;

  @override
  ConsumerState<InvitationCenterScreen> createState() =>
      _InvitationCenterScreenState();
}

class _InvitationCenterScreenState
    extends ConsumerState<InvitationCenterScreen> {
  late final TextEditingController _tokenController;
  bool _accepting = false;

  @override
  void initState() {
    super.initState();
    _tokenController = TextEditingController(text: widget.initialToken ?? '');
  }

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  Future<void> _accept() async {
    final token = _tokenController.text.trim();
    if (token.isEmpty || _accepting) return;
    setState(() => _accepting = true);
    try {
      await ref.read(operationalRepositoryProvider).acceptInvitation(
          token, 'mobile-accept-${DateTime.now().microsecondsSinceEpoch}');
      ref.invalidate(operationalInvitationsProvider);
      ref.invalidate(operationalCapabilitiesProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Invitation acceptée')));
      _tokenController.clear();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text(
                'Invitation invalide, expirée ou non destinée à ce compte.')));
      }
    } finally {
      if (mounted) setState(() => _accepting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final invitations = ref.watch(operationalInvitationsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Invitations opérationnelles')),
      body: RefreshIndicator(
        onRefresh: () async =>
            ref.refresh(operationalInvitationsProvider.future),
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              controller: _tokenController,
              autocorrect: false,
              decoration: const InputDecoration(
                labelText: 'Jeton reçu',
                helperText:
                    'Le serveur vérifie le compte cible et l’expiration.',
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _accepting ? null : _accept,
              icon: _accepting
                  ? const SizedBox.square(
                      dimension: 18, child: CircularProgressIndicator())
                  : const Icon(Icons.verified_user_outlined),
              label: const Text('Accepter'),
            ),
            const SizedBox(height: 24),
            Text('Pour ce compte',
                style: Theme.of(context).textTheme.titleMedium),
            invitations.when(
              loading: () => const Padding(
                  padding: EdgeInsets.all(24),
                  child: Center(child: CircularProgressIndicator())),
              error: (_, __) => const ListTile(
                  leading: Icon(Icons.error_outline),
                  title: Text('Invitations indisponibles')),
              data: (items) => Column(
                children: items
                    .map((item) => ListTile(
                          leading: const Icon(Icons.badge_outlined),
                          title: Text(
                              (item['event_name'] ?? 'Événement').toString()),
                          subtitle: Text(
                              '${item['role']} · ${item['status']}\nExpiration : ${item['expires_at'] ?? '—'}'),
                          isThreeLine: true,
                        ))
                    .toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
