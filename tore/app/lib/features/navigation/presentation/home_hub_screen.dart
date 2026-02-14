import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../state.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../menu_market/presentation/menu_screen.dart';
import '../../qr/presentation/qr_scanner_screen.dart';
import '../../ticker/ticker_providers.dart';
import '../../wallet/presentation/wallet_screen.dart';
import 'polymarket_tab_screen.dart';
import 'profile_screen.dart';
import 'ticker_screen.dart';

class HomeHubScreen extends ConsumerWidget {
  const HomeHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    final hasEvent = ctx.hasActiveEvent;
    final configAsync = hasEvent ? ref.watch(eventConfigProvider(ctx.activeEventId!)) : null;
    final eventAsync = hasEvent ? ref.watch(_eventDetailsProvider(ctx.activeEventId!)) : null;
    final config = configAsync?.maybeWhen(data: (c) => c, orElse: () => null);
    final eventState = eventAsync?.maybeWhen(data: _readEventState, orElse: () => 'LIVE') ?? 'LIVE';

    final menuOn = config?.menuEnabled ?? false;
    final walletOn = config?.walletEnabled ?? false;
    final polymarketOn = config?.polymarketEnabled ?? false;
    final tickerOn = menuOn || walletOn || polymarketOn;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Home Hub'),
        actions: [
          if (hasEvent && tickerOn)
            IconButton(
              tooltip: 'Ticker',
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const TickerScreen())),
              icon: const Icon(Icons.toll_outlined),
            ),
          IconButton(
            tooltip: 'Profil',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ProfileScreen())),
            icon: const Icon(Icons.settings_outlined),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen())),
        icon: const Icon(Icons.qr_code_scanner_outlined),
        label: const Text('Scanner QR'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _EventHeader(
            title: hasEvent ? (ctx.activeEventName ?? 'Event #${ctx.activeEventId}') : 'Aucun event actif',
            status: hasEvent ? eventState : 'OFF',
            onLeave: hasEvent
                ? () async {
                    final ok = await showDialog<bool>(
                          context: context,
                          builder: (_) => AlertDialog(
                            title: const Text('Quitter l’event ?'),
                            content: const Text('Tu vas revenir en mode libre.'),
                            actions: [
                              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Annuler')),
                              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Quitter')),
                            ],
                          ),
                        ) ??
                        false;
                    if (ok) ref.read(appContextProvider.notifier).leaveEvent();
                  }
                : null,
          ),
          const SizedBox(height: 14),
          if (!hasEvent)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('Scanne un QR join_event pour activer ton event.'),
              ),
            ),
          if (hasEvent && menuOn)
            _ModuleCard(
              icon: Icons.restaurant_menu_outlined,
              title: 'Menu',
              subtitle: 'Commander dans ton event',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => MenuScreen(eventId: ctx.activeEventId!))),
            ),
          if (hasEvent && walletOn)
            _ModuleCard(
              icon: Icons.account_balance_wallet_outlined,
              title: 'Wallet',
              subtitle: 'Solde, historique et My Wallet QR',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => WalletScreen(eventId: ctx.activeEventId!))),
            ),
          if (hasEvent && polymarketOn)
            _ModuleCard(
              icon: Icons.casino_outlined,
              title: 'Polymarket',
              subtitle: 'Markets et positions',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PolymarketTabScreen())),
            ),
          if (hasEvent && tickerOn)
            _ModuleCard(
              icon: Icons.toll_outlined,
              title: 'Ticker',
              subtitle: 'Activité live',
              onTap: () {
                final eventId = ctx.activeEventId;
                if (eventId != null) {
                  ref.read(tickerControllerProvider(eventId).notifier).refresh();
                }
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => const TickerScreen()));
              },
            ),
        ],
      ),
    );
  }
}

class _EventHeader extends StatelessWidget {
  const _EventHeader({required this.title, required this.status, this.onLeave});

  final String title;
  final String status;
  final VoidCallback? onLeave;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(title, style: Theme.of(context).textTheme.titleLarge)),
                if (status != 'OFF') _EventStateBadge(status: status),
              ],
            ),
            if (onLeave != null) ...[
              const SizedBox(height: 8),
              TextButton.icon(onPressed: onLeave, icon: const Icon(Icons.logout), label: const Text('Quitter l’event')),
            ],
          ],
        ),
      ),
    );
  }
}

class _EventStateBadge extends StatelessWidget {
  const _EventStateBadge({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final normalized = status.toUpperCase();
    final isPaused = normalized == 'PAUSE' || normalized == 'PAUSED' || normalized == 'READ_ONLY' || normalized == 'FROZEN';
    return Chip(
      label: Text(isPaused ? 'PAUSE' : 'LIVE'),
      avatar: Icon(Icons.circle, size: 12, color: isPaused ? Colors.orangeAccent : Colors.greenAccent),
    );
  }
}

final _eventDetailsProvider = FutureProvider.family<Map<String, dynamic>, int>((ref, eventId) async {
  return ref.read(apiProvider).event(eventId);
});

String _readEventState(Map<String, dynamic> event) {
  final value = (event['state'] ?? event['status'] ?? event['event_state'] ?? 'LIVE').toString().toUpperCase();
  return value;
}

class _ModuleCard extends StatelessWidget {
  const _ModuleCard({required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Icon(icon),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
