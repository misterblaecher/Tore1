import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/features/community/community_models.dart';
import 'package:tore/features/community/data/community_explorer_cache.dart';
import 'package:tore/features/events/presentation/create_event_wizard_screen.dart';
import 'package:tore/features/qr/presentation/code_entry_sheet.dart';
import 'package:tore/features/qr/presentation/join_event_screen.dart';
import 'package:tore/state.dart';

import 'orga_detail_screen.dart';

class CommunityScreen extends ConsumerStatefulWidget {
  const CommunityScreen({super.key});

  @override
  ConsumerState<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends ConsumerState<CommunityScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final TextEditingController _search = TextEditingController();
  final TextEditingController _joinCode = TextEditingController();
  final TextEditingController _city = TextEditingController();
  final CommunityExplorerCache _cache = CommunityExplorerCache();

  Timer? _debounce;
  List<OrgaSummary> _items = const [];
  String? _nextCursor;
  bool _loading = false;
  bool _loadingMore = false;
  bool _isCached = false;
  DateTime? _lastSyncAt;
  String _type = 'all';
  String _sort = 'recent';
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _loadExplorer(reset: true);
  }

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    _joinCode.dispose();
    _city.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  String _idem() => 'orga-join-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  Map<String, String> _params({String? cursor}) => {
        if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
        if (_type != 'all') 'type': _type,
        if (_city.text.trim().isNotEmpty) 'city': _city.text.trim(),
        'sort': _sort,
        if (cursor != null) 'cursor': cursor,
        'limit': '20',
      };

  Future<void> _loadExplorer({required bool reset, bool fromRetry = false}) async {
    final api = ref.read(apiProvider);
    final cursor = reset ? null : _nextCursor;
    if (reset) {
      setState(() {
        _loading = true;
        _error = null;
      });
      final cache = await _cache.read(_params());
      if (cache.payload != null) {
        final cachedItems = ((cache.payload!['items'] as List?) ?? const [])
            .map((e) => OrgaSummary.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList();
        setState(() {
          _items = cachedItems;
          _nextCursor = cache.payload!['nextCursor']?.toString();
          _isCached = true;
          _lastSyncAt = cache.lastSyncAt;
        });
      }
    } else {
      setState(() => _loadingMore = true);
    }

    try {
      final res = await api.listOrgas(
        q: _search.text.trim().isEmpty ? null : _search.text.trim(),
        type: _type == 'all' ? null : _type,
        city: _city.text.trim().isEmpty ? null : _city.text.trim(),
        sort: _sort,
        cursor: cursor,
        limit: 20,
      );
      final networkItems = ((res['items'] as List?) ?? const [])
          .map((e) => OrgaSummary.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      final next = res['nextCursor']?.toString() ?? res['next_cursor']?.toString();
      final updated = reset ? networkItems : [..._items, ...networkItems];
      if (mounted) {
        setState(() {
          _items = updated;
          _nextCursor = next;
          _isCached = false;
          _lastSyncAt = DateTime.now();
          _error = null;
        });
      }
      if (reset) {
        await _cache.save(_params(), {'items': networkItems.map((e) => {
          'id': e.id,
          'name': e.name,
          'city': e.city,
          'type': e.type,
          'joinMode': e.joinMode,
          'followersCount': e.followersCount,
          'lastActiveAt': e.lastActiveAt?.toIso8601String(),
        }).toList(), 'nextCursor': next});
      }
    } catch (_) {
      if (mounted && (_items.isEmpty || fromRetry)) {
        setState(() => _error = 'Mode lecture (cache)');
      }
    } finally {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  void _onSearchChanged(String _) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: communityExplorerDebounceMs), () => _loadExplorer(reset: true));
  }

  String _ago(DateTime? dt) {
    if (dt == null) return '';
    final d = DateTime.now().difference(dt);
    if (d.inDays > 0) return 'actif il y a ${d.inDays}j';
    if (d.inHours > 0) return 'actif il y a ${d.inHours}h';
    return 'actif il y a ${d.inMinutes.clamp(1, 59)}min';
  }

  void showCodeEntrySheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => const CodeEntrySheet(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateEventWizardScreen())),
        icon: const Icon(Icons.add),
        label: const Text('+ Créer'),
      ),
      appBar: AppBar(
        title: const Text('Communauté'),
        actions: [
          TextButton.icon(
            onPressed: () => showCodeEntrySheet(context),
            icon: const Icon(Icons.login_outlined),
            label: const Text('Entrer un code'),
          ),
        ],
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Explorer'), Tab(text: 'Mes Orgas')]),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          ListView(
            padding: const EdgeInsets.all(12),
            children: [
              TextField(
                controller: _search,
                onChanged: _onSearchChanged,
                decoration: InputDecoration(
                  hintText: 'Rechercher une orga',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _search.text.isEmpty
                      ? null
                      : IconButton(
                          onPressed: () {
                            _search.clear();
                            _loadExplorer(reset: true);
                          },
                          icon: const Icon(Icons.clear),
                        ),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final item in const {'all': 'Tous', 'comite': 'Comité', 'bar': 'Bar', 'asso': 'Asso', 'autre': 'Autre'}.entries)
                  ChoiceChip(
                    label: Text(item.value),
                    selected: _type == item.key,
                    onSelected: (_) {
                      setState(() => _type = item.key);
                      _loadExplorer(reset: true);
                    },
                  ),
              ]),
              const SizedBox(height: 8),
              Wrap(spacing: 8, children: [
                ChoiceChip(label: const Text('Récent'), selected: _sort == 'recent', onSelected: (_) {
                  setState(() => _sort = 'recent');
                  _loadExplorer(reset: true);
                }),
                ChoiceChip(label: const Text('Populaire'), selected: _sort == 'popular', onSelected: (_) {
                  setState(() => _sort = 'popular');
                  _loadExplorer(reset: true);
                }),
              ]),
              const SizedBox(height: 8),
              TextField(controller: _city, onSubmitted: (_) => _loadExplorer(reset: true), decoration: const InputDecoration(hintText: 'Ville (optionnel)')),
              const SizedBox(height: 8),
              if (_isCached)
                Container(
                  padding: const EdgeInsets.all(8),
                  color: Colors.amber.withOpacity(0.2),
                  child: Text('CACHE • ${_lastSyncAt != null ? _lastSyncAt!.toLocal().toString().substring(0, 16) : ''}'),
                ),
              if (_error != null)
                ListTile(
                  title: Text(_error!),
                  subtitle: const Text('Mode lecture (cache)'),
                  trailing: TextButton(onPressed: () => _loadExplorer(reset: true, fromRetry: true), child: const Text('Retry')),
                ),
              FilledButton.icon(
                onPressed: () async {
                  final code = _joinCode.text.trim();
                  if (code.isEmpty) return;
                  await api.joinOrgaByCode(code: code, idempotencyKey: _idem());
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Orga rejointe')));
                    _tabs.animateTo(1);
                  }
                },
                icon: const Icon(Icons.group_add_outlined),
                label: const Text('Join by code'),
              ),
              const SizedBox(height: 6),
              TextField(controller: _joinCode, decoration: const InputDecoration(hintText: 'Code invitation')),
              const SizedBox(height: 12),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (!_loading && _items.isEmpty)
                ListTile(
                  title: const Text('Aucun résultat'),
                  trailing: TextButton(
                    onPressed: () {
                      _search.clear();
                      _city.clear();
                      setState(() {
                        _type = 'all';
                        _sort = 'recent';
                      });
                      _loadExplorer(reset: true);
                    },
                    child: const Text('Reset filtres'),
                  ),
                ),
              for (final item in _items)
                Card(
                  child: ListTile(
                    title: Text(item.name),
                    subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(item.city ?? '-'),
                      Wrap(spacing: 6, children: [
                        Chip(label: Text(item.type ?? '-')),
                        Chip(label: Text(item.joinMode)),
                      ]),
                      Text('${item.followersCount} suivent ${_ago(item.lastActiveAt)}'.trim()),
                    ]),
                    trailing: FilledButton(
                      onPressed: null,
                      child: Text(orgaPrimaryCtaLabel(joinMode: parseOrgaJoinMode(item.joinMode))),
                    ),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaDetailScreen(orgId: item.id))),
                  ),
                ),
              if (_nextCursor != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: OutlinedButton(
                    onPressed: _loadingMore ? null : () => _loadExplorer(reset: false),
                    child: Text(_loadingMore ? 'Chargement…' : 'Charger plus'),
                  ),
                ),
            ],
          ),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: api.myOrgas(),
            builder: (context, snap) {
              final items = snap.data ?? const [];
              return ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  for (final item in items)
                    Card(
                      child: ListTile(
                        title: Text((item['orga']?['name'] ?? 'Orga').toString()),
                        subtitle: Text('Rôle: ${item['role']} • Status: ${item['status']}'),
                        onTap: () {
                          final orgId = ((item['orga']?['id'] as num?) ?? 0).toInt();
                          if (orgId <= 0) return;
                          Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaDetailScreen(orgId: orgId, myRole: (item['role'] ?? '').toString())));
                        },
                      ),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
