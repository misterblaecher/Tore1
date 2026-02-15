import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shared/cache/cache_providers.dart';
import '../../state.dart';
import 'broadcast_repository.dart';

final broadcastRepositoryProvider = Provider<BroadcastRepository>((ref) {
  return BroadcastRepository(ref.watch(apiProvider), ref.watch(cacheStoreProvider));
});

final broadcastFeedProvider = FutureProvider.family<BroadcastResult, int>((ref, eventId) async {
  return ref.watch(broadcastRepositoryProvider).fetch(eventId);
});

class BroadcastScreen extends ConsumerWidget {
  const BroadcastScreen({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(broadcastFeedProvider(eventId));
    return Scaffold(
      appBar: AppBar(title: const Text('Broadcast')),
      body: async.when(
        data: (data) => RefreshIndicator(
          onRefresh: () => ref.refresh(broadcastFeedProvider(eventId).future),
          child: ListView(
            padding: const EdgeInsets.all(12),
            children: [
              if (data.fromCache)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text('Offline cache • dernier sync ${data.lastSyncAt?.toLocal().toString() ?? '-'}'),
                ),
              ...data.items.map((item) => Card(
                    child: ListTile(
                      title: Text(item.message),
                      subtitle: Text('${item.level.toUpperCase()} • ${item.createdAt.toLocal()}'),
                    ),
                  )),
              if (data.items.isEmpty) const Padding(padding: EdgeInsets.only(top: 80), child: Center(child: Text('Aucun broadcast.'))),
            ],
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const Center(child: Text('Impossible de charger les broadcasts.')),
      ),
    );
  }
}
