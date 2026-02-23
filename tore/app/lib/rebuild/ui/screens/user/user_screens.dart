import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../models/event_context.dart';
import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BootSplashScreen extends StatelessWidget {
  const BootSplashScreen({super.key, required this.network});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Boot',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [LoadingSkeleton(lines: 3), Text('TORÈ v3 rebuild boot…'), Text('Offline mode supported')]),
      );
}

class ConsentCharterScreen extends StatelessWidget {
  const ConsentCharterScreen({super.key, required this.onAccept});
  final VoidCallback onAccept;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Consent Charter',
        scopeBadges: const ['USER'],
        body: Column(children: [const Text('Night charter consent required.'), const SizedBox(height: 12), FilledButton(onPressed: onAccept, child: const Text('Accept & continue'))]),
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
        body: cards.isEmpty ? const EmptyStateView(message: 'Aucun module actif pour le moment.') : Column(children: cards),
      );
}

class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen({super.key, required this.onResolve, this.network = ConnectivityState.online});
  final Future<void> Function(String payload) onResolve;
  final ConnectivityState network;

  String _copyForCode(String code) {
    switch (code) {
      case 'qr_unknown':
        return 'QR inconnu. Vérifiez que vous scannez un code TORÈ valide.';
      case 'expired':
        return 'Ce QR est expiré. Demandez un nouveau QR depuis votre écran événement.';
      case 'replay':
        return 'Ce QR a déjà été utilisé. Utilisez un QR encore non consommé.';
      case 'module_off':
        return 'Ce module est désactivé pour cet événement. Rendez-vous sur le hub.';
      case 'event_paused':
        return 'Événement en pause. Les actions reprendront automatiquement.';
      case 'backend_down':
        return 'Service momentanément indisponible. Réessayez dans quelques instants.';
      default:
        return 'Scan impossible. Essayez la saisie manuelle ci-dessous.';
    }
  }

  @override
  Widget build(BuildContext context) {
    final ctrl = TextEditingController();
    void handleResolve() async {
      if (ctrl.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saisissez un code pour continuer.')));
        return;
      }
      HapticFeedback.lightImpact();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('QR reçu, résolution en cours...')));
      await onResolve(ctrl.text.trim());
      if (!context.mounted) return;
      final lowered = ctrl.text.toLowerCase();
      for (final key in const ['qr_unknown', 'expired', 'replay', 'module_off', 'event_paused', 'backend_down']) {
        if (lowered.contains(key)) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(_copyForCode(key))));
          return;
        }
      }
    }

    return ScreenScaffold(
      title: 'QR Scanner',
      connectivity: network,
      scopeBadges: const ['USER', 'SCAN'],
      body: Column(children: [
        Container(
          height: 220,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ToreTokens.ruby, width: 2),
            color: ToreTokens.surfaceAlt,
          ),
          child: const Center(child: Icon(Icons.qr_code_scanner, size: 64, color: ToreTokens.ruby)),
        ),
        const SizedBox(height: 8),
        const Text('Cadrez le QR dans la zone rubis. Le scan se lance automatiquement.'),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Text('Saisie manuelle', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              TextField(controller: ctrl, decoration: const InputDecoration(labelText: 'Code ou payload QR')),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Torche (stub)'))),
                const SizedBox(width: 8),
                Expanded(child: OutlinedButton(onPressed: () {}, child: const Text('Aide'))),
              ]),
              const SizedBox(height: 8),
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
  Widget build(BuildContext context) => ScreenScaffold(title: 'Bars', connectivity: network, scopeBadges: const ['USER'], body: Column(children: children));
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
        body: Column(children: [Wrap(spacing: 8, children: const [Chip(label: Text('Live')), Chip(label: Text('Today')), Chip(label: Text('Upcoming'))]), const SizedBox(height: 8), ...children]),
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
          const SizedBox(height: 8),
          if (!writeAllowed) const BlockedStateView(title: 'Entrée temporairement bloquée', message: 'L’action est indisponible: module gelé, lecture seule ou réseau hors ligne.'),
          const SizedBox(height: 8),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: ToreTokens.yellowCta, foregroundColor: Colors.black),
            onPressed: writeAllowed ? onJoin : null,
            child: const Text('Join'),
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
        const SizedBox(height: 8),
        if (modules.isEmpty)
          const EmptyStateView(message: 'Aucun module actif. Les modules OFF restent invisibles.')
        else
          ...modules,
        const SizedBox(height: 8),
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
      body: Column(children: [
        Align(alignment: Alignment.centerRight, child: OutlinedButton.icon(onPressed: () {}, icon: const Icon(Icons.refresh), label: const Text('Pull to refresh'))),
        if (items.isEmpty)
          const EmptyStateView(message: 'Le menu sera publié prochainement.')
        else
          ...items,
        if (offline) const Padding(padding: EdgeInsets.only(top: 8), child: Text('Affichage cache local.')), 
      ]),
      footer: Container(
        padding: const EdgeInsets.all(12),
        color: ToreTokens.surfaceAlt,
        child: Row(
          children: [
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text('Cart total'),
                Text('42.00 €', style: TextStyle(fontFamily: 'monospace', fontSize: 18, fontWeight: FontWeight.bold)),
              ]),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: ToreTokens.yellowCta, foregroundColor: Colors.black),
              onPressed: offline ? null : () {},
              child: const Text('Confirmer'),
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
          const Text('€ 129.20', style: TextStyle(fontFamily: 'monospace', fontSize: 36, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
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
        body: Column(children: [Row(children: [OutlinedButton(onPressed: () {}, child: const Text('Filters')), const SizedBox(width: 8), OutlinedButton(onPressed: () {}, child: const Text('Pause'))]), const SizedBox(height: 8), ...rows]),
      );
}

class PolymarketGlobalScreen extends StatelessWidget {
  const PolymarketGlobalScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(title: 'Polymarket Global', connectivity: network, scopeBadges: const ['USER'], body: Column(children: rows));
}

class PolymarketEventScreen extends StatelessWidget {
  const PolymarketEventScreen({super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(title: 'Polymarket Event', connectivity: network, scopeBadges: const ['USER'], body: Column(children: rows));
}

class ProfileSettingsScreen extends StatelessWidget {
  const ProfileSettingsScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Profile Settings',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          const ListTile(title: Text('Privacy level'), subtitle: Text('Public / Friends / Private')),
          SwitchListTile(value: true, onChanged: (_) {}, title: const Text('Night theme')),
          SwitchListTile(value: false, onChanged: (_) {}, title: const Text('High contrast')),
          SwitchListTile(value: false, onChanged: (_) {}, title: const Text('Reduce motion')),
          SwitchListTile(value: true, onChanged: (_) {}, title: const Text('Mask balance on lock screen')),
        ]),
      );
}
