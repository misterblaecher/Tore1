import 'package:flutter/material.dart';

import '../../../models/event_context.dart';
import '../../../models/qr_resolve.dart';
import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BootSplashScreen extends StatelessWidget {
  const BootSplashScreen({super.key, required this.network, this.onLongPressDiagnostics});
  final ConnectivityState network;
  final VoidCallback? onLongPressDiagnostics;
  @override
  Widget build(BuildContext context) => GestureDetector(
        onLongPress: onLongPressDiagnostics,
        child: ScreenScaffold(
          title: 'Boot',
          connectivity: network,
          scopeBadges: const ['USER'],
          body: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [LoadingSkeleton(lines: 3), SizedBox(height: ToreTokens.s12), Text('TORÈ v3 rebuild boot…'), Text('Long-press logo for diagnostics'), Text('Offline mode supported')]),
        ),
      );
}

class ConsentCharterScreen extends StatelessWidget {
  const ConsentCharterScreen({super.key, required this.onAccept});
  final VoidCallback onAccept;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Consent Charter',
        scopeBadges: const ['USER'],
        body: Column(children: [const Text('Night charter consent required.'), const SizedBox(height: ToreTokens.s12), FilledButton(onPressed: onAccept, child: const Text('Accept & continue'))]),
      );
}

class HomeHubScreen extends StatelessWidget {
  const HomeHubScreen({super.key, required this.network, required this.cards});
  final ConnectivityState network;
  final List<Widget> cards;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Home Hub',
        connectivity: network,
        scopeBadges: const ['USER', 'LIVE'],
        body: cards.isEmpty
            ? const EmptyStateView(message: 'Aucun module actif pour le moment.')
            : ListView.separated(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: cards.length, separatorBuilder: (_, __) => const SizedBox(height: ToreTokens.s8), itemBuilder: (_, i) => cards[i]),
      );
}

class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen({super.key, required this.onResolve, this.network = ConnectivityState.online});
  final Future<void> Function(String payload) onResolve;
  final ConnectivityState network;

  @override
  Widget build(BuildContext context) {
    final ctrl = TextEditingController();

    Future<void> handleResolve() async {
      final payload = ctrl.text.trim();
      if (payload.isEmpty) {
        ToreFeedback.warning(context, 'Saisissez un code pour continuer.');
        return;
      }
      ToreFeedback.success(context, 'QR reçu, résolution en cours...');
      await onResolve(payload);
      if (!context.mounted) return;
      final normalized = normalizeUiCode(payload.split(':').first);
      final copy = resolveUiCopy(normalized);
      if (uiCopyMapping.containsKey(normalized)) {
        ToreFeedback.error(context, '${copy.title} — ${copy.message}');
      } else {
        ToreFeedback.success(context, 'QR accepté. Action lancée.');
      }
    }

    return ScreenScaffold(
      title: 'QR Scanner',
      connectivity: network,
      scopeBadges: const ['USER', 'SCAN'],
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        AnimatedScale(
          scale: 1,
          duration: ToreMotion.micro(context),
          child: Container(
            height: 220,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: ToreTokens.ruby, width: 2),
              color: ToreTokens.surfaceAlt,
            ),
            child: const Center(child: Icon(Icons.qr_code_scanner, size: 64, color: ToreTokens.ruby)),
          ),
        ),
        const SizedBox(height: ToreTokens.s8),
        const Text('Cadrez le QR dans la zone rubis. Le scan se lance automatiquement.'),
        const SizedBox(height: ToreTokens.s12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text('Saisie manuelle', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: ToreTokens.s8),
              Semantics(
                textField: true,
                label: 'QR manual input',
                child: TextField(controller: ctrl, decoration: const InputDecoration(labelText: 'Code ou payload QR')),
              ),
              const SizedBox(height: ToreTokens.s12),
              Row(children: [
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Torche (stub)'))),
                const SizedBox(width: ToreTokens.s8),
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Aide'))),
              ]),
              const SizedBox(height: ToreTokens.s8),
              FilledButton(onPressed: handleResolve, child: const Text('Résoudre le code')),
            ]),
          ),
        ),
      ]),
    );
  }
}

class BarsScreen extends StatelessWidget {
  const BarsScreen({super.key, required this.network, required this.children});
  final ConnectivityState network;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Bars',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: children.length, itemBuilder: (_, i) => children[i]));
}

class BarEventsScreen extends StatelessWidget {
  const BarEventsScreen({super.key, required this.children, this.network = ConnectivityState.online});
  final List<Widget> children;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Events',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [Wrap(spacing: ToreTokens.s8, children: const [Chip(label: Text('Live')), Chip(label: Text('Today')), Chip(label: Text('Upcoming'))]), const SizedBox(height: ToreTokens.s8), ...children]),
      );
}

class JoinEventScreen extends StatelessWidget {
  const JoinEventScreen({super.key, required this.writeAllowed, required this.onJoin, this.network = ConnectivityState.online});
  final bool writeAllowed;
  final VoidCallback onJoin;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Join Event',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          const TextField(decoration: InputDecoration(labelText: 'Optional code')),
          const SizedBox(height: ToreTokens.s8),
          if (!writeAllowed) const BlockedStateView(title: 'Entrée temporairement bloquée', message: 'L’action est indisponible: module gelé, lecture seule ou réseau hors ligne.'),
          const SizedBox(height: ToreTokens.s8),
          Semantics(
            button: true,
            label: 'JOIN',
            child: FilledButton(
              style: FilledButton.styleFrom(backgroundColor: ToreTokens.yellowCta, foregroundColor: Colors.black),
              onPressed: writeAllowed ? onJoin : null,
              child: const Text('Join'),
            ),
          ),
        ]),
      );
}

class EventHubScreen extends StatelessWidget {
  const EventHubScreen({
    super.key,
    required this.network,
    required this.modules,
    this.eventState = EventState.running,
    this.writeAllowedReason = 'Actions disponibles',
  });
  final ConnectivityState network;
  final List<Widget> modules;
  final EventState eventState;
  final String writeAllowedReason;

  @override
  Widget build(BuildContext context) {
    final labels = {
      EventState.running: 'LIVE',
      EventState.paused: 'PAUSED',
      EventState.readOnly: 'MENU_ONLY',
      EventState.ended: 'CLOSED',
      EventState.draft: 'DRAFT',
    };
    final stateLabel = labels[eventState] ?? 'LIVE';
    final ctaEnabled = network != ConnectivityState.offline && eventState == EventState.running;
    return ScreenScaffold(
      title: 'Event Hub',
      connectivity: network,
      scopeBadges: const ['USER', 'HUB'],
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Card(
          child: ListTile(
            title: Text('État événement: $stateLabel'),
            subtitle: Text(writeAllowedReason),
            trailing: ToreBadge(label: stateLabel, color: eventState == EventState.paused ? Colors.orange : ToreTokens.ruby),
          ),
        ),
        const SizedBox(height: ToreTokens.s8),
        if (modules.isEmpty)
          const EmptyStateView(message: 'Aucun module actif. Les modules OFF restent invisibles.')
        else
          ...modules,
        const SizedBox(height: ToreTokens.s8),
        FilledButton(onPressed: ctaEnabled ? () {} : null, child: const Text('Action principale')),
      ]),
    );
  }
}

class MenuScreen extends StatelessWidget {
  const MenuScreen({super.key, required this.network, required this.items});
  final ConnectivityState network;
  final List<Widget> items;
  @override
  Widget build(BuildContext context) {
    final offline = network == ConnectivityState.offline;
    return ScreenScaffold(
      title: 'Menu',
      connectivity: network,
      scopeBadges: const ['USER', 'CACHE-FIRST'],
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(onPressed: () {}, icon: const Icon(Icons.refresh), label: const Text('Pull to refresh'))),
        const SizedBox(height: ToreTokens.s8),
        if (items.isEmpty)
          const EmptyStateView(message: 'Le menu sera publié prochainement.')
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: ToreTokens.s8),
            itemBuilder: (_, i) => items[i],
          ),
        if (offline) const Padding(padding: EdgeInsets.only(top: ToreTokens.s8), child: Text('Affichage cache local.')),
      ]),
      footer: Container(
        padding: const EdgeInsets.all(ToreTokens.s12),
        color: ToreTokens.surfaceAlt,
        child: Row(
          children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                const Text('Cart total'),
                Text('42.00 €', style: ToreTypography.monoNumber(context, size: 18)),
              ]),
            ),
            Semantics(
              button: true,
              label: 'CONFIRMER',
              child: FilledButton(
                style: FilledButton.styleFrom(backgroundColor: ToreTokens.yellowCta, foregroundColor: Colors.black),
                onPressed: offline ? null : () {},
                child: const Text('Confirmer'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class WalletScreen extends StatelessWidget {
  const WalletScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Wallet',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('€ 129.20', style: ToreTypography.monoNumber(context, size: 36)),
          const SizedBox(height: ToreTokens.s12),
          if (rows.isEmpty) const EmptyStateView(message: 'Aucun mouvement pour le moment.'),
          ...rows,
        ]),
      );
}

class TickerScreen extends StatelessWidget {
  const TickerScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Ticker',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          Row(children: [OutlinedButton(onPressed: () {}, child: const Text('Filters')), const SizedBox(width: ToreTokens.s8), OutlinedButton(onPressed: () {}, child: const Text('Pause'))]),
          const SizedBox(height: ToreTokens.s8),
          ListView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: rows.length, itemBuilder: (_, i) => rows[i]),
        ]),
      );
}

class PolymarketGlobalScreen extends StatelessWidget {
  const PolymarketGlobalScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Polymarket Global',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: rows.length, itemBuilder: (_, i) => rows[i]));
}

class PolymarketEventScreen extends StatelessWidget {
  const PolymarketEventScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Polymarket Event',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), itemCount: rows.length, itemBuilder: (_, i) => rows[i]));
}

class ProfileSettingsScreen extends StatefulWidget {
  const ProfileSettingsScreen({super.key, this.network = ConnectivityState.online, this.onOpenDiagnostics, this.onOpenHelp});
  final ConnectivityState network;
  final VoidCallback? onOpenDiagnostics;
  final VoidCallback? onOpenHelp;

  @override
  State<ProfileSettingsScreen> createState() => _ProfileSettingsScreenState();
}

class _ProfileSettingsScreenState extends State<ProfileSettingsScreen> {
  bool reduceMotion = false;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Profile Settings',
        connectivity: widget.network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          GestureDetector(
            onLongPress: widget.onOpenDiagnostics,
            child: const ListTile(title: Text('Profile header (long press for diagnostics)'), subtitle: Text('Privacy level')),
          ),
          SwitchListTile(value: true, onChanged: (_) {}, title: const Text('Night theme')),
          ValueListenableBuilder<bool>(
            valueListenable: TorePreferences.highContrast,
            builder: (context, value, _) => SwitchListTile(
              value: value,
              onChanged: (next) => TorePreferences.highContrast.value = next,
              title: const Text('High contrast'),
              subtitle: Text(value ? 'Texte renforcé + contours accentués' : 'Palette standard nuit'),
            ),
          ),
          SwitchListTile(value: reduceMotion, onChanged: (v) => setState(() => reduceMotion = v), title: const Text('Reduce motion')),
          SwitchListTile(value: true, onChanged: (_) {}, title: const Text('Mask balance on lock screen')),
          ListTile(title: const Text('Help / Runbook'), trailing: const Icon(Icons.help_outline), onTap: widget.onOpenHelp),
        ]),
      );
}
