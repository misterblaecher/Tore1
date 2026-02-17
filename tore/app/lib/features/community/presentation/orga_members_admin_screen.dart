import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';

class OrgaMembersAdminScreen extends ConsumerStatefulWidget {
  const OrgaMembersAdminScreen({super.key, required this.orgId});

  final int orgId;

  @override
  ConsumerState<OrgaMembersAdminScreen> createState() => _OrgaMembersAdminScreenState();
}

class _OrgaMembersAdminScreenState extends ConsumerState<OrgaMembersAdminScreen> {
  String _idem() => 'orga-members-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    final canWriteNow = canWrite(ref, intent: WriteIntent.nonCritical);
    final reason = writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(title: const Text('Membres orga'), bottom: const TabBar(tabs: [Tab(text: 'Pending'), Tab(text: 'Active')])),
        body: FutureBuilder<Map<String, dynamic>>(
          future: api.orgaMembers(orgId: widget.orgId),
          builder: (context, snap) {
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final items = ((snap.data!['items'] as List?) ?? const []).cast<Map>();
            final pending = items.where((e) => (e['status'] ?? '').toString() == 'PENDING').toList();
            final active = items.where((e) => (e['status'] ?? '').toString() == 'ACTIVE').toList();

            Widget section(List<Map> rows, {required bool pendingTab}) => ListView(
                  children: [
                    if (!canWriteNow && reason != null) Padding(padding: const EdgeInsets.all(12), child: Text(reason)),
                    for (final row in rows)
                      ListTile(
                        title: Text((row['user_id'] ?? '').toString()),
                        subtitle: Text('${row['role']} • ${row['status']}'),
                        trailing: pendingTab
                            ? Wrap(spacing: 4, children: [
                                TextButton(
                                  onPressed: canWriteNow
                                      ? () async {
                                          await api.orgaApproveMember(orgId: widget.orgId, userId: (row['user_id'] ?? '').toString(), idempotencyKey: _idem());
                                          if (mounted) setState(() {});
                                        }
                                      : null,
                                  child: const Text('Approve'),
                                ),
                                TextButton(
                                  onPressed: canWriteNow
                                      ? () async {
                                          await api.orgaRejectMember(orgId: widget.orgId, userId: (row['user_id'] ?? '').toString(), reason: 'Rejected by manager', idempotencyKey: _idem());
                                          if (mounted) setState(() {});
                                        }
                                      : null,
                                  child: const Text('Reject'),
                                ),
                              ])
                            : null,
                      ),
                  ],
                );

            return TabBarView(children: [section(pending, pendingTab: true), section(active, pendingTab: false)]);
          },
        ),
      ),
    );
  }
}
