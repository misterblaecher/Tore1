import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import '../../shared/cache/cache_providers.dart';
import '../../state.dart';
import 'broadcast_repository.dart';

final broadcastRepositoryProvider = Provider<BroadcastRepository>((ref) {
  return BroadcastRepository(
      ref.watch(apiProvider), ref.watch(cacheStoreProvider));
});

final broadcastFeedProvider =
    FutureProvider.family<BroadcastResult, int>((ref, eventId) async {
  return ref.watch(broadcastRepositoryProvider).fetch(eventId);
});

class BroadcastScreen extends ConsumerWidget {
  const BroadcastScreen(
      {super.key, required this.eventId, this.canCompose = false});

  final int eventId;
  final bool canCompose;

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
              if (canCompose) _BroadcastComposer(eventId: eventId),
              if (data.fromCache)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                      'Offline cache • dernier sync ${data.lastSyncAt?.toLocal().toString() ?? '-'}'),
                ),
              ...data.items.map((item) => Card(
                    child: ListTile(
                      title: Text(item.message),
                      subtitle: Text(
                          '${item.level.toUpperCase()} • ${item.createdAt.toLocal()}'),
                    ),
                  )),
              if (data.items.isEmpty)
                const Padding(
                    padding: EdgeInsets.only(top: 80),
                    child: Center(child: Text('Aucun broadcast.'))),
            ],
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) =>
            const Center(child: Text('Impossible de charger les broadcasts.')),
      ),
    );
  }
}

class _BroadcastComposer extends ConsumerStatefulWidget {
  const _BroadcastComposer({required this.eventId});
  final int eventId;

  @override
  ConsumerState<_BroadcastComposer> createState() => _BroadcastComposerState();
}

class _BroadcastComposerState extends ConsumerState<_BroadcastComposer> {
  final _controller = TextEditingController();
  String _level = 'info';
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final message = _controller.text.trim();
    if (message.isEmpty || _sending) return;
    if (_level == 'urgent') {
      final confirmed = await showDialog<bool>(
            context: context,
            builder: (context) => AlertDialog(
              title: const Text('Envoyer une annonce urgente ?'),
              content: const Text(
                  'Cette annonce sera immédiatement visible par les participants.'),
              actions: [
                TextButton(
                    onPressed: () => Navigator.pop(context, false),
                    child: const Text('Annuler')),
                FilledButton(
                    onPressed: () => Navigator.pop(context, true),
                    child: const Text('Confirmer')),
              ],
            ),
          ) ??
          false;
      if (!confirmed) return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await ref.read(broadcastRepositoryProvider).create(
            eventId: widget.eventId,
            message: message,
            level: _level,
            idempotencyKey:
                'mobile-broadcast-${DateTime.now().microsecondsSinceEpoch}',
          );
      _controller.clear();
      ref.invalidate(broadcastFeedProvider(widget.eventId));
      final _ = await ref.refresh(broadcastFeedProvider(widget.eventId).future);
    } on DioException catch (error) {
      final detail = error.response?.data is Map
          ? (error.response!.data as Map)['detail']
          : null;
      final retry = detail is Map ? detail['retry_after_seconds'] : null;
      setState(() => _error = error.response?.statusCode == 429
          ? 'Trop d’annonces. Réessaie dans ${retry ?? 'quelques'} secondes.'
          : 'Annonce refusée par le serveur.');
    } catch (_) {
      setState(() => _error = 'Annonce impossible à envoyer.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Nouvelle annonce',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            TextField(
              controller: _controller,
              maxLength: 240,
              minLines: 1,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Message court'),
            ),
            DropdownButtonFormField<String>(
              initialValue: _level,
              items: const [
                DropdownMenuItem(value: 'info', child: Text('Normal')),
                DropdownMenuItem(value: 'urgent', child: Text('Urgent')),
              ],
              onChanged: _sending
                  ? null
                  : (value) => setState(() => _level = value ?? 'info'),
              decoration: const InputDecoration(labelText: 'Priorité'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ],
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: FilledButton.icon(
                onPressed: _sending ? null : _send,
                icon: _sending
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.send_outlined),
                label: const Text('Envoyer'),
              ),
            ),
          ]),
        ),
      );
}
