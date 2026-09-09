import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../ui/app_design_system.dart';
import '../../community/presentation/orga_detail_screen.dart';
import '../../profile/data/profile_repository.dart';
import '../../profile/domain/profile_models.dart';
import '../../profile/presentation/profile_providers.dart';
import '../../../shared/widgets/require_auth_sheet.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authSessionProvider);
    if (session.isGuest) return const _GuestProfile();
    if (!session.isAuthed) {
      return _SessionExpiredProfile(message: session.message);
    }

    final profileAsync = ref.watch(ownerProfileProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profil TORÈ'),
        actions: [
          IconButton(
            tooltip: 'Actualiser',
            onPressed: () => _refresh(ref),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: profileAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => _ProfileError(
            error: error,
            onRetry: () => _refresh(ref),
          ),
          data: (result) => _OwnerProfileBody(result: result),
        ),
      ),
    );
  }

  static void _refresh(WidgetRef ref) {
    ref.invalidate(ownerProfileProvider);
    ref.invalidate(affiliationsProvider);
    ref.invalidate(effectiveCapabilitiesProvider);
  }
}

class _GuestProfile extends ConsumerWidget {
  const _GuestProfile();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
                  const ToreSectionHeader('Mode invité'),
                  const Text(
                    'Tu peux découvrir les événements et profils publics. Connecte-toi pour créer et modifier ton profil TORÈ.',
                  ),
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
              label: 'Quitter le mode invité',
              icon: Icons.logout,
              onPressed: () => ref.read(authSessionProvider.notifier).logout(),
            ),
          ],
        ),
      ),
    );
  }
}

class _SessionExpiredProfile extends StatelessWidget {
  const _SessionExpiredProfile({this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: ToreCard(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.lock_clock_outlined, size: 42),
                  const SizedBox(height: AppSpacing.sm),
                  Text(message ?? 'Ta session a expiré.'),
                  const SizedBox(height: AppSpacing.md),
                  ToreButton.primary(
                    label: 'Se reconnecter',
                    icon: Icons.login,
                    onPressed: () => RequireAuthSheet.show(context),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ProfileError extends StatelessWidget {
  const _ProfileError({required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: ToreCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 42),
              const SizedBox(height: AppSpacing.sm),
              const Text('Profil indisponible pour le moment.'),
              const SizedBox(height: AppSpacing.md),
              ToreButton.secondary(
                label: 'Réessayer',
                icon: Icons.refresh,
                onPressed: onRetry,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OwnerProfileBody extends ConsumerWidget {
  const _OwnerProfileBody({required this.result});

  final ProfileLoadResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = result.profile;
    final affiliations = ref.watch(affiliationsProvider);
    final capabilities = ref.watch(effectiveCapabilitiesProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ProfileScreen._refresh(ref);
        await ref.read(ownerProfileProvider.future);
      },
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (result.isFromCache)
            _OfflineCacheNotice(cachedAt: result.cachedAt),
          _IdentityCard(profile: profile),
          if (profile.isMinimal) ...[
            const SizedBox(height: AppSpacing.md),
            const _MinimalProfileNotice(),
          ],
          const SizedBox(height: AppSpacing.md),
          _ProfileActions(profile: profile),
          const SizedBox(height: AppSpacing.lg),
          const ToreSectionHeader('Affiliations'),
          affiliations.when(
            loading: () => const ToreCard(
                child: Center(child: CircularProgressIndicator())),
            error: (_, __) => const ToreCard(
                child: Text('Affiliations temporairement indisponibles.')),
            data: (items) => _AffiliationsList(items: items),
          ),
          const SizedBox(height: AppSpacing.lg),
          const ToreSectionHeader('Rôles et accès'),
          capabilities.when(
            loading: () => const ToreCard(
                child: Center(child: CircularProgressIndicator())),
            error: (_, __) => const ToreCard(
                child: Text('Les accès ne peuvent pas être vérifiés.')),
            data: (value) => _CapabilitiesCard(capabilities: value),
          ),
          if (profile.privacy?.eventHistoryOptIn == true) ...[
            const SizedBox(height: AppSpacing.lg),
            const ToreSectionHeader('Historique d’événements'),
            ToreCard(
              child: profile.eventHistory.isEmpty
                  ? const Text('Aucun événement visible dans ton historique.')
                  : Column(
                      children: profile.eventHistory
                          .map((event) => ListTile(
                                contentPadding: EdgeInsets.zero,
                                leading: const Icon(Icons.event_outlined),
                                title: Text((event['name'] ?? '').toString()),
                              ))
                          .toList(),
                    ),
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          const ToreSectionHeader('Compte'),
          ToreCard(
            child: ToreButton.secondary(
              label: 'Déconnexion',
              icon: Icons.logout,
              onPressed: () => ref.read(authSessionProvider.notifier).logout(),
            ),
          ),
        ],
      ),
    );
  }
}

class _OfflineCacheNotice extends StatelessWidget {
  const _OfflineCacheNotice({this.cachedAt});

  final DateTime? cachedAt;

  @override
  Widget build(BuildContext context) {
    final age = cachedAt == null
        ? null
        : DateTime.now().difference(cachedAt!).inMinutes.clamp(0, 99999);
    return Container(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadii.sm),
      ),
      child: Text(
        age == null
            ? 'Mode hors ligne · copie privée en cache'
            : 'Mode hors ligne · cache privé âgé de $age min',
      ),
    );
  }
}

class _IdentityCard extends StatelessWidget {
  const _IdentityCard({required this.profile});

  final ToreProfile profile;

  @override
  Widget build(BuildContext context) {
    final initial = profile.displayName.trim().isEmpty
        ? 'T'
        : profile.displayName.trim()[0].toUpperCase();
    return ToreCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 36,
            backgroundImage: profile.avatarUrl?.isNotEmpty == true
                ? NetworkImage(profile.avatarUrl!)
                : null,
            child: profile.avatarUrl?.isNotEmpty == true ? null : Text(initial),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                    profile.displayName.isEmpty
                        ? 'Profil minimal'
                        : profile.displayName,
                    style: Theme.of(context).textTheme.titleLarge),
                if (profile.username?.isNotEmpty == true)
                  Text('@${profile.username}', style: AppTextStyles.muted),
                if (profile.city?.isNotEmpty == true)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.xs),
                    child: Text(profile.city!, style: AppTextStyles.muted),
                  ),
                if (profile.bio.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.sm),
                    child: Text(profile.bio),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MinimalProfileNotice extends StatelessWidget {
  const _MinimalProfileNotice();

  @override
  Widget build(BuildContext context) => const ToreCard(
        child: Row(
          children: [
            Icon(Icons.info_outline),
            SizedBox(width: AppSpacing.sm),
            Expanded(
                child: Text(
                    'Choisis un pseudo unique pour compléter ton profil.')),
          ],
        ),
      );
}

class _ProfileActions extends ConsumerWidget {
  const _ProfileActions({required this.profile});

  final ToreProfile profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return ToreCard(
      child: Column(
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.edit_outlined),
            title: const Text('Modifier mon profil'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _edit(context, ref),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.visibility_outlined),
            title: const Text('Confidentialité'),
            subtitle: Text(_visibilityLabel(
                profile.privacy?.profile ?? ProfileVisibility.private)),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _privacy(context, ref),
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.preview_outlined),
            title: const Text('Aperçu de mon profil'),
            subtitle: const Text('Visiteur, utilisateur TORÈ ou propriétaire'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _preview(context, ref),
          ),
        ],
      ),
    );
  }

  Future<void> _edit(BuildContext context, WidgetRef ref) async {
    final values = await showDialog<Map<String, String>>(
      context: context,
      builder: (_) => _EditProfileDialog(profile: profile),
    );
    if (values == null || !context.mounted) return;
    try {
      await ref.read(profileRepositoryProvider).patchProfile(
            username: values['username'],
            displayName: values['display_name'],
            avatarUrl: values['avatar_url'],
            oripeaux: values['oripeaux'],
            bio: values['bio'],
            city: values['city'],
          );
      ProfileScreen._refresh(ref);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Profil enregistré sur TORÈ.')));
      }
    } on DioException catch (error) {
      if (!context.mounted) return;
      final conflict = error.response?.statusCode == 409;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(conflict
              ? 'Ce pseudo est déjà utilisé.'
              : 'Impossible d’enregistrer le profil.')));
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Impossible d’enregistrer le profil.')));
      }
    }
  }

  Future<void> _privacy(BuildContext context, WidgetRef ref) async {
    final current = profile.privacy;
    if (current == null) return;
    final values = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _PrivacyDialog(privacy: current),
    );
    if (values == null || !context.mounted) return;
    try {
      await ref.read(profileRepositoryProvider).patchPrivacy(values);
      ProfileScreen._refresh(ref);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Confidentialité enregistrée sur TORÈ.')));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Impossible d’enregistrer la confidentialité.')));
      }
    }
  }

  Future<void> _preview(BuildContext context, WidgetRef ref) async {
    final selected = await showModalBottomSheet<String>(
      context: context,
      builder: (_) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ListTile(title: Text('Voir mon profil comme…')),
            ListTile(
                leading: const Icon(Icons.public),
                title: const Text('Visiteur public'),
                onTap: () => Navigator.pop(context, 'PUBLIC')),
            ListTile(
                leading: const Icon(Icons.people_outline),
                title: const Text('Utilisateur TORÈ connecté'),
                onTap: () => Navigator.pop(context, 'TORE_USER')),
            ListTile(
                leading: const Icon(Icons.person_outline),
                title: const Text('Propriétaire'),
                onTap: () => Navigator.pop(context, 'OWNER')),
          ],
        ),
      ),
    );
    if (selected == null || !context.mounted) return;
    showDialog<void>(
      context: context,
      builder: (_) => _PreviewDialog(
        future: ref.read(profileRepositoryProvider).preview(selected),
        contextLabel: selected,
      ),
    );
  }

  String _visibilityLabel(ProfileVisibility value) {
    switch (value) {
      case ProfileVisibility.public:
        return 'Public';
      case ProfileVisibility.toreUsers:
        return 'Utilisateurs TORÈ';
      case ProfileVisibility.private:
        return 'Privé';
    }
  }
}

class _AffiliationsList extends StatelessWidget {
  const _AffiliationsList({required this.items});

  final List<Affiliation> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const ToreCard(
          child: Text('Aucune affiliation validée ou en attente.'));
    }
    return Column(
      children: items
          .map((item) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: ToreCard(
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(_statusIcon(item.status),
                        color: _statusColor(item.status)),
                    title: Text(item.structure.name),
                    subtitle: Text([
                      item.role,
                      _statusLabel(item.status),
                      if (item.mandate?.isNotEmpty == true) item.mandate!,
                      _visibilityLabel(item.visibility),
                    ].join(' · ')),
                    trailing: item.structure.id > 0
                        ? const Icon(Icons.chevron_right)
                        : null,
                    onTap: item.structure.id > 0
                        ? () => Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) =>
                                OrgaDetailScreen(orgId: item.structure.id)))
                        : null,
                  ),
                ),
              ))
          .toList(),
    );
  }

  static String _statusLabel(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return 'Active';
      case 'PENDING':
        return 'En attente';
      case 'ENDED':
        return 'Mandat terminé';
      case 'REVOKED':
        return 'Révoquée';
      default:
        return 'Rejetée';
    }
  }

  static IconData _statusIcon(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return Icons.verified_outlined;
      case 'PENDING':
        return Icons.schedule;
      case 'ENDED':
        return Icons.history;
      default:
        return Icons.block_outlined;
    }
  }

  static Color _statusColor(String status) {
    switch (status.toUpperCase()) {
      case 'ACTIVE':
        return AppColors.success;
      case 'PENDING':
        return AppColors.warning;
      default:
        return Colors.white54;
    }
  }

  static String _visibilityLabel(ProfileVisibility value) =>
      profileVisibilityToJson(value).replaceAll('_', ' ');
}

class _CapabilitiesCard extends StatelessWidget {
  const _CapabilitiesCard({required this.capabilities});

  final EffectiveCapabilities capabilities;

  @override
  Widget build(BuildContext context) {
    final labels = <String>{
      ...capabilities.globalRoles,
      ...capabilities.structures.map(
          (item) => '${item['role']} · structure ${item['organization_id']}'),
      ...capabilities.events
          .map((item) => '${item['role']} · event ${item['event_id']}'),
      ...capabilities.bars
          .map((item) => '${item['role']} · bar ${item['bar_id']}'),
    }.where((item) => item != 'USER').toList();
    return ToreCard(
      child: labels.isEmpty
          ? const Text(
              'Aucun rôle opérationnel. Ton compte reste utilisateur TORÈ.')
          : Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children:
                  labels.map((label) => Chip(label: Text(label))).toList(),
            ),
    );
  }
}

class _EditProfileDialog extends StatefulWidget {
  const _EditProfileDialog({required this.profile});
  final ToreProfile profile;

  @override
  State<_EditProfileDialog> createState() => _EditProfileDialogState();
}

class _EditProfileDialogState extends State<_EditProfileDialog> {
  late final TextEditingController username;
  late final TextEditingController displayName;
  late final TextEditingController avatar;
  late final TextEditingController oripeaux;
  late final TextEditingController bio;
  late final TextEditingController city;
  final formKey = GlobalKey<FormState>();

  @override
  void initState() {
    super.initState();
    username = TextEditingController(text: widget.profile.username);
    displayName = TextEditingController(text: widget.profile.displayName);
    avatar = TextEditingController(text: widget.profile.avatarUrl);
    oripeaux = TextEditingController(text: widget.profile.oripeaux);
    bio = TextEditingController(text: widget.profile.bio);
    city = TextEditingController(text: widget.profile.city);
  }

  @override
  void dispose() {
    username.dispose();
    displayName.dispose();
    avatar.dispose();
    oripeaux.dispose();
    bio.dispose();
    city.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Modifier mon profil'),
        content: Form(
          key: formKey,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: username,
                  decoration: const InputDecoration(labelText: 'Pseudo unique'),
                  validator: (value) => RegExp(r'^[a-z0-9._]{3,40}$')
                          .hasMatch((value ?? '').trim().toLowerCase())
                      ? null
                      : '3 à 40 caractères : a-z, 0-9, point ou underscore',
                ),
                TextFormField(
                  controller: displayName,
                  decoration: const InputDecoration(labelText: 'Nom affiché'),
                  validator: (value) => (value ?? '').trim().isEmpty
                      ? 'Nom affiché requis'
                      : null,
                ),
                TextFormField(
                    controller: avatar,
                    decoration: const InputDecoration(labelText: 'URL photo')),
                TextFormField(
                    controller: oripeaux,
                    maxLength: 500,
                    maxLines: 2,
                    decoration: const InputDecoration(labelText: 'Oripeaux associés')),
                TextFormField(
                  controller: bio,
                  maxLength: 280,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Bio'),
                ),
                TextFormField(
                    controller: city,
                    decoration: const InputDecoration(labelText: 'Ville')),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Annuler')),
          FilledButton(
            onPressed: () {
              if (!formKey.currentState!.validate()) return;
              Navigator.pop(context, {
                'username': username.text.trim().toLowerCase(),
                'display_name': displayName.text.trim(),
                'avatar_url': avatar.text.trim(),
                'oripeaux': oripeaux.text.trim(),
                'bio': bio.text.trim(),
                'city': city.text.trim(),
              });
            },
            child: const Text('Enregistrer'),
          ),
        ],
      );
}

class _PrivacyDialog extends StatefulWidget {
  const _PrivacyDialog({required this.privacy});
  final ProfilePrivacy privacy;

  @override
  State<_PrivacyDialog> createState() => _PrivacyDialogState();
}

class _PrivacyDialogState extends State<_PrivacyDialog> {
  late ProfileVisibility profile = widget.privacy.profile;
  late ProfileVisibility photo = widget.privacy.photo;
  late ProfileVisibility bio = widget.privacy.bio;
  late ProfileVisibility affiliations = widget.privacy.affiliations;
  late bool history = widget.privacy.eventHistoryOptIn;

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: const Text('Confidentialité'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _VisibilityField(
                  label: 'Profil général',
                  value: profile,
                  onChanged: (v) => setState(() => profile = v)),
              _VisibilityField(
                  label: 'Photo',
                  value: photo,
                  onChanged: (v) => setState(() => photo = v)),
              _VisibilityField(
                  label: 'Bio',
                  value: bio,
                  onChanged: (v) => setState(() => bio = v)),
              _VisibilityField(
                  label: 'Affiliations',
                  value: affiliations,
                  onChanged: (v) => setState(() => affiliations = v)),
              SwitchListTile.adaptive(
                contentPadding: EdgeInsets.zero,
                value: history,
                title: const Text('Historique d’événements'),
                subtitle: const Text('Désactivé et privé par défaut'),
                onChanged: (value) => setState(() => history = value),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Annuler')),
          FilledButton(
            onPressed: () => Navigator.pop(context, {
              'profile': profileVisibilityToJson(profile),
              'photo': profileVisibilityToJson(photo),
              'bio': profileVisibilityToJson(bio),
              'affiliations': profileVisibilityToJson(affiliations),
              'event_history_opt_in': history,
            }),
            child: const Text('Enregistrer'),
          ),
        ],
      );
}

class _VisibilityField extends StatelessWidget {
  const _VisibilityField(
      {required this.label, required this.value, required this.onChanged});
  final String label;
  final ProfileVisibility value;
  final ValueChanged<ProfileVisibility> onChanged;

  @override
  Widget build(BuildContext context) =>
      DropdownButtonFormField<ProfileVisibility>(
        initialValue: value,
        decoration: InputDecoration(labelText: label),
        items: const [
          DropdownMenuItem(
              value: ProfileVisibility.public, child: Text('Public')),
          DropdownMenuItem(
              value: ProfileVisibility.toreUsers,
              child: Text('Utilisateurs TORÈ')),
          DropdownMenuItem(
              value: ProfileVisibility.private, child: Text('Privé')),
        ],
        onChanged: (value) {
          if (value != null) onChanged(value);
        },
      );
}

class _PreviewDialog extends StatelessWidget {
  const _PreviewDialog({required this.future, required this.contextLabel});
  final Future<ToreProfile?> future;
  final String contextLabel;

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text('Aperçu · $contextLabel'),
        content: FutureBuilder<ToreProfile?>(
          future: future,
          builder: (_, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const SizedBox(
                  height: 100,
                  child: Center(child: CircularProgressIndicator()));
            }
            if (snapshot.hasError) {
              return const Text('Aperçu indisponible.');
            }
            final profile = snapshot.data;
            if (profile == null) {
              return const Text(
                  'Ce profil n’est pas visible dans ce contexte.');
            }
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(profile.displayName,
                    style: Theme.of(context).textTheme.titleLarge),
                if (profile.username != null) Text('@${profile.username}'),
                if (profile.bio.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(profile.bio),
                ],
                if (profile.affiliations.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                      '${profile.affiliations.length} affiliation(s) visible(s)'),
                ],
              ],
            );
          },
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Fermer')),
        ],
      );
}
