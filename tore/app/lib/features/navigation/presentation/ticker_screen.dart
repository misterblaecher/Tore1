import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/network_state_provider.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../qr/presentation/module_unavailable_screen.dart';
import '../../ticker/ticker_filter_provider.dart';
import '../../ticker/ticker_models.dart';
import '../../ticker/ticker_providers.dart';

class TickerScreen extends ConsumerWidget {
  const TickerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;
    if (eventId == null) {
      return const Scaffold(
          body:
              Center(child: Text('Sélectionne un event pour voir le ticker.')));
    }

    final configAsync = ref.watch(eventConfigProvider(eventId));
    final tickerEnabled = configAsync.maybeWhen(
      data: (cfg) => cfg.tickerEnabled,
      orElse: () => false,
    );
    if (!tickerEnabled) {
      return const ModuleUnavailableScreen(
        title: 'Ticker indisponible',
        message: 'Ce module est désactivé pour cet event.',
        reasonCode: 'module_off',
      );
    }

    final state = ref.watch(tickerControllerProvider(eventId));
    final selectedFilter = ref.watch(tickerFilterProvider(eventId));
    final network = ref.watch(networkStatusProvider);
    final filters = _buildFilters(state.items);

    final filteredItems = state.items.where((item) {
      switch (selectedFilter) {
        case TickerFilter.all:
          return true;
        case TickerFilter.prices:
          return item.type == 'price';
        case TickerFilter.orders:
          return item.type == 'order';
        case TickerFilter.gifts:
          return item.type == 'gift';
        case TickerFilter.alerts:
          return item.severity == 'warning' ||
              item.severity == 'error' ||
              item.type == 'broadcast';
      }
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ticker'),
        actions: [
          IconButton(
            onPressed: () =>
                ref.read(tickerControllerProvider(eventId).notifier).refresh(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () =>
            ref.read(tickerControllerProvider(eventId).notifier).refresh(),
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            SizedBox(
              height: 40,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: filters.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, index) {
                  final filter = filters[index];
                  return ChoiceChip(
                    selected: filter == selectedFilter,
                    label: Text(filter.label),
                    onSelected: (_) => ref
                        .read(tickerFilterProvider(eventId).notifier)
                        .state = filter,
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
            if (network == NetworkState.offline)
              Text(
                  'Offline • cache local${state.lastSyncAt != null ? ' • sync ${state.lastSyncAt}' : ''}',
                  style: const TextStyle(color: Colors.orange)),
            if (state.loading && state.items.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 100),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (filteredItems.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 100),
                child: Center(child: Text('Aucune activité.')),
              )
            else
              ...filteredItems.map((item) => _TickerTile(item: item)),
          ],
        ),
      ),
    );
  }

  List<TickerFilter> _buildFilters(List<TickerItem> items) {
    final kinds = items.map((e) => e.type).toSet();
    final out = <TickerFilter>[TickerFilter.all];
    if (kinds.contains('price')) out.add(TickerFilter.prices);
    if (kinds.contains('order')) out.add(TickerFilter.orders);
    if (kinds.contains('gift')) out.add(TickerFilter.gifts);
    if (kinds.contains('broadcast')) out.add(TickerFilter.alerts);
    return out;
  }
}

class _TickerTile extends StatelessWidget {
  const _TickerTile({required this.item});

  final TickerItem item;

  @override
  Widget build(BuildContext context) {
    final (title, subtitle, icon) = switch (item.payload) {
      BroadcastTickerPayload p => (
          'Broadcast',
          p.message,
          Icons.campaign_outlined
        ),
      GiftTickerPayload p => (
          'Gift',
          '${p.fromLabel} sent ${p.amount} Credits to ${p.toLabel}',
          Icons.card_giftcard
        ),
      PriceTickerPayload p => (
          'Price',
          '${p.drinkName} ${p.direction == 'up' ? '↑' : '↓'} ${p.fromPrice}→${p.toPrice}',
          Icons.show_chart
        ),
      OrderTickerPayload p => (
          'Order ${p.status}',
          '#${p.orderId} • ${p.totalTickets} Credits',
          Icons.receipt_long
        ),
    };

    return Card(
      child: ListTile(
        dense: true,
        leading: Icon(icon, size: 18),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: Text(item.ts.toLocal().toString().substring(11, 19),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 11)),
      ),
    );
  }
}
