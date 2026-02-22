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
  int _cooldown = 0;

  Future<void> _requestCode() async {
    if (_cooldown > 0) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final email = _emailCtrl.text.trim();
    if (kDebugMode) {
      debugPrint('[auth][otp] request -> POST /auth/email/request_otp body={"email":"$email"}');
    }
    try {
      final out = await ref.read(authRepositoryProvider).requestEmailOtp(email);
      if (kDebugMode) {
        debugPrint('[auth][otp] request <- success expires=${out.expiresInSeconds}s cooldown=${out.resendCooldownSeconds}s');
      }
      setState(() {
        _requested = true;
        _devToken = out.devToken;
        _cooldown = out.resendCooldownSeconds;
      });
      _tickCooldown();
    } catch (_) {
      setState(() => _error = 'Impossible d\'envoyer le code.');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _tickCooldown() async {
    while (mounted && _cooldown > 0) {
      await Future<void>.delayed(const Duration(seconds: 1));
      if (!mounted) return;
      setState(() => _cooldown = (_cooldown - 1).clamp(0, 999));
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
      appBar: AppBar(title: const Text('Créer compte / Se connecter')),
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
            onPressed: _loading || _cooldown > 0 ? null : _requestCode,
            child: Text(_requested ? (_cooldown > 0 ? 'Renvoyer (${_cooldown}s)' : 'Renvoyer un code') : 'Recevoir un code'),
          ),
          const SizedBox(height: 8),
          const ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text('Continuer avec téléphone (bientôt)'),
            subtitle: Text('Disponible prochainement'),
          ),
          const ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            title: Text('WhatsApp (bientôt)'),
            subtitle: Text('Disponible prochainement'),
          ),
          if (_requested) ...[
            const SizedBox(height: 16),
            TextField(
              controller: _tokenCtrl,
              keyboardType: TextInputType.number,
              maxLength: 6,
              decoration: const InputDecoration(labelText: 'Code 6 chiffres'),
            ),
            const Text('Le code expire en 10 minutes.'),
            if (kDebugMode)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: _paste,
                  child: const Text('Coller depuis presse-papier'),
                ),
              ),
            if (kDebugMode && _devToken != null)
              SelectableText('DEV code: $_devToken', style: const TextStyle(color: Colors.orangeAccent)),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: _loading ? null : _verify,
              child: const Text('Vérifier code'),
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
