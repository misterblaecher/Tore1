import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../ui/app_design_system.dart';

class CompleteProfileScreen extends ConsumerStatefulWidget {
  const CompleteProfileScreen({super.key});

  @override
  ConsumerState<CompleteProfileScreen> createState() => _CompleteProfileScreenState();
}

class _CompleteProfileScreenState extends ConsumerState<CompleteProfileScreen> {
  final _displayCtrl = TextEditingController();
  final _bioCtrl = TextEditingController();
  bool _loading = false;
  String? _error;

  Future<void> _submit() async {
    if (_displayCtrl.text.trim().isEmpty) {
      setState(() => _error = 'Le pseudo est obligatoire.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authRepositoryProvider).patchMe(displayName: _displayCtrl.text.trim(), bio: _bioCtrl.text.trim());
      ref.invalidate(meProvider);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted) setState(() => _error = 'Impossible de sauvegarder. Réessaie.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Compléter profil')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          const AppCard(child: Text('Avant de continuer, ajoute un pseudo.')),
          const SizedBox(height: AppSpacing.sm),
          AppCard(
            child: Column(
              children: [
                TextField(controller: _displayCtrl, enabled: !_loading, decoration: const InputDecoration(labelText: 'Pseudo *')),
                const SizedBox(height: AppSpacing.sm),
                TextField(controller: _bioCtrl, enabled: !_loading, maxLines: 3, decoration: const InputDecoration(labelText: 'Bio (optionnel)')),
                const SizedBox(height: AppSpacing.md),
                PrimaryButton(label: _loading ? 'Sauvegarde...' : 'Continuer', onPressed: _loading ? null : _submit, loading: _loading),
                if (_error != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_error!, style: const TextStyle(color: Colors.redAccent))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
