import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/app_context/app_context.dart';
import 'package:tore/core/perf/prefetch.dart';
import 'package:tore/features/events/presentation/event_config_providers.dart';
import 'package:tore/features/events/presentation/event_hub_screen.dart';
import 'package:tore/features/events/presentation/create_event_wizard_screen.dart';
import 'package:tore/features/menu_market/presentation/menu_screen.dart';
import 'package:tore/features/navigation/presentation/polymarket_tab_screen.dart';
import 'package:tore/features/navigation/presentation/profile_screen.dart';
import 'package:tore/features/committees/presentation/committees_screens.dart';
import 'package:tore/features/glossary/glossary_screens.dart';
import 'package:tore/features/navigation/presentation/ticker_screen.dart';
import 'package:tore/features/qr/presentation/code_entry_sheet.dart';
import 'package:tore/features/community/presentation/community_screen.dart';
import 'package:tore/features/qr/presentation/qr_scanner_screen.dart';
import 'package:tore/features/ticker/ticker_providers.dart';
import 'package:tore/features/wallet/presentation/wallet_screen.dart';
import 'package:tore/features/map_calendar/presentation/calendar_screen.dart';
import 'package:tore/state.dart';
import 'package:tore/core/auth/auth_models.dart';
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
    final modules = ref.watch(_modulesProvider).maybeWhen(data: (m) => m, orElse: () => const <String, dynamic>{});
    final committeesModule = modules['committee_os'] == true;
    final glossaryModule = modules['folklore_glossary'] == true;
    final me = ref.watch(meProvider).valueOrNull;
    final accountMode = me?.accountMode ?? AccountMode.user;

    final menuOn = config?.menuEnabled ?? false;
    final walletOn = config?.walletEnabled ?? false;
    final polymarketOn = config?.polymarketEnabled ?? false;
    final tickerOn = menuOn || walletOn || polymarketOn;

    if (hasEvent && ctx.activeEventId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        prefetchEventEssentials(
          read: ref.read,
          refresh: ref.refresh,
          eventId: ctx.activeEventId!,
          modulesOn: {'menu': menuOn, 'wallet': walletOn, 'polymarket': polymarketOn},
        );
      });
    }
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
      floatingActionButton: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (accountMode == AccountMode.organizer)
            FloatingActionButton.extended(
              heroTag: 'create-event-fab',
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CreateEventWizardScreen())),
              icon: const Icon(Icons.add),
              label: const Text('Créer event'),
            ),
          const SizedBox(height: 8),
          FloatingActionButton.extended(
            heroTag: 'scan-qr-fab',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen())),
            icon: const Icon(Icons.qr_code_scanner_outlined),
            label: const Text('Scanner QR'),
          ),
        ],
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
          ToreCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Mode actif: ${accountMode.name}', style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                if (accountMode == AccountMode.user) const Text('Découvrir et participer aux events.'),
                if (accountMode == AccountMode.organizer) const Text("Créer et gérer des events depuis l'app."),
                if (accountMode == AccountMode.team) const Text('Scanner QR et gérer les check-ins.'),
              ],
            ),
          ),
          const SizedBox(height: 10),
          if (!hasEvent)
            ToreCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('Scanne un QR join_event ou entre un code pour activer ton event.'),
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: () => showCodeEntrySheet(context),
                    icon: const Icon(Icons.login_outlined),
                    label: const Text('Entrer un code'),
                  ),
                ],
              ),
            ),
          if (!hasEvent)
            _ModuleCard(
              icon: Icons.calendar_month_outlined,
              title: 'Calendrier',
              subtitle: 'Events publics: Live / Today / Upcoming',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CalendarScreen())),
            ),
          if (!hasEvent)
            _ModuleCard(
              icon: Icons.groups_outlined,
              title: 'Communauté',
              subtitle: 'Explorer + Join by code + Mes orgas',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CommunityScreen())),
            ),
          if (hasEvent)
            _ModuleCard(
              icon: Icons.event_note_outlined,
              title: 'Event Hub',
              subtitle: 'Modules actifs de l’event',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventHubScreen(eventId: ctx.activeEventId!, eventName: ctx.activeEventName ?? 'Event #${ctx.activeEventId}'))),
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
          if (committeesModule)
            _ModuleCard(
              icon: Icons.groups_outlined,
              title: 'Comité OS',
              subtitle: 'Page publique + espace privé',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CommitteesListScreen())),
            ),
          if (glossaryModule)
            _ModuleCard(
              icon: Icons.menu_book_outlined,
              title: 'Glossaire Folklore',
              subtitle: 'Comités publics et termes folklore',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const GlossaryHomeScreen())),
            ),
          if (committeesModule)
            _ModuleCard(
              icon: Icons.calendar_month_outlined,
              title: 'Calendrier',
              subtitle: 'Vue publique cross-bars',
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CalendarScreen())),
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

final _modulesProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  return ref.read(apiProvider).modulesState();
});
