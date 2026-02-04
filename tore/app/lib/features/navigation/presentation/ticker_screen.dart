import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../ticker/ticker_models.dart';
import '../../ticker/ticker_providers.dart';
import '../../leaderboard/presentation/leaderboard_screen.dart';

class TickerScreen extends ConsumerStatefulWidget {
  const TickerScreen({super.key});

  @override
  ConsumerState<TickerScreen> createState() => _TickerScreenState();
}

class _TickerScreenState extends ConsumerState<TickerScreen> {
  Timer? _timer;
  bool _paused = false;
  int? _eventId;

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startTimer(int eventId) {
    if (_eventId == eventId && _timer != null) return;
    _eventId = eventId;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (_paused) return;
      ref.invalidate(tickerProvider(eventId));
    });
  }

  @override
  Widget build(BuildContext context) {
    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;

    if (eventId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Ticker')),
        body: const Center(child: Text('Sélectionne un event pour voir le feed live.')),
      );
    }

    // start/refresh timer once we know the eventId
    _startTimer(eventId);

    final asyncItems = ref.watch(tickerProvider(eventId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ticker'),
        actions: [
          IconButton(
            tooltip: _paused ? 'Reprendre' : 'Pause',
            icon: Icon(_paused ? Icons.play_arrow : Icons.pause),
            onPressed: () => setState(() => _paused = !_paused),
          ),
          IconButton(
            tooltip: 'Rafraîchir',
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.invalidate(tickerProvider(eventId)),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(tickerProvider(eventId)),
        child: asyncItems.when(
          loading: () => ListView(
            children: const [
              SizedBox(height: 240),
              Center(child: CircularProgressIndicator()),
            ],
          ),
          error: (e, _) => ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(ErrorMapper.message(e)),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.invalidate(tickerProvider(eventId)),
                child: const Text('Réessayer'),
              ),
            ],
          ),
          data: (items) {
            if (items.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 220),
                  Center(child: Text('Aucune activité pour le moment.')),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: items.length + 1,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                if (i == 0) {
                  return _TickerHeader(
                    eventLabel: ctx.activeEventName ?? '#$eventId',
                    paused: _paused,
                    onOpenLeaderboard: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => LeaderboardScreen(eventId: eventId),
                        ),
                      );
                    },
                  );
                }
                final item = items[i - 1];
                return _TickerTile(item: item);
              },
            );
          },
        ),
      ),
    );
  }
}

class _TickerHeader extends StatelessWidget {
  final String eventLabel;
  final bool paused;
  final VoidCallback onOpenLeaderboard;

  const _TickerHeader({
    required this.eventLabel,
    required this.paused,
    required this.onOpenLeaderboard,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            const Icon(Icons.toll_outlined),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Event : $eventLabel\n${paused ? '⏸️ Pause' : '🔴 Live'}',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            TextButton(
              onPressed: onOpenLeaderboard,
              child: const Text('Classement'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TickerTile extends StatelessWidget {
  final TickerItem item;
  const _TickerTile({required this.item});

  IconData _iconForType(String type) {
    switch (type) {
      case 'order':
        return Icons.shopping_bag_outlined;
      case 'checkin':
        return Icons.qr_code_scanner_outlined;
      case 'move':
      case 'price_move':
        return Icons.show_chart_outlined;
      case 'leaderboard':
        return Icons.emoji_events_outlined;
      default:
        return Icons.bolt_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final time = TimeOfDay.fromDateTime(item.ts).format(context);
    return ListTile(
      leading: Icon(_iconForType(item.type)),
      title: Text(item.title),
      subtitle: Text(item.subtitle ?? time),
      trailing: Text(time),
    );
  }
}
