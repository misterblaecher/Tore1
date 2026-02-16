import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/api.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/glossary/glossary_providers.dart';
import 'package:tore/features/glossary/glossary_screens.dart';
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
        future: Future.wait([
          ref.read(apiProvider).committeeMeWithCacheStatus(committeeId),
          ref.read(apiProvider).committeeYears(committeeId),
          ref.read(apiProvider).committee(committeeId),
          ref.read(apiProvider).modulesState(),
        ]),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final meResult = snap.data![0] as CommitteeFetchResult;
          final me = meResult.payload as Map<String, dynamic>;
          final perms = (me['permissions'] as Map?)?.cast<String, dynamic>() ?? const {};
          final committee = snap.data![2] as Map<String, dynamic>;
          final modules = snap.data![3] as Map<String, dynamic>;
          final committeeModuleOn = modules['committee_os'] == true;
          final glossaryModuleOn = modules['folklore_glossary'] == true;
          final settingsAsync = glossaryModuleOn ? ref.watch(committeeGlossarySettingsProvider(committeeId)) : null;
          final role = (me['membership']?['role'] ?? '').toString().toUpperCase();
          final canModerateGlossary = ['MOD', 'ADMIN', 'OWNER'].contains(role);
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (meResult.fromCache) const _ReadOnlyBanner(label: 'Mode lecture (cache)'),
              Text('Role: ${me['membership']?['role'] ?? 'VISITOR'}'),
              const SizedBox(height: 8),
              ListTile(
                title: const Text('Forum + archives'),
                subtitle: const Text('Forum catégorisé par année'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => CommitteeForumScreen(
                    committeeId: committeeId,
                    committeeName: committee['name']?.toString() ?? 'Comité',
                    canAdminCategories: me['membership']?['role'] == 'ADMIN' || me['membership']?['role'] == 'OWNER',
                    canModerate: ['MOD', 'ADMIN', 'OWNER'].contains(me['membership']?['role']),
                  ),
                )),
              ),
              if (committeeModuleOn && glossaryModuleOn)
                settingsAsync!.when(
                  loading: () => const SizedBox.shrink(),
                  error: (_, __) => const SizedBox.shrink(),
                  data: (settings) => Column(
                    children: [
                      if (settings.data.publicEnabled)
                        ListTile(
                          title: const Text('Glossaire'),
                          subtitle: const Text('Voir les termes du comité'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) => GlossaryTermsScreen(
                              committeeId: committeeId,
                              committeeName: committee['name']?.toString() ?? 'Comité',
                              isPublicScope: true,
                            ),
                          )),
                        ),
                      if (canModerateGlossary)
                        ListTile(
                          title: const Text('Gérer Glossaire'),
                          subtitle: const Text('Toggle public + créer/éditer/archiver/delete'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => Navigator.of(context).push(MaterialPageRoute(
                            builder: (_) => CommitteeGlossaryAdminScreen(
                              committeeId: committeeId,
                              committeeName: committee['name']?.toString() ?? 'Comité',
                            ),
                          )),
                        ),
                    ],
                  ),
                ),
              ListTile(
                title: const Text('Finances'),
                subtitle: Text(perms['can_manage_finances'] == true ? 'Ledger + exports + ajout entrées' : 'Ledger + exports (lecture)'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteeFinancesScreen(committeeId: committeeId, canManageFinances: me['canManageFinances'] == true))),
              ),
              if (me['canManageBapteme'] == true)
                ListTile(
                  title: const Text('Baptême'),
                  subtitle: const Text('Campagnes, invités, créneaux, incidents'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommitteeBaptemeScreen(committeeId: committeeId))),
                ),
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

class CommitteeForumScreen extends ConsumerStatefulWidget {
  const CommitteeForumScreen({super.key, required this.committeeId, required this.committeeName, required this.canModerate, required this.canAdminCategories});
  final int committeeId;
  final String committeeName;
  final bool canModerate;
  final bool canAdminCategories;

  @override
  ConsumerState<CommitteeForumScreen> createState() => _CommitteeForumScreenState();
}

class _CommitteeForumScreenState extends ConsumerState<CommitteeForumScreen> {
  int? _yearId;
  int? _categoryId;

  @override
  Widget build(BuildContext context) {
    final network = ref.watch(networkStatusProvider);
    final writeBlocked = isReadOnly(ref) || network != NetworkState.online;
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.committeeName} · Forum'),
        actions: [
          if (widget.canAdminCategories && _yearId != null)
            IconButton(
              icon: const Icon(Icons.settings),
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CategoriesAdminScreen(committeeId: widget.committeeId, yearId: _yearId!))),
            ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: writeBlocked || _yearId == null || _categoryId == null
            ? null
            : () async {
                final created = await showModalBottomSheet<bool>(
                  context: context,
                  isScrollControlled: true,
                  builder: (_) => NewPostSheet(committeeId: widget.committeeId, yearId: _yearId!, categoryId: _categoryId!),
                );
                if (created == true) setState(() {});
              },
        label: Text(writeBlocked ? 'Mode lecture' : 'New post'),
        icon: const Icon(Icons.add),
      ),
      body: FutureBuilder(
        future: Future.wait([ref.read(apiProvider).committeeYears(widget.committeeId), if (_yearId != null) ref.read(apiProvider).committeeForumCategoriesWithCacheStatus(committeeId: widget.committeeId, yearId: _yearId!)]),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final years = snap.data![0] as List<dynamic>;
          _yearId ??= (years.cast<Map>().firstWhere((e) => e['isActive'] == true, orElse: () => years.first as Map)['id'] as int);
          return FutureBuilder(
            future: ref.read(apiProvider).committeeForumCategoriesWithCacheStatus(committeeId: widget.committeeId, yearId: _yearId!),
            builder: (context, catSnap) {
              if (!catSnap.hasData) return const Center(child: CircularProgressIndicator());
              final catResult = catSnap.data!;
              final categories = (catResult.payload as List<dynamic>).cast<Map>();
              if (categories.isNotEmpty && !_hasCategory(categories, _categoryId)) {
                _categoryId = categories.first['id'] as int;
              }
              return Column(
                children: [
                  if (catResult.fromCache || writeBlocked) const Padding(padding: EdgeInsets.all(8), child: _ReadOnlyBanner(label: 'Mode lecture (offline/degraded/cache)')),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Row(
                      children: [
                        const Text('Année:'),
                        const SizedBox(width: 8),
                        DropdownButton<int>(
                          value: _yearId,
                          items: [for (final y in years.cast<Map>()) DropdownMenuItem<int>(value: y['id'] as int, child: Text((y['yearLabel'] ?? '').toString()))],
                          onChanged: (v) => setState(() {
                            _yearId = v;
                            _categoryId = null;
                          }),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(
                    height: 44,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        for (final c in categories)
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 6),
                            child: ChoiceChip(
                              label: Text(c['name'].toString()),
                              selected: _categoryId == c['id'],
                              onSelected: (_) => setState(() => _categoryId = c['id'] as int),
                            ),
                          ),
                      ],
                    ),
                  ),
                  Expanded(
                    child: _categoryId == null
                        ? const Center(child: Text('Aucune catégorie'))
                        : FutureBuilder(
                            future: ref.read(apiProvider).committeeForumPostsWithCacheStatus(committeeId: widget.committeeId, yearId: _yearId!, categoryId: _categoryId!),
                            builder: (context, postSnap) {
                              if (!postSnap.hasData) return const Center(child: CircularProgressIndicator());
                              final payload = (postSnap.data!.payload as Map<String, dynamic>);
                              final items = (payload['items'] as List<dynamic>).cast<Map>();
                              return ListView(
                                children: [
                                  for (final p in items)
                                    ListTile(
                                      title: Text(p['title'].toString(), maxLines: 1, overflow: TextOverflow.ellipsis),
                                      subtitle: Text('${p['createdByDisplayName']} · ${p['body'].toString()}', maxLines: 1, overflow: TextOverflow.ellipsis),
                                      trailing: Wrap(spacing: 4, children: [if (p['isPinned'] == true) const Chip(label: Text('PIN')), if (p['isLocked'] == true) const Chip(label: Text('LOCK'))]),
                                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                                        builder: (_) => PostDetailScreen(
                                          committeeId: widget.committeeId,
                                          postId: p['id'] as int,
                                          canModerate: widget.canModerate,
                                          writeBlocked: writeBlocked,
                                        ),
                                      )),
                                    ),
                                ],
                              );
                            },
                          ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }

  bool _hasCategory(List<Map> categories, int? id) => categories.any((c) => c['id'] == id);
}


class NewPostSheet extends ConsumerStatefulWidget {
  const NewPostSheet({super.key, required this.committeeId, required this.yearId, required this.categoryId});
  final int committeeId;
  final int yearId;
  final int categoryId;

  @override
  ConsumerState<NewPostSheet> createState() => _NewPostSheetState();
}

class _NewPostSheetState extends ConsumerState<NewPostSheet> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(left: 16, right: 16, top: 16, bottom: MediaQuery.of(context).viewInsets.bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(controller: _title, decoration: const InputDecoration(labelText: 'Titre')),
          TextField(controller: _body, maxLines: 5, decoration: const InputDecoration(labelText: 'Message')),
          const SizedBox(height: 10),
          FilledButton(
            onPressed: _loading
                ? null
                : () async {
                    setState(() => _loading = true);
                    await ref.read(apiProvider).createCommitteeForumPost(
                          committeeId: widget.committeeId,
                          yearId: widget.yearId,
                          categoryId: widget.categoryId,
                          title: _title.text.trim(),
                          body: _body.text.trim(),
                          idempotencyKey: 'forum-post-${DateTime.now().millisecondsSinceEpoch}',
                        );
                    if (context.mounted) Navigator.of(context).pop(true);
                  },
            child: Text(_loading ? '...' : 'Publier'),
          ),
        ],
      ),
    );
  }
}

class PostDetailScreen extends ConsumerStatefulWidget {
  const PostDetailScreen({super.key, required this.committeeId, required this.postId, required this.canModerate, required this.writeBlocked});
  final int committeeId;
  final int postId;
  final bool canModerate;
  final bool writeBlocked;

  @override
  ConsumerState<PostDetailScreen> createState() => _PostDetailScreenState();
}

class _PostDetailScreenState extends ConsumerState<PostDetailScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Post'),
        actions: [
          if (widget.canModerate)
            PopupMenuButton<String>(
              onSelected: widget.writeBlocked ? null : (v) => _moderate(v),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'pin', child: Text('Pin / Unpin')),
                PopupMenuItem(value: 'lock', child: Text('Lock / Unlock')),
                PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
        ],
      ),
      body: FutureBuilder(
        future: ref.read(apiProvider).committeeForumPostDetail(committeeId: widget.committeeId, postId: widget.postId),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final post = snap.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(post['title'].toString(), style: Theme.of(context).textTheme.headlineSmall),
              Text('${post['createdByDisplayName']} · ${post['createdAt']}'),
              const SizedBox(height: 12),
              Text(post['body'].toString()),
            ],
          );
        },
      ),
    );
  }

  Future<void> _moderate(String action) async {
    final reason = await _askReason(context);
    if (reason == null || reason.trim().isEmpty) return;
    final detail = await ref.read(apiProvider).committeeForumPostDetail(committeeId: widget.committeeId, postId: widget.postId);
    Map<String, dynamic> body;
    if (action == 'pin') {
      body = {'pinned': !(detail['isPinned'] == true), 'reason': reason};
    } else if (action == 'lock') {
      body = {'locked': !(detail['isLocked'] == true), 'reason': reason};
    } else {
      body = {'reason': reason};
    }
    await ref.read(apiProvider).committeeForumModAction(
          committeeId: widget.committeeId,
          postId: widget.postId,
          action: action,
          body: body,
          idempotencyKey: 'forum-mod-$action-${DateTime.now().millisecondsSinceEpoch}',
        );
    if (mounted) setState(() {});
  }

  Future<String?> _askReason(BuildContext context) async {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reason'),
        content: TextField(controller: ctrl),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text('OK')),
        ],
      ),
    );
  }
}

class CategoriesAdminScreen extends ConsumerStatefulWidget {
  const CategoriesAdminScreen({super.key, required this.committeeId, required this.yearId});
  final int committeeId;
  final int yearId;

  @override
  ConsumerState<CategoriesAdminScreen> createState() => _CategoriesAdminScreenState();
}

class _CategoriesAdminScreenState extends ConsumerState<CategoriesAdminScreen> {
  @override
  Widget build(BuildContext context) {
    final writeBlocked = isReadOnly(ref) || ref.watch(networkStatusProvider) != NetworkState.online;
    return Scaffold(
      appBar: AppBar(title: const Text('Admin catégories')),
      floatingActionButton: FloatingActionButton(
        onPressed: writeBlocked
            ? null
            : () async {
                final ctrl = TextEditingController();
                final name = await showDialog<String>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    title: const Text('Nouvelle catégorie'),
                    content: TextField(controller: ctrl),
                    actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')), FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text('Créer'))],
                  ),
                );
                if (name != null && name.isNotEmpty) {
                  await ref.read(apiProvider).createCommitteeForumCategory(
                        committeeId: widget.committeeId,
                        yearId: widget.yearId,
                        name: name,
                        idempotencyKey: 'forum-cat-create-${DateTime.now().millisecondsSinceEpoch}',
                      );
                  setState(() {});
                }
              },
        child: const Icon(Icons.add),
      ),
      body: FutureBuilder(
        future: ref.read(apiProvider).committeeForumCategoriesWithCacheStatus(committeeId: widget.committeeId, yearId: widget.yearId),
        builder: (context, snap) {
          if (!snap.hasData) return const Center(child: CircularProgressIndicator());
          final items = (snap.data!.payload as List<dynamic>).cast<Map>();
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (writeBlocked) const _ReadOnlyBanner(label: 'Writes désactivés'),
              for (final row in items)
                ListTile(
                  title: Text(row['name'].toString()),
                  subtitle: Text('Ordre ${row['orderIndex']}'),
                  trailing: Wrap(
                    spacing: 6,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_upward),
                        onPressed: writeBlocked
                            ? null
                            : () async {
                                await ref.read(apiProvider).updateCommitteeForumCategory(
                                      committeeId: widget.committeeId,
                                      categoryId: row['id'] as int,
                                      orderIndex: ((row['orderIndex'] as int) - 1).clamp(0, 999),
                                      idempotencyKey: 'forum-cat-up-${DateTime.now().millisecondsSinceEpoch}',
                                    );
                                setState(() {});
                              },
                      ),
                      Switch(
                        value: row['isArchived'] == true,
                        onChanged: writeBlocked
                            ? null
                            : (v) async {
                                await ref.read(apiProvider).updateCommitteeForumCategory(
                                      committeeId: widget.committeeId,
                                      categoryId: row['id'] as int,
                                      isArchived: v,
                                      idempotencyKey: 'forum-cat-arch-${DateTime.now().millisecondsSinceEpoch}',
                                    );
                                setState(() {});
                              },
                      ),
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


class CommitteeFinancesScreen extends ConsumerStatefulWidget {
  const CommitteeFinancesScreen({super.key, required this.committeeId, required this.canManageFinances});
  final int committeeId;
  final bool canManageFinances;

  @override
  ConsumerState<CommitteeFinancesScreen> createState() => _CommitteeFinancesScreenState();
}

class _CommitteeFinancesScreenState extends ConsumerState<CommitteeFinancesScreen> {
  int? _yearId;

  @override
  Widget build(BuildContext context) {
    final readOnly = isReadOnly(ref) || ref.watch(networkStatusProvider) != NetworkState.online;
    return Scaffold(
      appBar: AppBar(title: const Text('Finances comité')),
      floatingActionButton: widget.canManageFinances
          ? FloatingActionButton.extended(
              onPressed: readOnly || _yearId == null
                  ? null
                  : () async {
                      await showModalBottomSheet(
                        context: context,
                        isScrollControlled: true,
                        builder: (_) => _AddLedgerEntrySheet(committeeId: widget.committeeId, yearId: _yearId!),
                      );
                      setState(() {});
                    },
              label: const Text('Add entry'),
              icon: const Icon(Icons.add),
            )
          : null,
      body: FutureBuilder(
        future: ref.read(apiProvider).committeeYears(widget.committeeId),
        builder: (context, yearsSnap) {
          if (!yearsSnap.hasData) return const Center(child: CircularProgressIndicator());
          final years = (yearsSnap.data! as List).cast<Map>();
          _yearId ??= (years.firstWhere((y) => y['isActive'] == true, orElse: () => years.first)['id'] as int);
          return FutureBuilder(
            future: Future.wait([
              ref.read(apiProvider).committeeFinancesSummaryWithCacheStatus(committeeId: widget.committeeId, yearId: _yearId!),
              ref.read(apiProvider).committeeFinancesLedgerWithCacheStatus(committeeId: widget.committeeId, yearId: _yearId!),
            ]),
            builder: (context, snap) {
              if (!snap.hasData) return const Center(child: CircularProgressIndicator());
              final summaryRes = snap.data![0] as CommitteeFetchResult;
              final ledgerRes = snap.data![1] as CommitteeFetchResult;
              final summary = (summaryRes.payload as Map<String, dynamic>);
              final ledgerItems = ((ledgerRes.payload as Map<String, dynamic>)['items'] as List<dynamic>? ?? const []);
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (summaryRes.fromCache || ledgerRes.fromCache || readOnly) const _ReadOnlyBanner(label: 'Mode lecture (offline/degraded/cache)'),
                  Wrap(spacing: 8, children: years.map((y) => ChoiceChip(label: Text(y['yearLabel'].toString()), selected: _yearId == y['id'], onSelected: (_) => setState(() => _yearId = y['id'] as int))).toList()),
                  const SizedBox(height: 8),
                  Text('Income: ${summary['incomeCents'] ?? 0}c · Expense: ${summary['expenseCents'] ?? 0}c · Net: ${summary['netCents'] ?? 0}c'),
                  const SizedBox(height: 8),
                  Text('Exports', style: Theme.of(context).textTheme.titleMedium),
                  SelectableText(ref.read(apiProvider).committeeFinancesExportCsvUrl(committeeId: widget.committeeId, yearId: _yearId!)),
                  SelectableText(ref.read(apiProvider).committeeFinancesSnapshotUrl(committeeId: widget.committeeId, yearId: _yearId!)),
                  const Divider(),
                  Text('Par catégorie', style: Theme.of(context).textTheme.titleMedium),
                  for (final e in (summary['byCategory'] as Map<String, dynamic>? ?? const {}).entries)
                    ListTile(title: Text(e.key), subtitle: Text('in ${(e.value['incomeCents'] ?? 0)} · out ${(e.value['expenseCents'] ?? 0)}')),
                  const Divider(),
                  Text('Ledger', style: Theme.of(context).textTheme.titleMedium),
                  for (final row in ledgerItems)
                    ListTile(
                      dense: true,
                      title: Text('${row['occurredAt']} · ${row['category']} · ${row['amountCents']}c'),
                      subtitle: Text('${row['type']} · ${row['note'] ?? ''}'),
                    ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}

class _AddLedgerEntrySheet extends ConsumerStatefulWidget {
  const _AddLedgerEntrySheet({required this.committeeId, required this.yearId});
  final int committeeId;
  final int yearId;

  @override
  ConsumerState<_AddLedgerEntrySheet> createState() => _AddLedgerEntrySheetState();
}

class _AddLedgerEntrySheetState extends ConsumerState<_AddLedgerEntrySheet> {
  final _amount = TextEditingController();
  final _category = TextEditingController();
  final _note = TextEditingController();
  String _type = 'EXPENSE';

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(left: 16, right: 16, top: 16, bottom: MediaQuery.of(context).viewInsets.bottom + 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(value: _type, items: const [DropdownMenuItem(value: 'EXPENSE', child: Text('EXPENSE')), DropdownMenuItem(value: 'INCOME', child: Text('INCOME'))], onChanged: (v) => setState(() => _type = v ?? 'EXPENSE')),
          TextField(controller: _amount, decoration: const InputDecoration(labelText: 'Amount (cents)'), keyboardType: TextInputType.number),
          TextField(controller: _category, decoration: const InputDecoration(labelText: 'Category')),
          TextField(controller: _note, decoration: const InputDecoration(labelText: 'Note')),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: () async {
              await ref.read(apiProvider).createCommitteeFinanceEntry(
                    committeeId: widget.committeeId,
                    body: {
                      'yearId': widget.yearId,
                      'type': _type,
                      'amountCents': int.tryParse(_amount.text) ?? 0,
                      'currency': 'EUR',
                      'category': _category.text,
                      'occurredAt': DateTime.now().toIso8601String().substring(0, 10),
                      'note': _note.text,
                    },
                    idempotencyKey: 'committee-finance-${DateTime.now().millisecondsSinceEpoch}',
                  );
              if (mounted) Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}

class CommitteeBaptemeScreen extends ConsumerStatefulWidget {
  const CommitteeBaptemeScreen({super.key, required this.committeeId});
  final int committeeId;

  @override
  ConsumerState<CommitteeBaptemeScreen> createState() => _CommitteeBaptemeScreenState();
}

class _CommitteeBaptemeScreenState extends ConsumerState<CommitteeBaptemeScreen> {
  int? _yearId;
  int? _campaignId;
  final _campaignName = TextEditingController();
  final _inviteName = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final readOnly = isReadOnly(ref) || ref.watch(networkStatusProvider) != NetworkState.online;
    return Scaffold(
      appBar: AppBar(title: const Text('Baptême (admin)')),
      body: FutureBuilder(
        future: ref.read(apiProvider).committeeYears(widget.committeeId),
        builder: (context, yearsSnap) {
          if (!yearsSnap.hasData) return const Center(child: CircularProgressIndicator());
          final years = (yearsSnap.data! as List).cast<Map>();
          _yearId ??= (years.firstWhere((y) => y['isActive'] == true, orElse: () => years.first)['id'] as int);
          return FutureBuilder(
            future: ref.read(apiProvider).committeeBaptemeCampaign(committeeId: widget.committeeId, yearId: _yearId!),
            builder: (context, campSnap) {
              if (!campSnap.hasData) return const Center(child: CircularProgressIndicator());
              final campaign = (campSnap.data!['campaign'] as Map<String, dynamic>?);
              _campaignId = campaign?['id'] as int?;
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (readOnly) const _ReadOnlyBanner(label: 'Mode lecture (offline/degraded/cache)'),
                  TextField(controller: _campaignName, decoration: const InputDecoration(labelText: 'Nom campagne')),
                  FilledButton(onPressed: readOnly ? null : () async {
                    final created = await ref.read(apiProvider).createCommitteeBaptemeCampaign(committeeId: widget.committeeId, yearId: _yearId!, name: _campaignName.text, idempotencyKey: 'bap-campaign-${DateTime.now().millisecondsSinceEpoch}');
                    _campaignId = created['id'] as int;
                    setState(() {});
                  }, child: const Text('Créer campagne')),
                  if (_campaignId != null) ...[
                    const SizedBox(height: 8),
                    Text('Campaign #$_campaignId'),
                    TextField(controller: _inviteName, decoration: const InputDecoration(labelText: 'Blue name')),
                    FilledButton(onPressed: readOnly ? null : () async {
                      final invite = await ref.read(apiProvider).createCommitteeBaptemeInvite(committeeId: widget.committeeId, campaignId: _campaignId!, blueDisplayName: _inviteName.text, idempotencyKey: 'bap-invite-${DateTime.now().millisecondsSinceEpoch}');
                      await Clipboard.setData(ClipboardData(text: invite['inviteCode'].toString()));
                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Invite code copié: ${invite['inviteCode']}')));
                      setState(() {});
                    }, child: const Text('Créer invite')),
                    FutureBuilder(
                      future: ref.read(apiProvider).committeeBaptemeInvites(committeeId: widget.committeeId, campaignId: _campaignId!),
                      builder: (context, invitesSnap) {
                        if (!invitesSnap.hasData) return const SizedBox.shrink();
                        final invites = (invitesSnap.data!['items'] as List<dynamic>);
                        return Column(children: [for (final i in invites) ListTile(title: Text(i['blueDisplayName'].toString()), subtitle: Text('${i['status']} · ${i['inviteCode']}'))]);
                      },
                    ),
                    SelectableText(ref.read(apiProvider).committeeBaptemeInvitesExportUrl(committeeId: widget.committeeId, campaignId: _campaignId!)),
                    SelectableText(ref.read(apiProvider).committeeBaptemeSlotsExportUrl(committeeId: widget.committeeId, campaignId: _campaignId!)),
                  ],
                ],
              );
            },
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
