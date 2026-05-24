import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../state.dart';
import '../data/orga_posts_cache.dart';

class OrgaPostsScreen extends ConsumerStatefulWidget {
  const OrgaPostsScreen(
      {super.key,
      required this.orgId,
      required this.canModerate,
      required this.canPost});

  final int orgId;
  final bool canModerate;
  final bool canPost;

  @override
  ConsumerState<OrgaPostsScreen> createState() => _OrgaPostsScreenState();
}

class _OrgaPostsScreenState extends ConsumerState<OrgaPostsScreen> {
  final _composer = TextEditingController();
  final _cache = OrgaPostsCache();
  bool _cacheBanner = false;

  String _idem() =>
      'orga-post-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  @override
  void dispose() {
    _composer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Posts orga')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: api.listOrgaPosts(widget.orgId),
        builder: (context, snap) {
          final onlineItems = ((snap.data?['items'] as List?) ?? const [])
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          return FutureBuilder<(List<Map<String, dynamic>>, bool)>(
            future: _cache.read(widget.orgId),
            builder: (context, cacheSnap) {
              final cacheItems =
                  cacheSnap.data?.$1 ?? const <Map<String, dynamic>>[];
              final isStale = cacheSnap.data?.$2 ?? true;
              final items = onlineItems.isNotEmpty ? onlineItems : cacheItems;
              _cacheBanner = onlineItems.isEmpty && cacheItems.isNotEmpty;
              if (onlineItems.isNotEmpty) {
                _cache.save(widget.orgId, onlineItems);
              }
              return ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  if (_cacheBanner)
                    MaterialBanner(
                        content: Text(isStale
                            ? 'Cache posts >24h'
                            : 'Affichage cache offline'),
                        actions: const [SizedBox.shrink()]),
                  if (widget.canPost)
                    Row(
                      children: [
                        Expanded(
                            child: TextField(
                                controller: _composer,
                                decoration: const InputDecoration(
                                    hintText: 'Écrire un post...'))),
                        IconButton(
                          onPressed:
                              canWrite(ref, intent: WriteIntent.nonCritical)
                                  ? () async {
                                      final txt = _composer.text.trim();
                                      if (txt.isEmpty) return;
                                      await api.createOrgaPost(
                                          orgId: widget.orgId,
                                          text: txt,
                                          idempotencyKey: _idem());
                                      _composer.clear();
                                      setState(() {});
                                    }
                                  : null,
                          icon: const Icon(Icons.send),
                        ),
                      ],
                    ),
                  const SizedBox(height: 8),
                  for (final item in items)
                    Card(
                      child: ListTile(
                        title: Text(item['text']?.toString() ?? '-'),
                        subtitle:
                            Text(item['author_user_id']?.toString() ?? ''),
                        trailing: widget.canModerate
                            ? PopupMenuButton<String>(
                                onSelected: (value) async {
                                  if (value == 'pin') {
                                    await api.pinOrgaPost(
                                        orgId: widget.orgId,
                                        postId: (item['id'] as num).toInt(),
                                        idempotencyKey: _idem());
                                  } else if (value == 'delete') {
                                    await api.deleteOrgaPost(
                                        orgId: widget.orgId,
                                        postId: (item['id'] as num).toInt(),
                                        idempotencyKey: _idem());
                                  }
                                  setState(() {});
                                },
                                itemBuilder: (_) => const [
                                  PopupMenuItem(
                                      value: 'pin', child: Text('Pin')),
                                  PopupMenuItem(
                                      value: 'delete', child: Text('Delete')),
                                ],
                              )
                            : null,
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
}
