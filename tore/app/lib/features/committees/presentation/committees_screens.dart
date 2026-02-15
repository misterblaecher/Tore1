import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/shared/utils/write_gate.dart';
import 'package:tore/state.dart';

class CommitteesListScreen extends ConsumerStatefulWidget {
  const CommitteesListScreen({super.key});

  @override
  ConsumerState<CommitteesListScreen> createState() => _CommitteesListScreenState();
}

class _CommitteesListScreenState extends ConsumerState<CommitteesListScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Comité OS')),
      body: FutureBuilder(
        future: ref.read(apiProvider).committeesWithCacheStatus(),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final result = snap.data!;
          final items = (result.payload as List<dynamic>);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (result.fromCache) const _ReadOnlyBanner(label: 'Mode lecture (cache)'),
              const SizedBox(height: 8),
              for (final row in items)
                Card(
                  child: ListTile(
                    title: Text((row as Map)['name']?.toString() ?? '-'),
                    subtitle: Text(row['descriptionPublic']?.toString() ?? ''),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteePublicScreen(committeeId: row['id'] as int))),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class CommitteePublicScreen extends ConsumerWidget {
  const CommitteePublicScreen({super.key, required this.committeeId});
  final int committeeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: const Text('Comité public')),
      body: FutureBuilder(
        future: Future.wait([ref.read(apiProvider).committee(committeeId), ref.read(apiProvider).committeeMeWithCacheStatus(committeeId)]),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final data = snap.data!;
          final committee = data[0] as Map<String, dynamic>;
          final me = (data[1] as CommitteeFetchResult).payload as Map<String, dynamic>;
          final isMember = me['isMember'] == true;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(committee['name']?.toString() ?? '', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(committee['descriptionPublic']?.toString() ?? ''),
              const SizedBox(height: 8),
              Text('Année active: ${committee['activeYear'] ?? '-'}'),
              const SizedBox(height: 16),
              if (!isMember)
                FilledButton(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteeJoinScreen(committeeId: committeeId))),
                  child: const Text('Join committee'),
                )
              else
                FilledButton(
                  onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteeHomeScreen(committeeId: committeeId))),
                  child: const Text('Ouvrir espace privé'),
                ),
            ],
          );
        },
      ),
    );
  }
}

class CommitteeJoinScreen extends ConsumerStatefulWidget {
  const CommitteeJoinScreen({super.key, required this.committeeId});
  final int committeeId;

  @override
  ConsumerState<CommitteeJoinScreen> createState() => _CommitteeJoinScreenState();
}

class _CommitteeJoinScreenState extends ConsumerState<CommitteeJoinScreen> {
  final _code = TextEditingController();
  String? _error;
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    final network = ref.watch(networkStatusProvider);
    final writeBlocked = isReadOnly(ref) || network != NetworkState.online;
    return Scaffold(
      appBar: AppBar(title: const Text('Rejoindre comité')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (writeBlocked) const _ReadOnlyBanner(label: 'Writes désactivés (offline/degraded)'),
          TextField(controller: _code, decoration: const InputDecoration(labelText: 'Code secret')),
          if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 10),
          FilledButton(
            onPressed: writeBlocked || _loading
                ? null
                : () async {
                    setState(() {
                      _loading = true;
                      _error = null;
                    });
                    try {
                      await ref.read(apiProvider).committeeJoinByCode(
                            committeeId: widget.committeeId,
                            code: _code.text.trim(),
                            idempotencyKey: 'committee-join-${DateTime.now().millisecondsSinceEpoch}',
                          );
                      if (context.mounted) Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => CommitteeHomeScreen(committeeId: widget.committeeId)));
                    } catch (e) {
                      setState(() => _error = e.toString());
                    } finally {
                      setState(() => _loading = false);
                    }
                  },
            child: Text(_loading ? '...' : 'Valider'),
          ),
        ],
      ),
    );
  }
}

class CommitteeHomeScreen extends ConsumerWidget {
  const CommitteeHomeScreen({super.key, required this.committeeId});
  final int committeeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: const Text('Comité privé')),
      body: FutureBuilder(
        future: Future.wait([ref.read(apiProvider).committeeMeWithCacheStatus(committeeId), ref.read(apiProvider).committeeYears(committeeId)]),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final meResult = snap.data![0] as CommitteeFetchResult;
          final me = meResult.payload as Map<String, dynamic>;
          final years = snap.data![1] as List<dynamic>;
          final perms = (me['permissions'] as Map?)?.cast<String, dynamic>() ?? const {};
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (meResult.fromCache) const _ReadOnlyBanner(label: 'Mode lecture (cache)'),
              Text('Role: ${me['membership']?['role'] ?? 'VISITOR'}'),
              const SizedBox(height: 10),
              const ListTile(title: Text('Forum'), subtitle: Text('Placeholder PR28')),
              ListTile(title: const Text('Archives'), subtitle: Text('Années: ${years.map((e) => (e as Map)['yearLabel']).join(', ')}')),
              const ListTile(title: Text('Finances'), subtitle: Text('Placeholder PR29')),
              const ListTile(title: Text('Baptême'), subtitle: Text('Placeholder PR29')),
              if (perms['can_manage_members'] == true)
                ListTile(
                  title: const Text('Members (admin)'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteeMembersScreen(committeeId: committeeId))),
                ),
            ],
          );
        },
      ),
    );
  }
}

class CommitteeMembersScreen extends ConsumerStatefulWidget {
  const CommitteeMembersScreen({super.key, required this.committeeId});
  final int committeeId;

  @override
  ConsumerState<CommitteeMembersScreen> createState() => _CommitteeMembersScreenState();
}

class _CommitteeMembersScreenState extends ConsumerState<CommitteeMembersScreen> {
  Future<void> _invite() async {
    await ref.read(apiProvider).createCommitteeInviteCode(
          committeeId: widget.committeeId,
          usesLeft: 5,
          idempotencyKey: 'committee-invite-${DateTime.now().millisecondsSinceEpoch}',
        );
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final writeBlocked = isReadOnly(ref) || ref.watch(networkStatusProvider) != NetworkState.online;
    return Scaffold(
      appBar: AppBar(title: const Text('Members')),
      body: FutureBuilder(
        future: ref.read(apiProvider).committeeMembers(widget.committeeId),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final items = (snap.data!['items'] as List<dynamic>);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (writeBlocked) const _ReadOnlyBanner(label: 'Writes désactivés'),
              FilledButton(onPressed: writeBlocked ? null : _invite, child: const Text('Créer invite code')),
              const SizedBox(height: 8),
              for (final row in items)
                Card(
                  child: ListTile(
                    title: Text((row as Map)['userId'].toString()),
                    subtitle: Text('Role: ${row['role']}'),
                    trailing: PopupMenuButton<String>(
                      onSelected: writeBlocked
                          ? null
                          : (value) async {
                              final reason = 'admin update';
                              if (value == 'revoke') {
                                await ref.read(apiProvider).revokeCommitteeMember(
                                      committeeId: widget.committeeId,
                                      userId: row['userId'].toString(),
                                      reason: reason,
                                      idempotencyKey: 'committee-revoke-${DateTime.now().millisecondsSinceEpoch}',
                                    );
                              } else {
                                await ref.read(apiProvider).setCommitteeMemberRole(
                                      committeeId: widget.committeeId,
                                      userId: row['userId'].toString(),
                                      role: value,
                                      reason: reason,
                                      idempotencyKey: 'committee-role-${DateTime.now().millisecondsSinceEpoch}',
                                    );
                              }
                              setState(() {});
                            },
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 'ADMIN', child: Text('Set ADMIN')),
                        PopupMenuItem(value: 'MOD', child: Text('Set MOD')),
                        PopupMenuItem(value: 'MEMBER', child: Text('Set MEMBER')),
                        PopupMenuItem(value: 'revoke', child: Text('Revoke')),
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
}

class _ReadOnlyBanner extends StatelessWidget {
  const _ReadOnlyBanner({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: Colors.amber.shade100, borderRadius: BorderRadius.circular(8)),
      child: Text(label),
    );
  }
}
