import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../core/auth/email_token.dart';
import '../../../core/auth/providers.dart';

class EmailAuthScreen extends ConsumerStatefulWidget {
  const EmailAuthScreen({super.key});

  @override
  ConsumerState<EmailAuthScreen> createState() => _EmailAuthScreenState();
}

class _EmailAuthScreenState extends ConsumerState<EmailAuthScreen> {
  final _emailCtrl = TextEditingController();
  final _tokenCtrl = TextEditingController();

  bool _loading = false;
  bool _requested = false;
  String? _devToken;
  String? _error;

  Future<void> _requestLink() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final out = await ref.read(authRepositoryProvider).requestEmailLink(_emailCtrl.text.trim());
      setState(() {
        _requested = true;
        _devToken = out.devToken;
      });
    } catch (_) {
      setState(() => _error = 'Impossible d\'envoyer le lien pour le moment.');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _verify() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authSessionProvider.notifier).loginWithEmail(
            email: _emailCtrl.text.trim(),
            token: EmailToken.normalize(_tokenCtrl.text),
          );
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      setState(() => _error = 'Code invalide ou expiré.');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData('text/plain');
    final text = data?.text;
    if (text != null && text.isNotEmpty) {
      _tokenCtrl.text = text.trim();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Connexion Email')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _emailCtrl,
            keyboardType: TextInputType.emailAddress,
            decoration: const InputDecoration(labelText: 'Email'),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _loading ? null : _requestLink,
            child: Text(_requested ? 'Renvoyer un lien' : 'Recevoir un lien magique'),
          ),
          if (_requested) ...[
            const SizedBox(height: 16),
            TextField(
              controller: _tokenCtrl,
              decoration: const InputDecoration(labelText: 'Code / token'),
            ),
            if (kDebugMode)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: _paste,
                  child: const Text('Coller depuis presse-papier'),
                ),
              ),
            if (kDebugMode && _devToken != null)
              SelectableText('DEV token: $_devToken', style: const TextStyle(color: Colors.orangeAccent)),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _loading ? null : _verify,
              child: const Text('Vérifier'),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.redAccent)),
          ],
          if (_loading) const Padding(padding: EdgeInsets.only(top: 12), child: Center(child: CircularProgressIndicator())),
        ],
      ),
    );
  }
}
