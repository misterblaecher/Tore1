import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../core/auth/auth_repository.dart';
import '../../../core/app_context/app_context.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meAsync = ref.watch(meProvider);
    final ctx = ref.watch(appContextProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      body: meAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Erreur: $e')),
        data: (me) {
          final initials = _initials(me.displayName, me.id);

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundImage:
                        (me.avatarUrl != null && me.avatarUrl!.isNotEmpty) ? NetworkImage(me.avatarUrl!) : null,
                    child: (me.avatarUrl == null || me.avatarUrl!.isEmpty)
                        ? Text(initials, style: const TextStyle(fontWeight: FontWeight.w800))
                        : null,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          me.displayName.isEmpty ? 'Utilisateur' : me.displayName,
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 2),
                        Text('User #${me.id.length >= 4 ? me.id.substring(0, 4).toUpperCase() : me.id}'),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),

              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Confidentialité', style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      SwitchListTile.adaptive(
                        value: me.showAvatar,
                        title: const Text('Afficher mon avatar'),
                        onChanged: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          try {
                            await repo.patchMe(showAvatar: v);
                            ref.invalidate(meProvider);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Préférence enregistrée')),
                              );
                            }
                          } catch (_) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Erreur réseau, réessaie.')),
                              );
                            }
                          }
                        },
                      ),
                      SwitchListTile.adaptive(
                        value: me.showAddress,
                        title: const Text('Afficher mon adresse'),
                        onChanged: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          try {
                            await repo.patchMe(showAddress: v);
                            ref.invalidate(meProvider);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Préférence enregistrée')),
                              );
                            }
                          } catch (_) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Erreur réseau, réessaie.')),
                              );
                            }
                          }
                        },
                      ),
                      SwitchListTile.adaptive(
                        value: me.showIdentityToStaff,
                        title: const Text("Autoriser l'affichage de mon identité au staff"),
                        subtitle: const Text('Visible seulement si le bar active aussi ce mode.'),
                        onChanged: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          try {
                            await repo.patchMe(showIdentityToStaff: v);
                            ref.invalidate(meProvider);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Consentement enregistré')),
                              );
                            }
                          } catch (_) {
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Erreur réseau, réessaie.')),
                              );
                            }
                          }
                        },
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),
              if (ctx.hasActiveEvent)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Quitter l’event'),
                    subtitle: Text(ctx.activeEventName ?? 'Event #${ctx.activeEventId}'),
                    onTap: () async {
                      final ok = await showDialog<bool>(
                            context: context,
                            builder: (_) => AlertDialog(
                              title: const Text('Quitter l’event ?'),
                              actions: [
                                TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Annuler')),
                                FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Quitter')),
                              ],
                            ),
                          ) ??
                          false;
                      if (ok) {
                        ref.read(appContextProvider.notifier).leaveEvent();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Event quitté.')));
                        }
                      }
                    },
                  ),
                ),
              if (ctx.hasActiveEvent) const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Modifier profil', style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      _EditField(
                        label: 'Pseudo',
                        initialValue: me.displayName,
                        onSave: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          await repo.patchMe(displayName: v);
                          ref.invalidate(meProvider);
                        },
                      ),
                      const SizedBox(height: 10),
                      _EditField(
                        label: 'Avatar URL',
                        initialValue: me.avatarUrl ?? '',
                        onSave: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          await repo.patchMe(avatarUrl: v);
                          ref.invalidate(meProvider);
                        },
                      ),
                      const SizedBox(height: 10),
                      _EditField(
                        label: 'Adresse',
                        initialValue: me.addressText ?? '',
                        onSave: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          await repo.patchMe(addressText: v);
                          ref.invalidate(meProvider);
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  static String _initials(String displayName, String id) {
    final trimmed = displayName.trim();
    if (trimmed.isEmpty) {
      return id.isNotEmpty ? id.substring(0, 1).toUpperCase() : '?';
    }
    final parts = trimmed.split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    final a = parts.isNotEmpty ? parts[0][0].toUpperCase() : '?';
    final b = parts.length >= 2 ? parts[1][0].toUpperCase() : '';
    return (a + b).trim();
  }
}

class _EditField extends StatefulWidget {
  final String label;
  final String initialValue;
  final Future<void> Function(String value) onSave;

  const _EditField({
    required this.label,
    required this.initialValue,
    required this.onSave,
  });

  @override
  State<_EditField> createState() => _EditFieldState();
}

class _EditFieldState extends State<_EditField> {
  late final TextEditingController _ctrl;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: TextField(
            controller: _ctrl,
            decoration: InputDecoration(labelText: widget.label),
          ),
        ),
        const SizedBox(width: 10),
        ElevatedButton(
          onPressed: _saving
              ? null
              : () async {
                  setState(() => _saving = true);
                  try {
                    await widget.onSave(_ctrl.text.trim());
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('${widget.label} enregistré')),
                      );
                    }
                  } finally {
                    if (mounted) setState(() => _saving = false);
                  }
                },
          child: _saving ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('OK'),
        ),
      ],
    );
  }
}
