import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/state.dart';

class CommunityScreen extends ConsumerStatefulWidget {
  const CommunityScreen({super.key});

  @override
  ConsumerState<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends ConsumerState<CommunityScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  final TextEditingController _search = TextEditingController();
  final TextEditingController _joinCode = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    _search.dispose();
    _joinCode.dispose();
    super.dispose();
  }

  String _idem() => 'orga-join-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Communauté'),
        bottom: TabBar(controller: _tabs, tabs: const [Tab(text: 'Explorer'), Tab(text: 'Mes Orgas')]),
      ),
      body: TabBarView(
        controller: _tabs,
        children: [
          FutureBuilder<Map<String, dynamic>>(
            future: api.listOrgas(query: _search.text.trim().isEmpty ? null : _search.text.trim()),
            builder: (context, snap) {
              final items = ((snap.data?['items'] as List?) ?? const []).cast<dynamic>();
              return ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  TextField(
                    controller: _search,
                    decoration: InputDecoration(
                      hintText: 'Rechercher une orga',
                      suffixIcon: IconButton(icon: const Icon(Icons.search), onPressed: () => setState(() {})),
                    ),
                    onSubmitted: (_) => setState(() {}),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: () async {
                      final code = _joinCode.text.trim();
                      if (code.isEmpty) return;
                      await api.joinOrgaByCode(code: code, idempotencyKey: _idem());
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Orga rejointe')));
                        _tabs.animateTo(1);
                        setState(() {});
                      }
                    },
                    icon: const Icon(Icons.group_add_outlined),
                    label: const Text('Join by code'),
                  ),
                  const SizedBox(height: 6),
                  TextField(controller: _joinCode, decoration: const InputDecoration(hintText: 'Code invitation')), 
                  const SizedBox(height: 12),
                  if (snap.connectionState == ConnectionState.waiting) const Center(child: CircularProgressIndicator()),
                  for (final raw in items)
                    Card(
                      child: ListTile(
                        title: Text((raw as Map)['name']?.toString() ?? 'Orga'),
                        subtitle: Text('${raw['city'] ?? '-'} • ${raw['org_type'] ?? '-'}'),
                      ),
                    ),
                ],
              );
            },
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
                        subtitle: Text('Rôle: ${item['role']}'),
                        trailing: FilledButton(
                          onPressed: () {},
                          child: const Text('Créer un event'),
                        ),
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
