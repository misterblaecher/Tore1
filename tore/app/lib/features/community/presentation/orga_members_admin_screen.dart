import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import '../../../ui/components/tore_list_row.dart';
import 'orga_admin_helpers.dart';
import 'orga_admin_providers.dart';

class OrgaMembersAdminScreen extends ConsumerStatefulWidget {
  const OrgaMembersAdminScreen({super.key, required this.orgId, this.myRole = 'MANAGER', this.myUserId = ''});

  final int orgId;
  final String myRole;
  final String myUserId;

  @override
  ConsumerState<OrgaMembersAdminScreen> createState() => _OrgaMembersAdminScreenState();
}

class _OrgaMembersAdminScreenState extends ConsumerState<OrgaMembersAdminScreen> {
  String _idem() => 'orga-members-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  bool get _isOwner => widget.myRole == 'OWNER';

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    final membersAsync = ref.watch(orgaMembershipsProvider(widget.orgId));
    final canWriteNow = canWrite(ref, intent: WriteIntent.nonCritical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(title: const Text('Membres & rôles'), bottom: const TabBar(tabs: [Tab(text: 'Pending'), Tab(text: 'Active'), Tab(text: 'Left')])),
        body: membersAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => const Center(child: Text('Erreur chargement membres')),
          data: (data) {
            final items = ((data['items'] as List?) ?? const []).cast<Map>();
            final pending = items.where((e) => (e['status'] ?? '').toString() == 'PENDING').toList();
            final active = items.where((e) => (e['status'] ?? '').toString() == 'ACTIVE').toList();
            final left = items.where((e) => (e['status'] ?? '').toString() == 'LEFT').toList();

            Future<void> askReasonAndRun({required String title, required Future<void> Function(String reason) onSubmit}) async {
              final ctl = TextEditingController();
              await showDialog(
                context: context,
                builder: (_) => AlertDialog(
                  title: Text(title),
                  content: TextField(controller: ctl, decoration: const InputDecoration(hintText: 'Raison obligatoire')),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
                    FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Confirmer')),
                  ],
                ),
              );
              final reasonValue = ctl.text.trim();
              if (reasonValue.isEmpty) return;
              await onSubmit(reasonValue);
            }

            Widget section(List<Map> rows, {required bool pendingTab, bool leftTab = false}) => ListView(
                  children: [
                    if (!canWriteNow && reason != null) Padding(padding: const EdgeInsets.all(12), child: Text(reason)),
                    for (final row in rows)
                      ToreListRow(
                        title: (row['user_id'] ?? '').toString(),
                        subtitle: '${row['role']} • ${row['status']}',
                        trailing: pendingTab
                            ? Wrap(spacing: 4, children: [
                                TextButton(
                                  onPressed: canWriteNow
                                      ? () async {
                                          await api.orgaApproveMember(orgId: widget.orgId, userId: (row['user_id'] ?? '').toString(), idempotencyKey: _idem());
                                          ref.invalidate(orgaMembershipsProvider(widget.orgId));
                                        }
                                      : null,
                                  child: const Text('Approve'),
                                ),
                                TextButton(
                                  onPressed: canWriteNow
                                      ? () async {
                                          await askReasonAndRun(
                                            title: 'Refuser demande',
                                            onSubmit: (why) async => api.orgaRejectMember(orgId: widget.orgId, userId: (row['user_id'] ?? '').toString(), reason: why, idempotencyKey: _idem()),
                                          );
                                          ref.invalidate(orgaMembershipsProvider(widget.orgId));
                                        }
                                      : null,
                                  child: const Text('Reject'),
                                ),
                              ])
                            : leftTab
                                ? null
                                : Wrap(spacing: 4, children: [
                                    if ((row['user_id'] ?? '').toString() != widget.myUserId && (row['role'] ?? '').toString() != 'OWNER')
                                      TextButton(
                                        onPressed: canWriteNow
                                            ? () async {
                                                String role = (row['role'] ?? 'MEMBER').toString();
                                                await showModalBottomSheet(
                                                  context: context,
                                                  builder: (_) => StatefulBuilder(
                                                    builder: (_, setLocal) => Padding(
                                                      padding: const EdgeInsets.all(12),
                                                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                                                        DropdownButtonFormField<String>(
                                                          value: role,
                                                          items: const ['MANAGER', 'STAFF', 'MEMBER', 'FOLLOWER', 'OWNER']
                                                              .where((r) => _isOwner || r != 'OWNER')
                                                              .map((r) => DropdownMenuItem(value: r, child: Text(r)))
                                                              .toList(),
                                                          onChanged: (v) => setLocal(() => role = v ?? role),
                                                        ),
                                                        const SizedBox(height: 8),
                                                        FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Valider')),
                                                      ]),
                                                    ),
                                                  ),
                                                );
                                                await askReasonAndRun(
                                                  title: 'Changer rôle',
                                                  onSubmit: (why) async {
                                                    final payload = buildRoleChangePayload(role: role, reason: why);
                                                    await api.orgaSetMembershipRole(
                                                      orgId: widget.orgId,
                                                      userId: (row['user_id'] ?? '').toString(),
                                                      role: payload['role'].toString(),
                                                      reason: payload['reason'].toString(),
                                                      idempotencyKey: _idem(),
                                                    );
                                                  },
                                                );
                                                ref.invalidate(orgaMembershipsProvider(widget.orgId));
                                              }
                                            : null,
                                        child: const Text('Changer rôle'),
                                      ),
                                    if ((row['role'] ?? '').toString() != 'OWNER')
                                      TextButton(
                                        onPressed: canWriteNow
                                            ? () async {
                                                await askReasonAndRun(
                                                  title: 'Retirer membre',
                                                  onSubmit: (why) async => api.orgaRemoveMembership(
                                                    orgId: widget.orgId,
                                                    userId: (row['user_id'] ?? '').toString(),
                                                    reason: why,
                                                    idempotencyKey: _idem(),
                                                  ),
                                                );
                                                ref.invalidate(orgaMembershipsProvider(widget.orgId));
                                              }
                                            : null,
                                        child: const Text('Retirer'),
                                      ),
                                  ]),
                      ),
                  ],
                );

            return TabBarView(children: [section(pending, pendingTab: true), section(active, pendingTab: false), section(left, pendingTab: false, leftTab: true)]);
          },
        ),
      ),
    );
  }
}
