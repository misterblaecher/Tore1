import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_repository.dart';
import '../../../core/auth/email_token.dart';
import '../../../core/auth/providers.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../ui/app_design_system.dart';

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
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      setState(() => _error = 'Hors-ligne. Vérifie ta connexion.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final out = await ref.read(authRepositoryProvider).requestEmailOtp(_emailCtrl.text.trim());
      setState(() {
        _requested = true;
        _devToken = out.devToken;
        _cooldown = out.resendCooldownSeconds;
      });
      _tickCooldown();
    } on EmailRateLimitException catch (e) {
      setState(() {
        _requested = true;
        _cooldown = e.retryAfterSeconds;
        _error = 'Trop de tentatives. Réessaie dans ${e.retryAfterSeconds} secondes.';
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
      await ref.read(authSessionProvider.notifier).loginWithEmail(email: _emailCtrl.text.trim(), token: EmailToken.normalize(_tokenCtrl.text));
      if (mounted) Navigator.of(context).pop();
    } on DioException {
      setState(() => _error = 'Hors-ligne. Vérifie ta connexion.');
    } catch (_) {
      setState(() => _error = 'Code invalide ou expiré.');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Créer compte / Se connecter')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          const SectionTitle('Connexion email'),
          AppCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              TextField(controller: _emailCtrl, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
              const SizedBox(height: AppSpacing.sm),
              PrimaryButton(
                label: _requested ? (_cooldown > 0 ? 'Renvoyer (${_cooldown}s)' : 'Renvoyer un code') : 'Recevoir un code',
                icon: Icons.mail_outline,
                loading: _loading,
                onPressed: _loading || _cooldown > 0 || ref.watch(networkStatusProvider) != NetworkState.online ? null : _requestCode,
              ),
              if (_requested) ...[
                const SizedBox(height: AppSpacing.md),
                TextField(controller: _tokenCtrl, keyboardType: TextInputType.number, maxLength: 6, decoration: const InputDecoration(labelText: 'Code 6 chiffres')),
                PrimaryButton(label: 'Vérifier code', icon: Icons.verified_outlined, loading: _loading, onPressed: _verify),
              ],
              if (kDebugMode && _devToken != null) ...[
                const SizedBox(height: AppSpacing.sm),
                SelectableText('DEV code: $_devToken', style: const TextStyle(color: Colors.orangeAccent)),
              ],
              if (_error != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ],
              if (_loading) const Padding(padding: EdgeInsets.only(top: AppSpacing.sm), child: Center(child: CircularProgressIndicator())),
            ]),
          ),
          const SizedBox(height: AppSpacing.sm),
          const AppCard(child: Text('Téléphone / WhatsApp bientôt disponibles.')),
          if (kDebugMode)
            SecondaryButton(
              label: 'Coller code depuis presse-papier',
              icon: Icons.content_paste,
              onPressed: () async {
                final data = await Clipboard.getData('text/plain');
                final text = data?.text;
                if (text != null && text.isNotEmpty) _tokenCtrl.text = text.trim();
              },
            ),
        ],
      ),
    );
  }
}
