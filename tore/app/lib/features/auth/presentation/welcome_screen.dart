import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../shared/widgets/network_banner.dart';
import 'email_auth_screen.dart';

class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  bool _loadingGuest = false;
  bool _loadingGoogle = false;
  String? _error;

  Future<void> _continueGuest() async {
    setState(() {
      _error = null;
      _loadingGuest = true;
    });
    try {
      await ref.read(authSessionProvider.notifier).continueAsGuest();
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Impossible de démarrer le mode invité.');
    } finally {
      if (mounted) setState(() => _loadingGuest = false);
    }
  }

  Future<void> _continueGoogle() async {
    setState(() {
      _error = null;
      _loadingGoogle = true;
    });
    try {
      await ref.read(authSessionProvider.notifier).loginWithGoogle();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loadingGoogle = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            const ToreNetworkBanner(),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Spacer(),
                    Text('TORÈ',
                        style: Theme.of(context).textTheme.headlineMedium,
                        textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    const Text('Choisis une méthode de connexion.',
                        textAlign: TextAlign.center),
                    const Spacer(),
                    if (_error != null) ...[
                      Text(_error!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.redAccent)),
                      const SizedBox(height: 8),
                    ],
                    FilledButton(
                      onPressed: _loadingGuest ? null : _continueGuest,
                      child: _loadingGuest
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Continuer en invité'),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton(
                      onPressed: _loadingGoogle ? null : _continueGoogle,
                      child: _loadingGoogle
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Text('Continuer avec Google'),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).push(
                          MaterialPageRoute(
                              builder: (_) => const EmailAuthScreen())),
                      child: const Text('Continuer par Email (OTP)'),
                    ),
                    const SizedBox(height: 10),
                    const OutlinedButton(
                      onPressed: null,
                      child: Text('Continuer avec téléphone (bientôt)'),
                    ),
                    const SizedBox(height: 10),
                    const OutlinedButton(
                      onPressed: null,
                      child: Text('WhatsApp (bientôt)'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
