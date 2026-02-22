import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../core/auth/auth_models.dart';
import '../../../core/app_context/app_context.dart';
import '../../../state.dart';
import '../../../core/network/api_exception.dart';
import '../../events/presentation/event_manage_landing_screen.dart';
import '../../events/presentation/event_hub_screen.dart';
import '../../community/community_models.dart';
import '../../auth/presentation/email_auth_screen.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  String? _sessionToken;
  Timer? _pendingPoll;
  String _idem() => "profile-v2-${DateTime.now().millisecondsSinceEpoch}";

  @override
  void initState() {
    super.initState();
    _loadSessionToken();
  }

  Future<void> _loadSessionToken() async {
    final token = await ref.read(authRepositoryProvider).api.tokenStorage.readToken();
    if (!mounted) return;
    setState(() => _sessionToken = token);
  }

  void _syncPendingPoll(AppUser? me) {
    final shouldPoll = me?.roleRequestPending != null;
    if (!shouldPoll) {
      _pendingPoll?.cancel();
      _pendingPoll = null;
      return;
    }
    if (_pendingPoll != null) return;
    _pendingPoll = Timer.periodic(const Duration(seconds: 50), (_) {
      ref.invalidate(meProvider);
    });
  }

  @override
  void dispose() {
    _pendingPoll?.cancel();
    super.dispose();
  }

  Future<void> _patchPreference(Future<void> Function() action, String okMessage) async {
    try {
      await action();
      ref.invalidate(meProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(okMessage)));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Erreur réseau, réessaie.')),
      );
    }
  }


  Future<String?> _askUpgradeCode(AccountMode mode) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text('Code ${mode == AccountMode.organizer ? 'Organisateur' : 'Équipe'}'),
        content: TextField(
          controller: controller,
          obscureText: true,
          decoration: const InputDecoration(hintText: 'Entrer le code'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.of(context).pop(controller.text.trim()), child: const Text('Envoyer')),
        ],
      ),
    );
    controller.dispose();
    return result;
  }

  Future<void> _upgradeGuestAccount() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Sauvegarder mon compte', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () async {
                  Navigator.of(context).pop();
                  try {
                    await ref.read(authSessionProvider.notifier).loginWithGoogle();
                    await _runGuestUpgradeBestEffort();
                  } catch (_) {
                    if (!mounted) return;
                    ScaffoldMessenger.of(this.context).showSnackBar(const SnackBar(content: Text('Google indisponible, essaie Email.')));
                  }
                },
                child: const Text('Continuer avec Google'),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () async {
                  Navigator.of(context).pop();
                  await Navigator.of(this.context).push(MaterialPageRoute(builder: (_) => const EmailAuthScreen()));
                  await _runGuestUpgradeBestEffort();
                },
                child: const Text('Continuer par Email'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _runGuestUpgradeBestEffort() async {
    final repo = ref.read(authRepositoryProvider);
    final guestId = await repo.api.tokenStorage.readGuestDeviceId();
    if (guestId != null && guestId.isNotEmpty) {
      try {
        await repo.upgradeGuest(guestDeviceId: guestId);
      } catch (_) {}
    }
    ref.invalidate(meProvider);
    ref.invalidate(authSessionProvider);
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authSessionProvider);
    final meAsync = ref.watch(meProvider);
    final ctx = ref.watch(appContextProvider);
    final runtimeStateAsync = ctx.hasActiveEvent
        ? ref.watch(_profileEventProvider(ctx.activeEventId!))
        : const AsyncValue<String>.data('N/A');

    _syncPendingPoll(meAsync.valueOrNull);


    if (session.status == AuthStatus.unauthenticated) {
      return _LoginRequiredView(
        title: 'Profil',
        message: 'Connecte-toi pour voir ton profil.',
      );
    }

    if (session.isGuest) {
      return Scaffold(
        appBar: AppBar(title: const Text('Profil')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: Colors.orange.withOpacity(0.15),
              child: ListTile(
                title: const Text('Tu es en invité — sauvegarde ton compte'),
                subtitle: const Text('Pour conserver ton profil et tes actions.'),
                trailing: FilledButton(onPressed: _upgradeGuestAccount, child: const Text('Sauvegarder')),
              ),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () async => ref.read(authSessionProvider.notifier).logout(),
              icon: const Icon(Icons.logout),
              label: const Text('Se déconnecter'),
            ),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      body: meAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) {
          final isUnauthorized = e is ApiException && (e.statusCode == 401 || e.statusCode == 403);
          if (isUnauthorized) {
            return const _LoginRequiredBody(message: 'Connecte-toi pour voir ton profil.');
          }
          return Center(child: Text('Erreur: $e'));
        },
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
                      const Text('Mode de compte', style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      if (me.roleRequestPending != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text('Demande en attente: ${me.roleRequestPending!.requestedMode.name}'),
                        ),
                      Wrap(
                        spacing: 8,
                        children: [
                          (AccountMode.user, 'Utilisateur'),
                          (AccountMode.organizer, 'Organisateur'),
                          (AccountMode.team, 'Équipe'),
                        ].map((entry) {
                          return ChoiceChip(
                            label: Text(entry.$2),
                            selected: me.accountMode == entry.$1,
                            onSelected: (_) async {
                              if (entry.$1 == AccountMode.user) {
                                await _patchPreference(
                                  () => ref.read(authRepositoryProvider).patchMe(accountMode: AccountMode.user),
                                  'Mode utilisateur activé',
                                );
                                return;
                              }
                              final code = await _askUpgradeCode(entry.$1);
                              if (code == null || code.isEmpty) return;
                              await _patchPreference(
                                () => ref.read(authRepositoryProvider).requestRoleUpgrade(mode: entry.$1, code: code),
                                'Demande envoyée: en attente de validation admin',
                              );
                            },
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),
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
                        onChanged: (v) => _patchPreference(
                          () => ref.read(authRepositoryProvider).patchMe(showAvatar: v),
                          'Préférence enregistrée',
                        ),
                      ),
                      SwitchListTile.adaptive(
                        value: me.showAddress,
                        title: const Text('Afficher mon adresse'),
                        onChanged: (v) => _patchPreference(
                          () => ref.read(authRepositoryProvider).patchMe(showAddress: v),
                          'Préférence enregistrée',
                        ),
                      ),
                      SwitchListTile.adaptive(
                        value: me.showIdentityToStaff,
                        title: const Text("Autoriser l'affichage de mon identité au staff"),
                        subtitle: const Text('Visible seulement si le bar active aussi ce mode.'),
                        onChanged: (v) => _patchPreference(
                          () => ref.read(authRepositoryProvider).patchMe(showIdentityToStaff: v),
                          'Consentement enregistré',
                        ),
                      ),
                      SwitchListTile.adaptive(
                        value: me.showIdentityInBar,
                        title: const Text('Visible dans ce bar'),
                        onChanged: (v) => _patchPreference(
                          () => ref.read(authRepositoryProvider).patchMe(showIdentityInBar: v),
                          'Visibilité bar mise à jour',
                        ),
                      ),
                      const SizedBox(height: 6),
                      Wrap(
                        spacing: 8,
                        children: [
                          ChoiceChip(
                            label: const Text('Public'),
                            selected: me.visibility == 'public',
                            onSelected: (_) => _patchPreference(
                              () => ref.read(authRepositoryProvider).patchMe(visibility: 'public'),
                              'Profil public',
                            ),
                          ),
                          ChoiceChip(
                            label: const Text('Privé'),
                            selected: me.visibility == 'private',
                            onSelected: (_) => _patchPreference(
                              () => ref.read(authRepositoryProvider).patchMe(visibility: 'private'),
                              'Profil privé',
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),
              if (ctx.hasActiveEvent)
                Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.event_available_outlined),
                        title: const Text('Event en cours'),
                        subtitle: Text(ctx.activeEventName ?? 'Event #${ctx.activeEventId}'),
                      ),
                      ListTile(
                        leading: const Icon(Icons.info_outline),
                        title: const Text('État runtime'),
                        subtitle: Text(runtimeStateAsync.maybeWhen(data: (v) => v, orElse: () => 'LIVE')),
                      ),
                      ListTile(
                        leading: const Icon(Icons.logout),
                        title: const Text('Quitter l’event'),
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
                    ],
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
                        label: 'Bio courte',
                        initialValue: me.bio ?? '',
                        onSave: (v) async {
                          final repo = ref.read(authRepositoryProvider);
                          await repo.patchMe(bio: v);
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


              const SizedBox(height: 12),
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Historique', style: TextStyle(fontWeight: FontWeight.w700)),
                      SizedBox(height: 6),
                      Text('Events / Gains bets / Hunts: bientôt (module OFF par défaut).'),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 12),
              FutureBuilder<MyEventsFetchResult>(
                future: ref.read(apiProvider).myEvents(),
                builder: (context, snap) {
                  final result = snap.data;
                  final buckets = result?.buckets ?? const <String, List<MyEventSummary>>{};
                  final allItems = [
                    ...?buckets['LIVE'],
                    ...?buckets['TODAY'],
                    ...?buckets['UPCOMING'],
                    ...?buckets['PAST'],
                  ];
                  if (snap.connectionState == ConnectionState.waiting && result == null) {
                    return const Card(child: Padding(padding: EdgeInsets.all(14), child: Center(child: CircularProgressIndicator())));
                  }
                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Mes Events', style: TextStyle(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 6),
                          Text('LIVE ${buckets['LIVE']?.length ?? 0} • TODAY ${buckets['TODAY']?.length ?? 0} • UPCOMING ${buckets['UPCOMING']?.length ?? 0} • PAST ${buckets['PAST']?.length ?? 0}'),
                          if (result != null)
                            Container(
                              margin: const EdgeInsets.only(top: 8),
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: result.fromCache ? Colors.amber.withOpacity(0.2) : Colors.green.withOpacity(0.12),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                result.fromCache
                                    ? 'Cache (TTL 24h) • dernière synchro: ${_fmt(result.lastSyncAt)}'
                                    : 'Sync live • ${_fmt(result.lastSyncAt)}',
                                style: const TextStyle(fontSize: 12),
                              ),
                            ),
                          const SizedBox(height: 8),
                          if (allItems.isEmpty) const Text('Aucun event pertinent.'),
                          for (final e in allItems.take(12))
                            ListTile(
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                              title: Text(e.name),
                              subtitle: Text('${e.roleForMe} • ${e.visibility} • ${e.status}'),
                              trailing: e.canManage ? const Icon(Icons.chevron_right) : null,
                              onTap: () {
                                final route = e.joined
                                    ? MaterialPageRoute(builder: (_) => EventHubScreen(eventId: e.id, eventName: e.name))
                                    : MaterialPageRoute(builder: (_) => EventManageLandingScreen(event: e));
                                Navigator.of(context).push(route);
                              },
                            ),
                        ],
                      ),
                    ),
                  );
                },
              ),

              const SizedBox(height: 12),
              FutureBuilder<Map<String, dynamic>>(
                future: ref.read(apiProvider).myProfileV2(),
                builder: (context, snap) {
                  final profile = snap.data ?? const <String, dynamic>{};
                  final orgas = ((profile['orgas'] as List?) ?? const []).cast<dynamic>();
                  final events = ((profile['events'] as List?) ?? const []).cast<dynamic>();
                  return Card(
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Profil V2', style: TextStyle(fontWeight: FontWeight.w700)),
                          const SizedBox(height: 8),
                          _EditField(
                            label: 'Pseudo (obligatoire)',
                            initialValue: (profile['display_name'] ?? me.displayName).toString(),
                            onSave: (v) async {
                              await ref.read(apiProvider).updateMyProfileV2(displayName: v, bio: profile['bio']?.toString(), instagramHandle: profile['instagram_handle']?.toString(), photoUrl: profile['photo_url']?.toString(), visibility: (profile['visibility'] ?? 'PUBLIC').toString(), idempotencyKey: _idem());
                            },
                          ),
                          const SizedBox(height: 10),
                          _EditField(
                            label: 'Bio',
                            initialValue: (profile['bio'] ?? '').toString(),
                            onSave: (v) async {
                              await ref.read(apiProvider).updateMyProfileV2(displayName: (profile['display_name'] ?? me.displayName).toString(), bio: v, instagramHandle: profile['instagram_handle']?.toString(), photoUrl: profile['photo_url']?.toString(), visibility: (profile['visibility'] ?? 'PUBLIC').toString(), idempotencyKey: _idem());
                            },
                          ),
                          const SizedBox(height: 10),
                          Text('Mes orgas (${orgas.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
                          for (final o in orgas.take(3)) Text('• ${(o as Map)['name']} (${o['role']})'),
                          const SizedBox(height: 8),
                          Text('Mes events (${events.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
                          for (final e in events.take(3)) Text('• ${(e as Map)['name']}'),
                        ],
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Diagnostics', style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      OutlinedButton.icon(
                        onPressed: () async {
                          final value = (_sessionToken != null && _sessionToken!.isNotEmpty) ? _sessionToken! : me.id;
                          await Clipboard.setData(ClipboardData(text: value));
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text(value == me.id ? 'User ID copié' : 'Token session copié')),
                          );
                        },
                        icon: const Icon(Icons.copy_all_outlined),
                        label: Text((_sessionToken != null && _sessionToken!.isNotEmpty) ? 'Copier mon token session' : 'Copier mon user id'),
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

  static String _fmt(DateTime? dt) {
    if (dt == null) return '-';
    final local = dt.toLocal();
    return '${local.day.toString().padLeft(2, '0')}/${local.month.toString().padLeft(2, '0')} ${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
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


class _LoginRequiredView extends StatelessWidget {
  const _LoginRequiredView({required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: _LoginRequiredBody(message: message),
    );
  }
}

class _LoginRequiredBody extends StatelessWidget {
  const _LoginRequiredBody({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EmailAuthScreen())),
              child: const Text('Se connecter'),
            ),
          ],
        ),
      ),
    );
  }
}

final _profileEventProvider = FutureProvider.family<String, int>((ref, eventId) async {
  final event = await ref.read(apiProvider).event(eventId);
  return (event['runtime_state'] ?? event['state'] ?? event['status'] ?? 'LIVE').toString().toUpperCase();
});

class _EditField extends ConsumerStatefulWidget {
  final String label;
  final String initialValue;
  final Future<void> Function(String value) onSave;

  const _EditField({
    required this.label,
    required this.initialValue,
    required this.onSave,
  });

  @override
  ConsumerState<_EditField> createState() => _EditFieldState();
}

class _EditFieldState extends ConsumerState<_EditField> {
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

  Future<void> _upgradeGuestAccount() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Sauvegarder mon compte', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: () async {
                  Navigator.of(context).pop();
                  try {
                    await ref.read(authSessionProvider.notifier).loginWithGoogle();
                    await _runGuestUpgradeBestEffort();
                  } catch (_) {
                    if (!mounted) return;
                    ScaffoldMessenger.of(this.context).showSnackBar(const SnackBar(content: Text('Google indisponible, essaie Email.')));
                  }
                },
                child: const Text('Continuer avec Google'),
              ),
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () async {
                  Navigator.of(context).pop();
                  await Navigator.of(this.context).push(MaterialPageRoute(builder: (_) => const EmailAuthScreen()));
                  await _runGuestUpgradeBestEffort();
                },
                child: const Text('Continuer par Email'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _runGuestUpgradeBestEffort() async {
    final repo = ref.read(authRepositoryProvider);
    final guestId = await repo.api.tokenStorage.readGuestDeviceId();
    if (guestId != null && guestId.isNotEmpty) {
      try {
        await repo.upgradeGuest(guestDeviceId: guestId);
      } catch (_) {}
    }
    ref.invalidate(meProvider);
    ref.invalidate(authSessionProvider);
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
