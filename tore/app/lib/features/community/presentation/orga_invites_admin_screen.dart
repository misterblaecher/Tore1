import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../../state.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_list_row.dart';
import 'orga_admin_providers.dart';

class OrgaInvitesAdminScreen extends ConsumerWidget {
  const OrgaInvitesAdminScreen({super.key, required this.orgId});

  final int orgId;

  String _idem() => 'orga-invite-admin-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final invites = ref.watch(orgaInvitesProvider(orgId));
    final api = ref.read(apiProvider);
    final canWriteNow = canWrite(ref, intent: WriteIntent.nonCritical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    Future<void> createInvite() async {
      String inviteType = 'MEMBER';
      int? expiry;
      await showModalBottomSheet(
        context: context,
        builder: (ctx) {
          return StatefulBuilder(builder: (_, setLocal) {
            return Padding(
              padding: const EdgeInsets.all(12),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                DropdownButtonFormField<String>(
                  value: inviteType,
                  items: const ['FOLLOWER', 'MEMBER', 'STAFF', 'MANAGER'].map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                  onChanged: (v) => setLocal(() => inviteType = v ?? 'MEMBER'),
                  decoration: const InputDecoration(labelText: 'Type'),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<int?>(
                  value: expiry,
                  items: const [
                    DropdownMenuItem<int?>(value: null, child: Text('Sans expiration')),
                    DropdownMenuItem<int?>(value: 1, child: Text('1 heure')),
                    DropdownMenuItem<int?>(value: 24, child: Text('24 heures')),
                    DropdownMenuItem<int?>(value: 24 * 7, child: Text('7 jours')),
                  ],
                  onChanged: (v) => setLocal(() => expiry = v),
                  decoration: const InputDecoration(labelText: 'Expiration'),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Créer'),
                )
              ]),
            );
          });
        },
      );
      final created = await api.orgaCreateInvite(orgId: orgId, inviteType: inviteType, expiresInHours: expiry, idempotencyKey: _idem());
      if (!context.mounted) return;
      await showDialog(
        context: context,
        builder: (ctx) {
          final rawCode = (created['code'] ?? '').toString();
          final webUrl = (created['webUrl'] ?? '').toString();
          return AlertDialog(
            title: const Text('Invitation créée'),
            content: Text(rawCode),
            actions: [
              TextButton(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: rawCode));
                },
                child: const Text('Copier code'),
              ),
              TextButton(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: webUrl));
                },
                child: const Text('Copier lien'),
              ),
              TextButton(
                onPressed: () async {
                  await Share.share(webUrl, subject: 'Invitation orga');
                },
                child: const Text('Partager'),
              ),
            ],
          );
        },
      );
      ref.invalidate(orgaInvitesProvider(orgId));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Invitations')),
      body: invites.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const Center(child: Text('Erreur chargement invitations')),
        data: (payload) {
          final items = ((payload['items'] as List?) ?? const []).cast<dynamic>();
          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              if (!canWriteNow && reason != null) Text(reason),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(onPressed: canWriteNow ? createInvite : null, icon: const Icon(Icons.add), label: const Text('Créer invitation')),
              ),
              const SizedBox(height: 8),
              ToreCard(
                child: Column(
                  children: [
                    for (final raw in items)
                      Builder(builder: (ctx) {
                        final row = Map<String, dynamic>.from(raw as Map);
                        final status = (row['status'] ?? 'ACTIVE').toString();
                        return ToreListRow(
                          title: '${row['invite_type'] ?? 'MEMBER'} • ${row['code_suffix'] ?? ''}',
                          subtitle: 'Expire: ${row['expires_at'] ?? '-'}',
                          trailing: Wrap(spacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
                            ToreChip(
                              label: status,
                              variant: status == 'ACTIVE'
                                  ? ToreChipVariant.ok
                                  : status == 'REVOKED'
                                      ? ToreChipVariant.closed
                                      : ToreChipVariant.warn,
                            ),
                            if (status == 'ACTIVE')
                              TextButton(
                                onPressed: canWriteNow
                                    ? () async {
                                        final reasonCtl = TextEditingController();
                                        await showDialog(
                                          context: context,
                                          builder: (_) => AlertDialog(
                                            title: const Text('Révoquer invitation'),
                                            content: TextField(controller: reasonCtl, decoration: const InputDecoration(hintText: 'Raison (obligatoire)')),
                                            actions: [
                                              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
                                              FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Confirmer')),
                                            ],
                                          ),
                                        );
                                        if (reasonCtl.text.trim().isEmpty) return;
                                        await api.orgaRevokeInvite(
                                          orgId: orgId,
                                          inviteId: (row['id'] as num).toInt(),
                                          reason: reasonCtl.text.trim(),
                                          idempotencyKey: _idem(),
                                        );
                                        ref.invalidate(orgaInvitesProvider(orgId));
                                      }
                                    : null,
                                child: const Text('Revoke'),
                              ),
                          ]),
                        );
                      }),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
