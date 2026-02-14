import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/app_context/app_context.dart';
import 'package:tore/features/events/presentation/event_config_providers.dart';
import 'package:tore/features/menu_market/presentation/menu_screen.dart';
import 'package:tore/features/navigation/presentation/polymarket_tab_screen.dart';
import 'package:tore/features/navigation/presentation/profile_screen.dart';
import 'package:tore/features/navigation/presentation/ticker_screen.dart';
import 'package:tore/features/qr/presentation/join_event_screen.dart';
import 'package:tore/features/qr/presentation/qr_scanner_screen.dart';
import 'package:tore/features/ticker/ticker_providers.dart';
import 'package:tore/features/wallet/presentation/wallet_screen.dart';
import 'package:tore/state.dart';
import 'package:tore/ui/components/components.dart';
import 'package:tore/shared/utils/write_gate.dart';

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
    final readOnly = isReadOnly(ref);

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
                ? (readOnly
                    ? null
                    : () async {
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
                      })
                : null,
          ),
          const SizedBox(height: 14),
          if (!hasEvent)
            ToreCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Scanne un QR join_event pour activer ton event.'),
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const JoinEventScreen())),
                    icon: const Icon(Icons.login_outlined),
                    label: const Text('Join event'),
                  ),
                ],
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
    return ToreCard(
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
            const ToreDivider(),
            const SizedBox(height: 8),
            TextButton.icon(onPressed: onLeave, icon: const Icon(Icons.logout), label: const Text('Quitter l’event')),
          ],
        ],
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
    return ToreChip(
      label: isPaused ? 'PAUSE' : 'LIVE',
      variant: isPaused ? ToreChipVariant.closed : ToreChipVariant.live,
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
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: ToreCard(
          child: Column(
            children: [
              Row(
                children: [
                  Icon(icon),
                  const SizedBox(width: 10),
                  Expanded(child: Text(title, style: const TextStyle(fontWeight: FontWeight.w700))),
                  const Icon(Icons.chevron_right),
                ],
              ),
              const SizedBox(height: 8),
              const ToreDivider(),
              const SizedBox(height: 8),
              Align(alignment: Alignment.centerLeft, child: Text(subtitle)),
            ],
          ),
        ),
      ),
    );
  }
}
