import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';

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
    final display = _displayCtrl.text.trim();
    if (display.isEmpty) {
      setState(() => _error = 'Le pseudo est obligatoire.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authRepositoryProvider).patchMe(displayName: display, bio: _bioCtrl.text.trim());
      ref.invalidate(meProvider);
      if (!mounted) return;
      Navigator.of(context).pop();
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Impossible de sauvegarder. Réessaie.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Compléter profil')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Avant de continuer, ajoute un pseudo.'),
          const SizedBox(height: 12),
          TextField(controller: _displayCtrl, enabled: !_loading, decoration: const InputDecoration(labelText: 'Pseudo *')),
          const SizedBox(height: 10),
          TextField(controller: _bioCtrl, enabled: !_loading, maxLines: 3, decoration: const InputDecoration(labelText: 'Bio (optionnel)')),
          const SizedBox(height: 16),
          FilledButton(onPressed: _loading ? null : _submit, child: Text(_loading ? 'Sauvegarde...' : 'Continuer')),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: const TextStyle(color: Colors.redAccent)),
          ],
        ],
      ),
    );
  }
}
