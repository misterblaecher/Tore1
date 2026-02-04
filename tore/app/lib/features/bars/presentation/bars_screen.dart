import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../shared/widgets/app_background.dart';
import '../../../shared/widgets/ticker_strip.dart';
import '../../../shared/widgets/trading_card.dart';
import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../events/presentation/events_screen.dart';

class BarsScreen extends ConsumerWidget {
  const BarsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('TORÈ'),
      ),
      body: AppBackground(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TickerStrip(
              items: const [
                TickerItem('Dealer Beer', '+1.8%', Color(0xFF2ECC71)),
                TickerItem('Jupiler', '+3.0%', Color(0xFFF5C400)),
                TickerItem('CRASH', 'Shots', Color(0xFFCA005D)),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Bar selector',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            Expanded(
              child: FutureBuilder<List<dynamic>>(
                future: api.bars(),
                builder: (context, snap) {
                  if (snap.connectionState != ConnectionState.done) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snap.hasError) {
                    return Center(child: Text(ErrorMapper.message(snap.error as Object)));
                  }

                  final bars = snap.data ?? const [];
                  if (bars.isEmpty) {
                    return const Center(child: Text('Aucun bar'));
                  }

                  return ListView.separated(
                    itemCount: bars.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (context, i) {
                      final b = Map<String, dynamic>.from(bars[i] as Map);
                      final id = (b['id'] as num?)?.toInt() ?? 0;
                      final name = (b['name'] as String?) ?? '';
                      final city = (b['city'] as String?) ?? '';

                      return TradingCard(
                        onTap: () {
                          ref.read(appContextProvider.notifier).setBar(
                                barId: id,
                                barName: name.isEmpty ? 'Bar #$id' : name,
                              );
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => EventsScreen(
                                barId: id,
                                barName: name.isEmpty ? 'Bar #$id' : name,
                              ),
                            ),
                          );
                        },
                        child: Row(
                          children: [
                            Container(
                              width: 34,
                              height: 34,
                              decoration: BoxDecoration(
                                color: const Color(0xFFCA005D).withOpacity(0.16),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(
                                  color: const Color(0xFFCA005D).withOpacity(0.35),
                                ),
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                '${i + 1}',
                                style: Theme.of(context)
                                    .textTheme
                                    .labelLarge
                                    ?.copyWith(color: Colors.white),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    name.isEmpty ? '(Sans nom)' : name,
                                    style: Theme.of(context).textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    city,
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodyMedium
                                        ?.copyWith(color: const Color(0xFF9AA4B2)),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.chevron_right),
                          ],
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}