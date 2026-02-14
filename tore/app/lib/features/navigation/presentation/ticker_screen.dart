import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../qr/presentation/module_unavailable_screen.dart';
import '../../ticker/ticker_models.dart';
import '../../ticker/ticker_providers.dart';
import '../../polymarket/market_detail_screen.dart';
import '../../wallet/presentation/wallet_screen.dart';

class TickerScreen extends ConsumerWidget {
  const TickerScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    final eventId = ctx.activeEventId;
    if (eventId == null) {
      return const Scaffold(body: Center(child: Text('Sélectionne un event pour voir le ticker.')));
    }

    final configAsync = ref.watch(eventConfigProvider(eventId));
    final tickerEnabled = configAsync.maybeWhen(
      data: (cfg) => cfg.menuEnabled || cfg.walletEnabled || cfg.polymarketEnabled,
      orElse: () => true,
    );
    if (!tickerEnabled) {
      return const ModuleUnavailableScreen(
        title: 'Ticker indisponible',
        message: 'Ce module est désactivé pour cet event.',
        reasonCode: 'module_off',
      );
    }

    final state = ref.watch(tickerControllerProvider(eventId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ticker'),
        actions: [
          IconButton(
            onPressed: () => ref.read(tickerControllerProvider(eventId).notifier).refresh(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(tickerControllerProvider(eventId).notifier).refresh(),
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            if (state.unstableConnection)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text('connexion instable', style: TextStyle(color: Colors.orange)),
              ),
            if (state.loading && state.items.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 100),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (state.items.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 100),
                child: Center(child: Text('Aucune activité.')),
              )
            else
              ...state.items.map((item) => _TickerTile(item: item, eventId: eventId)),
          ],
        ),
      ),
    );
  }
}

class _TickerTile extends StatelessWidget {
  const _TickerTile({required this.item, required this.eventId});

  final TickerItem item;
  final int eventId;

  Color _severityColor(BuildContext context) {
    switch (item.severity) {
      case 'warning':
        return Colors.orange;
      case 'success':
        return Colors.green;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: () {
          if (item.refKind == 'wallet_tx' || item.refKind == 'wallet_gift') {
            Navigator.of(context).push(MaterialPageRoute(builder: (_) => WalletScreen(eventId: eventId)));
            return;
          }
          if (item.refKind == 'wallet') {
            Navigator.of(context).push(MaterialPageRoute(builder: (_) => WalletScreen(eventId: eventId)));
            return;
          }
          if (item.refKind == 'polymarket_market') {
            final marketId = int.tryParse(item.refId ?? '');
            if (marketId != null) {
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => MarketDetailScreen(marketId: marketId)));
            }
            return;
          }
          if (item.refKind == 'order') {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Commande mise à jour.')),
            );
          }
        },
        title: Text(item.title),
        subtitle: Text(item.body),
        trailing: Wrap(
          spacing: 6,
          children: [
            Chip(label: Text(item.type, style: const TextStyle(fontSize: 11))),
            Chip(
              label: Text(item.severity, style: const TextStyle(fontSize: 11)),
              backgroundColor: _severityColor(context).withOpacity(0.16),
            ),
          ],
        ),
      ),
    );
  }
}
