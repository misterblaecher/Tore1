import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../../core/network/error_mapper.dart';
import '../../state.dart';
import '../../shared/widgets/sparkline.dart';
import 'chart_models.dart';
import 'chart_providers.dart';

class DrinkChartDetailScreen extends ConsumerWidget {
  final MenuDrinkMeta drink;
  const DrinkChartDetailScreen({super.key, required this.drink});

  String _eur(int cents) => (cents / 100.0).toStringAsFixed(2);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;

    if (eventId == null) {
      return Scaffold(
        appBar: AppBar(title: Text(drink.name)),
        body: const Center(child: Text('Sélectionne un event pour voir les graphiques.')),
      );
    }

    final historyAsync = ref.watch(
      drinkHistoryProvider(DrinkHistoryArgs(eventId: eventId, drinkId: drink.drinkId)),
    );

    return Scaffold(
      appBar: AppBar(title: Text(drink.name)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: historyAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorState(
            message: ErrorMapper.message(e),
            onRetry: () => ref.invalidate(
              drinkHistoryProvider(DrinkHistoryArgs(eventId: eventId, drinkId: drink.drinkId)),
            ),
          ),
          data: (points) {
            final series = points.isNotEmpty
                ? points.map((p) => p.priceEuro).toList()
                : <double>[drink.basePriceEuro, drink.effectivePriceEuro];

            final current = drink.effectivePriceCents;
            final base = drink.basePriceCents;
            final diff = current - base;
            final pct = base == 0 ? 0.0 : (diff / base) * 100.0;

            final minV = series.reduce((a, b) => a < b ? a : b);
            final maxV = series.reduce((a, b) => a > b ? a : b);

            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: _StatCard(
                        title: 'Base',
                        value: '${_eur(base)} €',
                        subtitle: 'prix d’entrée',
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _StatCard(
                        title: 'Actuel',
                        value: '${_eur(current)} €',
                        subtitle: '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%',
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text('Courbe (24h)', style: TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 10),
                        SizedBox(
                          height: 180,
                          child: _LineChart(values: series),
                        ),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Expanded(child: Text('Min: ${minV.toStringAsFixed(2)} €')),
                            Expanded(child: Text('Max: ${maxV.toStringAsFixed(2)} €', textAlign: TextAlign.end)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Card(
                  child: ListTile(
                    title: const Text('Mini-graph'),
                    subtitle: const Text('Vue rapide pour le menu'),
                    trailing: Sparkline(values: series),
                  ),
                ),
                const Spacer(),
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton.icon(
                    onPressed: () => ref.invalidate(
                      drinkHistoryProvider(DrinkHistoryArgs(eventId: eventId, drinkId: drink.drinkId)),
                    ),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Rafraîchir'),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          ElevatedButton(onPressed: onRetry, child: const Text('Réessayer')),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final String subtitle;
  const _StatCard({required this.title, required this.value, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 6),
            Text(value, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 4),
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _LineChart extends StatelessWidget {
  final List<double> values;
  const _LineChart({required this.values});

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return const Center(child: Text('Pas assez de données'));
    }
    return CustomPaint(
      painter: _LineChartPainter(values: values, color: Theme.of(context).colorScheme.primary),
      size: Size.infinite,
    );
  }
}

class _LineChartPainter extends CustomPainter {
  final List<double> values;
  final Color color;

  _LineChartPainter({required this.values, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final minV = values.reduce((a, b) => a < b ? a : b);
    final maxV = values.reduce((a, b) => a > b ? a : b);
    final range = (maxV - minV).abs() < 1e-9 ? 1.0 : (maxV - minV);

    final gridPaint = Paint()
      ..color = Colors.white.withOpacity(0.07)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    // Horizontal grid
    for (int i = 1; i <= 3; i++) {
      final y = size.height * (i / 4);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;

    final path = Path();
    for (int i = 0; i < values.length; i++) {
      final x = (i / (values.length - 1)) * size.width;
      final yNorm = (values[i] - minV) / range;
      final y = size.height - (yNorm * size.height);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, linePaint);

    // End dot
    final lastX = size.width;
    final lastY = size.height - (((values.last - minV) / range) * size.height);
    canvas.drawCircle(Offset(lastX, lastY), 3, Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _LineChartPainter oldDelegate) {
    return oldDelegate.values != values || oldDelegate.color != color;
  }
}
