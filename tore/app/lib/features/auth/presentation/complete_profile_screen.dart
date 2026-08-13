import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_models.dart';
import '../../../core/auth/providers.dart';
import '../../../ui/app_design_system.dart';

class CompleteProfileScreen extends ConsumerStatefulWidget {
  const CompleteProfileScreen({super.key, this.user});

  final AppUser? user;

  @override
  ConsumerState<CompleteProfileScreen> createState() =>
      _CompleteProfileScreenState();
}

class _CompleteProfileScreenState extends ConsumerState<CompleteProfileScreen> {
  final _displayCtrl = TextEditingController();
  final _bioCtrl = TextEditingController();
  final _avatarCtrl = TextEditingController();
  String _visibility = 'public';
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _displayCtrl.text = widget.user?.displayName ?? '';
    _bioCtrl.text = widget.user?.bio ?? '';
    _avatarCtrl.text = widget.user?.avatarUrl ?? '';
    _visibility = widget.user?.visibility ?? 'public';
  }

  @override
  void dispose() {
    _displayCtrl.dispose();
    _bioCtrl.dispose();
    _avatarCtrl.dispose();
    super.dispose();
  }

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
      await ref.read(authRepositoryProvider).patchMe(
            displayName: _displayCtrl.text.trim(),
            bio: _bioCtrl.text.trim(),
            avatarUrl: _avatarCtrl.text.trim(),
            visibility: _visibility,
          );
      ref.invalidate(meProvider);
      if (mounted) Navigator.of(context).pop();
    } catch (_) {
      if (mounted)
        setState(() => _error = 'Impossible de sauvegarder. Réessaie.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title:
            Text(widget.user == null ? 'Compléter profil' : 'Modifier profil'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          AppCard(
            child: Text(widget.user == null
                ? 'Avant de continuer, ajoute un pseudo.'
                : 'Ton pseudo et ta bio sont enregistrés dans ton profil TORÈ.'),
          ),
          const SizedBox(height: AppSpacing.sm),
          AppCard(
            child: Column(
              children: [
                TextField(
                    controller: _displayCtrl,
                    enabled: !_loading,
                    decoration: const InputDecoration(labelText: 'Pseudo *')),
                const SizedBox(height: AppSpacing.sm),
                TextField(
                    controller: _bioCtrl,
                    enabled: !_loading,
                    maxLines: 3,
                    decoration:
                        const InputDecoration(labelText: 'Bio (optionnel)')),
                const SizedBox(height: AppSpacing.sm),
                TextField(
                  controller: _avatarCtrl,
                  enabled: !_loading,
                  keyboardType: TextInputType.url,
                  decoration: const InputDecoration(
                    labelText: 'URL de la photo (optionnel)',
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                DropdownButtonFormField<String>(
                  initialValue: _visibility,
                  decoration: const InputDecoration(labelText: 'Visibilité'),
                  items: const [
                    DropdownMenuItem(value: 'public', child: Text('Public')),
                    DropdownMenuItem(
                      value: 'tore_users',
                      child: Text('Utilisateurs TORÈ'),
                    ),
                    DropdownMenuItem(value: 'private', child: Text('Privé')),
                  ],
                  onChanged: _loading
                      ? null
                      : (value) => setState(
                            () => _visibility = value ?? _visibility,
                          ),
                ),
                const SizedBox(height: AppSpacing.md),
                PrimaryButton(
                    label: _loading
                        ? 'Sauvegarde...'
                        : (widget.user == null ? 'Continuer' : 'Enregistrer'),
                    onPressed: _loading ? null : _submit,
                    loading: _loading),
                if (_error != null)
                  Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text(_error!,
                          style: const TextStyle(color: Colors.redAccent))),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
