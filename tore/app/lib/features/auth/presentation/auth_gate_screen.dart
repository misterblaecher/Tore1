import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../ui/app_design_system.dart';
import '../../../app_shell.dart';
import 'email_auth_screen.dart';

class AuthGateScreen extends ConsumerStatefulWidget {
  const AuthGateScreen({super.key});

  @override
  ConsumerState<AuthGateScreen> createState() => _AuthGateScreenState();
}

class _AuthGateScreenState extends ConsumerState<AuthGateScreen> {
  bool _loadingGuest = false;
  String? _error;

  Future<void> _continueGuest() async {
    setState(() {
      _error = null;
      _loadingGuest = true;
    });
    try {
      await ref.read(authSessionProvider.notifier).continueAsGuest();
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AppShell()),
      );
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Impossible de continuer en invité pour le moment.');
    } finally {
      if (mounted) setState(() => _loadingGuest = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF08080C),
      body: SolarBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(),
              Image.asset('assets/branding/logo_minimal.png', height: 70, errorBuilder: (_, __, ___) => const Icon(Icons.bolt, size: 52, color: AppColors.accentGold)),
              const SizedBox(height: 18),
              const Text('TORÈ', textAlign: TextAlign.center, style: AppTextStyles.massiveTitle),
              const SizedBox(height: 8),
              const Text('Territorial OS', textAlign: TextAlign.center, style: AppTextStyles.muted),
              const SizedBox(height: 28),
              if (_error != null) ...[
                Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.redAccent)),
                const SizedBox(height: 10),
              ],
              PrimaryButton(
                label: 'Créer un compte / Se connecter',
                icon: Icons.mark_email_read_outlined,
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const EmailAuthScreen()),
                ),
              ),
              const SizedBox(height: 10),
              SecondaryButton(
                label: _loadingGuest ? 'Chargement...' : 'Continuer en invité',
                icon: Icons.person_outline,
                onPressed: _loadingGuest ? null : _continueGuest,
              ),
              const SizedBox(height: 8),
              const Text(
                'Le mode invité donne un accès limité. Connecte-toi pour débloquer le profil et toutes les actions.',
                textAlign: TextAlign.center,
                style: AppTextStyles.muted,
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
      ),
    );
  }
}
