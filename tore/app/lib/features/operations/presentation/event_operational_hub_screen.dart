import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../../entry/presentation/entry_mode_screen.dart';
import '../../reports/presentation/report_providers.dart';
import '../../reports/presentation/report_screen.dart';
import '../domain/operational_models.dart';
import 'operational_providers.dart';

class EventOperationalHubScreen extends ConsumerWidget {
  const EventOperationalHubScreen({super.key, required this.capability});

  final ScopedCapability capability;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventId = capability.eventId!;
    final hub = ref.watch(eventOperationalHubProvider(eventId));
    final network = ref.watch(networkStatusProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(operationalCapabilitiesProvider);
        final _ =
            await ref.refresh(eventOperationalHubProvider(eventId).future);
        if (capability.allows('event.manage_staff')) {
          ref.invalidate(eventOperationalStaffProvider(eventId));
        }
        if (OperationalGuard.canViewReport(capability, eventId)) {
          ref.invalidate(eventReportProvider(eventId));
        }
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(capability.displayName,
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text('${capability.role} · ${capability.source}'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Chip(label: Text('Réseau : ${network.name}')),
              for (final action in capability.actions)
                Chip(label: Text(action.split('.').last)),
            ],
          ),
          const SizedBox(height: 12),
          hub.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (_, __) => _ErrorCard(onRetry: () {
              ref.invalidate(eventOperationalHubProvider(eventId));
              ref.invalidate(operationalCapabilitiesProvider);
            }),
            data: (result) {
              final event = result.data['event'] is Map
                  ? (result.data['event'] as Map).cast<String, dynamic>()
                  : const <String, dynamic>{};
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('État : ${event['state'] ?? '—'}'),
                      Text('Entrées : ${result.data['entry_count'] ?? '—'}'),
                      Text(result.isFromCache
                          ? 'Dernière donnée locale : ${result.cachedAt ?? '—'}'
                          : 'Synchronisé : ${result.cachedAt ?? 'maintenant'}'),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 12),
          if (OperationalGuard.canPerform(
              capability: capability,
              action: 'event.manage_entry',
              mode: OperationalMode.orga,
              scopeId: eventId))
            FilledButton.icon(
              onPressed: network == NetworkState.online
                  ? () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => EntryModeScreen(eventId: eventId)))
                  : null,
              icon: const Icon(Icons.qr_code_scanner),
              label: Text(network == NetworkState.online
                  ? 'Contrôle des entrées'
                  : 'Entrées bloquées hors ligne'),
            ),
          if (OperationalGuard.canViewReport(capability, eventId)) ...[
            const SizedBox(height: 24),
            _ReportSection(capability: capability),
          ],
          if (capability.allows('event.manage_staff')) ...[
            const SizedBox(height: 24),
            _StaffSection(eventId: eventId),
          ],
        ],
      ),
    );
  }
}

class _ReportSection extends ConsumerWidget {
  const _ReportSection({required this.capability});

  final ScopedCapability capability;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventId = capability.eventId!;
    final report = ref.watch(eventReportProvider(eventId));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Bilan soirée', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        report.when(
          loading: () => const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
          error: (_, __) => Card(
            child: ListTile(
              leading: const Icon(Icons.error_outline),
              title: const Text('Bilan indisponible'),
              trailing: IconButton(
                tooltip: 'Réessayer le bilan',
                onPressed: () => ref.invalidate(eventReportProvider(eventId)),
                icon: const Icon(Icons.refresh),
              ),
            ),
          ),
          data: (result) {
            final report = result.report;
            String euros(int cents) => '${(cents / 100).toStringAsFixed(2)} €';
            return Card(
              child: Column(
                children: [
                  if (result.fromCache)
                    const ListTile(
                      leading: Icon(Icons.cloud_off_outlined),
                      title: Text('Bilan en cache · lecture seule'),
                    ),
                  ListTile(
                    title: const Text('Recettes estimées'),
                    trailing: Text(euros(report.sales.grossRevenueCents)),
                  ),
                  ListTile(
                    title: const Text('Coûts'),
                    trailing: Text(euros(report.costs.totalCostCents)),
                  ),
                  ListTile(
                    title: const Text('Résultat estimé'),
                    trailing: Text(euros(report.profit.grossProfitCents)),
                  ),
                  ListTile(
                    title: const Text('Ouvrir le bilan soirée'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => ReportScreen(capability: capability),
                    )),
                  ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

class _StaffSection extends ConsumerWidget {
  const _StaffSection({required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final staff = ref.watch(eventOperationalStaffProvider(eventId));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child:
                  Text('Équipe', style: Theme.of(context).textTheme.titleLarge),
            ),
            FilledButton.tonalIcon(
              onPressed: () => _createInvite(context, ref),
              icon: const Icon(Icons.person_add_alt_1),
              label: const Text('Inviter'),
            ),
          ],
        ),
        staff.when(
          loading: () => const LinearProgressIndicator(),
          error: (_, __) => _ErrorCard(
              onRetry: () =>
                  ref.invalidate(eventOperationalStaffProvider(eventId))),
          data: (result) {
            final items = (result.data['items'] as List? ?? const [])
                .whereType<Map>()
                .map((item) => item.cast<String, dynamic>());
            final invitations =
                (result.data['invitations'] as List? ?? const [])
                    .whereType<Map>()
                    .map((item) => item.cast<String, dynamic>());
            return Column(
              children: [
                if (result.isFromCache)
                  const ListTile(
                      leading: Icon(Icons.cloud_off_outlined),
                      title:
                          Text('Liste locale — actions à confirmer en ligne')),
                for (final item in items)
                  ListTile(
                    leading: const Icon(Icons.badge_outlined),
                    title: Text(
                        (item['display_name'] ?? item['user_id']).toString()),
                    subtitle: Text('${item['role']} · ${item['status']}'),
                    trailing: item['status'] == 'ACTIVE'
                        ? IconButton(
                            tooltip: 'Révoquer',
                            onPressed: () => _revoke(
                                context, ref, item['user_id'].toString()),
                            icon: const Icon(Icons.person_remove_outlined),
                          )
                        : null,
                  ),
                if (invitations.isNotEmpty)
                  const ListTile(
                      title: Text('Invitations'),
                      leading: Icon(Icons.mail_outline)),
                for (final invitation in invitations)
                  ListTile(
                    leading: const Icon(Icons.schedule_send_outlined),
                    title: Text((invitation['target_user_id'] ?? 'Compte cible')
                        .toString()),
                    subtitle:
                        Text('${invitation['role']} · ${invitation['status']}'),
                    trailing: invitation['status'] == 'PENDING'
                        ? IconButton(
                            tooltip: 'Révoquer l’invitation',
                            onPressed: () => _revokeInvitation(context, ref,
                                (invitation['id'] as num).toInt()),
                            icon:
                                const Icon(Icons.cancel_schedule_send_outlined),
                          )
                        : null,
                  ),
              ],
            );
          },
        ),
      ],
    );
  }

  Future<void> _createInvite(BuildContext context, WidgetRef ref) async {
    final user = TextEditingController();
    String role = 'ENTRY';
    final submitted = await showDialog<bool>(
          context: context,
          builder: (context) => StatefulBuilder(
            builder: (context, setState) => AlertDialog(
              title: const Text('Inviter un membre'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: user,
                    decoration: const InputDecoration(
                        labelText: 'Identifiant utilisateur'),
                  ),
                  DropdownButtonFormField<String>(
                    initialValue: role,
                    items: const ['ENTRY', 'HELPER', 'MANAGER', 'BAR']
                        .map((value) =>
                            DropdownMenuItem(value: value, child: Text(value)))
                        .toList(),
                    onChanged: (value) => setState(() => role = value ?? role),
                    decoration: const InputDecoration(labelText: 'Rôle'),
                  ),
                ],
              ),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Annuler')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Créer')),
              ],
            ),
          ),
        ) ??
        false;
    if (!submitted || user.text.trim().isEmpty) {
      user.dispose();
      return;
    }
    try {
      final response =
          await ref.read(operationalRepositoryProvider).createInvitation(
                eventId: eventId,
                targetUserId: user.text,
                role: role,
                expiresInHours: 12,
                idempotencyKey:
                    'mobile-invite-${DateTime.now().microsecondsSinceEpoch}',
              );
      final link = response['deep_link']?.toString() ?? '';
      if (link.isNotEmpty) await Clipboard.setData(ClipboardData(text: link));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(link.isEmpty
                ? 'Invitation créée'
                : 'Lien à usage unique copié')));
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Invitation refusée par le serveur')));
      }
    } finally {
      user.dispose();
    }
  }

  Future<void> _revoke(
      BuildContext context, WidgetRef ref, String targetUserId) async {
    try {
      await ref
          .read(operationalRepositoryProvider)
          .revokeStaff(eventId, targetUserId, 'Retiré depuis l’application');
      ref.invalidate(eventOperationalStaffProvider(eventId));
      ref.invalidate(operationalCapabilitiesProvider);
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Révocation impossible')));
      }
    }
  }

  Future<void> _revokeInvitation(
      BuildContext context, WidgetRef ref, int invitationId) async {
    try {
      await ref.read(operationalRepositoryProvider).revokeInvitation(
          eventId, invitationId, 'Invitation retirée depuis l’application');
      ref.invalidate(eventOperationalStaffProvider(eventId));
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Révocation impossible')));
      }
    }
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.onRetry});
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.error_outline),
          title: const Text('Données opérationnelles indisponibles'),
          trailing:
              IconButton(onPressed: onRetry, icon: const Icon(Icons.refresh)),
        ),
      );
}
