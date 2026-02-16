import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../../../core/perf/prefetch.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../broadcast/broadcast_screen.dart';
import '../../menu_market/presentation/menu_screen.dart';
import 'event_polymarket_screen.dart';
import 'event_ranking_screen.dart';
import '../../navigation/presentation/ticker_screen.dart';
import '../../qr/presentation/module_unavailable_screen.dart';
import '../../wallet/presentation/wallet_screen.dart';
import '../../hunt/presentation/hunt_screen.dart';
import '../../battles/presentation/battles_screen.dart';
import '../../safety/presentation/safety_screen.dart';
import 'music_vote_screen.dart';
import 'active_event_context_provider.dart';
import '../../map_calendar/presentation/event_map_screen.dart';

class EventHubScreen extends ConsumerWidget {
  const EventHubScreen({super.key, required this.eventId, required this.eventName});

  final int eventId;
  final String eventName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contextAsync = ref.watch(activeEventContextProvider);
    final eventCtx = contextAsync.valueOrNull;
    final state = (eventCtx?.eventState ?? 'LIVE').toUpperCase();
    final title = eventCtx?.eventName ?? eventName;
    final modules = eventCtx?.modulesOn ?? const <String, bool>{};

    WidgetsBinding.instance.addPostFrameCallback((_) {
      prefetchEventEssentials(ref, eventId, modulesOn: modules);
    });

    final readOnly = isReadOnly(ref);
    final network = ref.watch(networkStatusProvider);
    final degradedBlocked = network == NetworkState.degraded;
    final runtimeBlocked = isWriteBlockedByEventState(state);
    final globalBlocked = isWriteBlocked(readOnly: readOnly, runtimeBlocked: runtimeBlocked, degradedBlocked: degradedBlocked);
    final eventReason = eventWriteBlockedReason(state);

    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.read(activeEventContextProvider.notifier).refresh(force: true),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Header(state: state, lastUpdatedAt: eventCtx?.lastUpdatedAt),
          const SizedBox(height: 10),
          if (_stateBanner(state) != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: ServiceLimitedBanner(message: _stateBanner(state)!),
            ),
          if (globalBlocked)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: ServiceLimitedBanner(
                message: eventReason ?? writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeState: state),
              ),
            ),
          ..._moduleCards(context, modules, eventId),
        ],
      ),
    );
  }

  List<Widget> _moduleCards(BuildContext context, Map<String, bool> modulesOn, int eventId) {
    final modules = [
      _module(
        key: 'menu',
        title: 'Menu',
        subtitle: 'Commander rapidement',
        icon: Icons.restaurant_menu_outlined,
        builder: (_) => MenuScreen(eventId: eventId),
      ),
      _module(
        key: 'wallet',
        title: 'Wallet',
        subtitle: 'Tickets & solde',
        icon: Icons.account_balance_wallet_outlined,
        builder: (_) => WalletScreen(eventId: eventId),
      ),
      _module(
        key: 'ticker',
        title: 'Ticker',
        subtitle: 'Flux live de l’event',
        icon: Icons.toll_outlined,
        builder: (_) => const TickerScreen(),
      ),
      _module(
        key: 'polymarket_event',
        aliases: const ['polymarket'],
        title: 'Polymarket EVENT',
        subtitle: 'Markets de cet event',
        icon: Icons.casino_outlined,
        builder: (_) => const EventPolymarketScreen(),
      ),
      _module(
        key: 'classement',
        title: 'Classement',
        subtitle: 'Top participants',
        icon: Icons.leaderboard_outlined,
        builder: (_) => EventRankingScreen(eventId: eventId),
      ),
      _module(key: 'hunt', title: 'Hunt', subtitle: 'Chasse QR', icon: Icons.map_outlined, builder: (_) => HuntScreen(eventId: eventId)),
      _module(key: 'battles', title: 'Battles', subtitle: 'Affonds en direct', icon: Icons.sports_mma_outlined, builder: (_) => BattlesScreen(eventId: eventId)),
      _module(key: 'music_vote', aliases: const ['music', 'vote'], title: 'Music vote', subtitle: 'Vote la prochaine track', icon: Icons.music_note_outlined, builder: (_) => MusicVoteScreen(eventId: eventId)),
      _module(key: 'safety', title: 'Safe Kit', subtitle: 'Buddy, check-ins et alerte ORGA', icon: Icons.health_and_safety_outlined, builder: (_) => SafetyScreen(eventId: eventId)),
      _module(key: 'map', title: 'Carte', subtitle: 'Lieu, trajets & navettes', icon: Icons.map_outlined, builder: (_) => EventMapScreen(eventId: eventId)),
      _module(
        key: 'broadcast',
        title: 'Broadcast',
        subtitle: 'Annonces de l’event',
        icon: Icons.campaign_outlined,
        builder: (_) => BroadcastScreen(eventId: eventId),
      ),
    ];

    final enabled = modules.where((module) => module.isEnabled(modulesOn)).toList();
    if (enabled.isEmpty) {
      return const [
        Padding(
          padding: EdgeInsets.only(top: 8),
          child: Text('Aucun module actif pour cet event.'),
        ),
      ];
    }

    return enabled
        .map(
          (module) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: module.builder)),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(module.icon),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(module.title, style: const TextStyle(fontWeight: FontWeight.w700)),
                            const SizedBox(height: 3),
                            Text(module.subtitle, style: Theme.of(context).textTheme.bodySmall),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right),
                    ],
                  ),
                ),
              ),
            ),
          ),
        )
        .toList();
  }

  _HubModule _module({
    required String key,
    List<String> aliases = const [],
    required String title,
    required String subtitle,
    required IconData icon,
    required WidgetBuilder builder,
  }) {
    return _HubModule(key: key, aliases: aliases, title: title, subtitle: subtitle, icon: icon, builder: builder);
  }

  _HubModule _moduleUnavailable({
    required String key,
    required String title,
    required String subtitle,
    required IconData icon,
  }) {
    return _module(
      key: key,
      title: title,
      subtitle: subtitle,
      icon: icon,
      builder: (_) => ModuleUnavailableScreen(
        title: title,
        message: 'Module activé mais pas encore dispo dans cette build',
        reasonCode: 'module_not_implemented',
      ),
    );
  }

  String? _stateBanner(String state) {
    switch (state.toUpperCase()) {
      case 'PAUSE':
        return 'Pause — commandes bloquées';
      case 'MENU_ONLY':
        return 'Menu only — commandes bloquées';
      case 'DEGRADED':
        return 'Réseau instable — actions sensibles bloquées';
      case 'FROZEN':
        return 'FROZEN — aucune action';
      default:
        return null;
    }
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.state, this.lastUpdatedAt});

  final String state;
  final DateTime? lastUpdatedAt;

  @override
  Widget build(BuildContext context) {
    final label = state == 'LIVE' ? 'LIVE' : state;
    final blocked = state != 'LIVE';
    return Row(
      children: [
        Chip(
          label: Text(label),
          backgroundColor: blocked ? Colors.orange.shade100 : Colors.green.shade100,
        ),
        const SizedBox(width: 8),
        if (lastUpdatedAt != null)
          Text('Maj ${TimeOfDay.fromDateTime(lastUpdatedAt!.toLocal()).format(context)}', style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _HubModule {
  const _HubModule({
    required this.key,
    required this.aliases,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.builder,
  });

  final String key;
  final List<String> aliases;
  final String title;
  final String subtitle;
  final IconData icon;
  final WidgetBuilder builder;

  bool isEnabled(Map<String, bool> modules) {
    if (modules[key] == true) return true;
    for (final alias in aliases) {
      if (modules[alias] == true) return true;
    }
    return false;
  }
}
