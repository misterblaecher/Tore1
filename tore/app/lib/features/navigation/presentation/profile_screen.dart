import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_models.dart';
import '../../../core/auth/providers.dart';
import '../../../ui/app_design_system.dart';
import '../../auth/presentation/complete_profile_screen.dart';
import '../../../shared/widgets/require_auth_sheet.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authSessionProvider);
    final meAsync = ref.watch(meProvider);

    if (session.isGuest) {
      final guestId = session.user?.id ?? 'guest';
      return Scaffold(
        appBar: AppBar(title: const Text('Profil')),
        backgroundColor: AppColors.backgroundPrimary,
        body: SolarBackground(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              ToreCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const ToreSectionHeader('Invité'),
                    Text(
                        'ID ${guestId.length > 14 ? guestId.substring(0, 14) : guestId}'),
                    const SizedBox(height: AppSpacing.md),
                    ToreButton.primary(
                      label: 'Se connecter',
                      icon: Icons.login,
                      onPressed: () => RequireAuthSheet.show(context),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              ToreButton.secondary(
                label: 'Quitter invité',
                icon: Icons.logout,
                onPressed: () =>
                    ref.read(authSessionProvider.notifier).logout(),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: meAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('Erreur profil: $e')),
          data: (me) {
            if (me.displayName.trim().isEmpty) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                      builder: (_) => const CompleteProfileScreen()),
                );
              });
              return const SizedBox.shrink();
            }
            return _AuthedProfile(me: me);
          },
        ),
      ),
    );
  }
}

class _AuthedProfile extends ConsumerWidget {
  const _AuthedProfile({required this.me});

  final AppUser me;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        ToreCard(
          child: Row(
            children: [
              Container(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                        color: AppColors.accentGold.withValues(alpha: 0.35),
                        blurRadius: 20)
                  ],
                ),
                child: CircleAvatar(
                  radius: 34,
                  backgroundImage:
                      (me.avatarUrl != null && me.avatarUrl!.isNotEmpty)
                          ? NetworkImage(me.avatarUrl!)
                          : null,
                  child: (me.avatarUrl == null || me.avatarUrl!.isEmpty)
                      ? Text(me.displayName.substring(0, 1).toUpperCase(),
                          style: const TextStyle(fontWeight: FontWeight.w700))
                      : null,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(me.displayName,
                        style: Theme.of(context).textTheme.titleLarge),
                    if (me.bio.trim().isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: AppSpacing.xs),
                        child: Text(me.bio, style: AppTextStyles.muted),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        const ToreSectionHeader('Réglages'),
        ToreCard(
          child: Column(
            children: [
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: me.showAvatar,
                title: const Text('Thème: halo avatar'),
                subtitle: const Text('Option visuelle légère.'),
                onChanged: (v) =>
                    ref.read(authRepositoryProvider).patchMe(showAvatar: v),
              ),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: me.showIdentityToStaff,
                title: const Text('Confidentialité staff'),
                onChanged: (v) => ref
                    .read(authRepositoryProvider)
                    .patchMe(showIdentityToStaff: v),
              ),
              const SizedBox(height: AppSpacing.sm),
              ToreButton.secondary(
                label: 'Déconnexion',
                icon: Icons.logout,
                onPressed: () =>
                    ref.read(authSessionProvider.notifier).logout(),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
