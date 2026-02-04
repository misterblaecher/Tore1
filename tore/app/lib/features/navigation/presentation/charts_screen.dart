import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../bars/presentation/bars_screen.dart';
import '../../charts/chart_detail_screen.dart';
import '../../charts/chart_models.dart';
import '../../charts/chart_providers.dart';
import '../../../shared/widgets/sparkline.dart';

class ChartsScreen extends ConsumerStatefulWidget {
  const ChartsScreen({super.key});

  @override
  ConsumerState<ChartsScreen> createState() => _ChartsScreenState();
}

class _ChartsScreenState extends ConsumerState<ChartsScreen> {
  String _query = '';
  bool _miniGraphs = false;

  @override
  Widget build(BuildContext context) {
    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;

    if (eventId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Graph')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Sélectionne un event pour voir les courbes de prix.',
                style: TextStyle(fontSize: 16),
              ),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const BarsScreen()),
                ),
                icon: const Icon(Icons.near_me_outlined),
                label: const Text('Choisir un bar / event'),
              ),
            ],
          ),
        ),
      );
    }

    final drinksAsync = ref.watch(eventMenuDrinksProvider(eventId));
    final moversAsync = ref.watch(topMoversProvider(eventId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Graph'),
        actions: [
          IconButton(
            tooltip: 'Rafraîchir',
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.invalidate(eventMenuDrinksProvider(eventId));
              ref.invalidate(topMoversProvider(eventId));
            },
          )
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(eventMenuDrinksProvider(eventId));
          ref.invalidate(topMoversProvider(eventId));
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Event : ${ctx.activeEventName ?? '#$eventId'}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              decoration: const InputDecoration(
                hintText: 'Rechercher une boisson…',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
              onChanged: (v) => setState(() => _query = v.trim().toLowerCase()),
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              value: _miniGraphs,
              onChanged: (v) => setState(() => _miniGraphs = v),
              title: const Text('Mini-graphs'),
              subtitle: const Text('Affiche une sparkline par boisson (plus d’appels réseau).'),
            ),
            const SizedBox(height: 10),

            // Top movers
            moversAsync.when(
              loading: () => const SizedBox.shrink(),
              error: (e, _) => const SizedBox.shrink(),
              data: (items) {
                if (items.isEmpty) return const SizedBox.shrink();
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Top movers', style: TextStyle(fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: items.take(6).map((m) {
                            final name = (m['name'] ?? m['drink_name'] ?? '').toString();
                            final pct = m['pct'] ?? m['change_pct'] ?? m['change'] ?? 0;
                            return Chip(
                              label: Text('$name ${pct.toString()}%'),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),

            const SizedBox(height: 12),

            drinksAsync.when(
              loading: () => const Center(child: Padding(
                padding: EdgeInsets.only(top: 40),
                child: CircularProgressIndicator(),
              )),
              error: (e, _) => Padding(
                padding: const EdgeInsets.only(top: 40),
                child: Center(child: Text(ErrorMapper.message(e))),
              ),
              data: (drinks) {
                final filtered = _query.isEmpty
                    ? drinks
                    : drinks.where((d) => d.name.toLowerCase().contains(_query)).toList();

                if (filtered.isEmpty) {
                  return const Padding(
                    padding: EdgeInsets.only(top: 30),
                    child: Center(child: Text('Aucune boisson')),
                  );
                }

                return Column(
                  children: filtered.map((drink) => _DrinkRow(
                    drink: drink,
                    eventId: eventId,
                    showSparkline: _miniGraphs,
                  )).toList(),
                );
              },
            ),
            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }
}

class _DrinkRow extends ConsumerWidget {
  final MenuDrinkMeta drink;
  final int eventId;
  final bool showSparkline;

  const _DrinkRow({
    required this.drink,
    required this.eventId,
    required this.showSparkline,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pct = drink.changePct;
    final subtitle = drink.type.isEmpty
        ? '${drink.effectivePriceEuro.toStringAsFixed(2)} €'
        : '${drink.type} • ${drink.effectivePriceEuro.toStringAsFixed(2)} €';

    Widget? trailing;
    if (showSparkline) {
      final histAsync = ref.watch(
        drinkHistoryProvider(DrinkHistoryArgs(eventId: eventId, drinkId: drink.drinkId)),
      );
      trailing = histAsync.maybeWhen(
        data: (points) {
          final series = points.isNotEmpty
              ? points.map((p) => p.priceEuro).toList()
              : <double>[drink.basePriceEuro, drink.effectivePriceEuro];
          return Sparkline(values: series);
        },
        orElse: () => const SizedBox(width: 68, height: 28),
      );
    } else {
      trailing = Text(
        '${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(1)}%',
        style: TextStyle(
          fontWeight: FontWeight.w700,
          color: pct >= 0 ? Colors.greenAccent : Colors.redAccent,
        ),
      );
    }

    return Card(
      child: ListTile(
        title: Text(drink.name),
        subtitle: Text(subtitle),
        trailing: trailing,
        onTap: () {
          Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => DrinkChartDetailScreen(drink: drink),
            ),
          );
        },
      ),
    );
  }
}
