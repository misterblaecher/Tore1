import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../domain/operational_models.dart';
import 'invitation_center_screen.dart';
import 'operational_providers.dart';

class OperationalModeSwitcher extends ConsumerWidget {
  const OperationalModeSwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final capabilities = ref.watch(operationalCapabilitiesProvider);
    final selection = ref.watch(operationalSelectionProvider);
    return capabilities.when(
      loading: () => const SizedBox(
          height: 48, child: Center(child: LinearProgressIndicator())),
      error: (_, __) => ListTile(
        dense: true,
        leading: const Icon(Icons.lock_outline),
        title: const Text('Mode utilisateur'),
        trailing: IconButton(
          tooltip: 'Réessayer les accès',
          onPressed: () => ref.invalidate(operationalCapabilitiesProvider),
          icon: const Icon(Icons.refresh),
        ),
      ),
      data: (caps) {
        Future.microtask(() =>
            ref.read(operationalSelectionProvider.notifier).restore(caps));
        return SizedBox(
          height: 54,
          child: ListView(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            scrollDirection: Axis.horizontal,
            children: [
              ChoiceChip(
                label: const Text('USER'),
                avatar: const Icon(Icons.person_outline, size: 18),
                selected: selection.mode == OperationalMode.user,
                onSelected: (_) => ref
                    .read(operationalSelectionProvider.notifier)
                    .selectUser(),
              ),
              if (caps.canUseOrga) ...[
                const SizedBox(width: 8),
                ChoiceChip(
                  label: Text(selection.mode == OperationalMode.orga
                      ? 'ORGA · ${selection.capability?.displayName ?? ''}'
                      : 'ORGA'),
                  avatar: const Icon(Icons.event_available_outlined, size: 18),
                  selected: selection.mode == OperationalMode.orga,
                  onSelected: (_) => _pick(
                      context, ref, OperationalMode.orga, caps, caps.events),
                ),
              ],
              if (caps.canUseBar) ...[
                const SizedBox(width: 8),
                ChoiceChip(
                  label: Text(selection.mode == OperationalMode.bar
                      ? 'BAR · ${selection.capability?.displayName ?? ''}'
                      : 'BAR'),
                  avatar: const Icon(Icons.local_bar_outlined, size: 18),
                  selected: selection.mode == OperationalMode.bar,
                  onSelected: (_) =>
                      _pick(context, ref, OperationalMode.bar, caps, caps.bars),
                ),
              ],
              if (caps.userId.isNotEmpty) ...[
                const SizedBox(width: 8),
                IconButton(
                  tooltip: 'Invitations opérationnelles',
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => const InvitationCenterScreen())),
                  icon: const Icon(Icons.mark_email_unread_outlined),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  Future<void> _pick(
      BuildContext context,
      WidgetRef ref,
      OperationalMode mode,
      OperationalCapabilities capabilities,
      List<ScopedCapability> candidates) async {
    final selected = candidates.length == 1
        ? candidates.first
        : await showModalBottomSheet<ScopedCapability>(
            context: context,
            builder: (context) => SafeArea(
              child: ListView(
                shrinkWrap: true,
                children: [
                  const ListTile(title: Text('Choisir un contexte actif')),
                  for (final capability in candidates)
                    ListTile(
                      title: Text(capability.displayName),
                      subtitle:
                          Text('${capability.role} · ${capability.scope}'),
                      onTap: () => Navigator.pop(context, capability),
                    ),
                ],
              ),
            ),
          );
    if (selected == null) return;
    await ref
        .read(operationalSelectionProvider.notifier)
        .selectScoped(mode, selected, capabilities);
    ref.invalidate(operationalCapabilitiesProvider);
  }
}
