import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class OrgaEventControlHubScreen extends StatelessWidget {
  const OrgaEventControlHubScreen({super.key, this.network = ConnectivityState.online, this.writeAllowed = true, this.entryApprovedCount = 0, required this.environmentLabel, required this.environmentColor, this.onOpenExports, this.onOpenRunbook});
  final ConnectivityState network;
  final bool writeAllowed;
  final int entryApprovedCount;
  final String environmentLabel;
  final Color environmentColor;
  final VoidCallback? onOpenExports;
  final VoidCallback? onOpenRunbook;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Event Control Hub',
        connectivity: network,
        scopeBadges: ['ORGA', 'CONTROL', environmentLabel],
        body: Column(
          children: [
            Card(
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.all(ToreTokens.s12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Entrées validées', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s4),
                    Text('$entryApprovedCount', style: ToreTypography.monoNumber(context, size: 40)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: ToreTokens.s8),
            ListTile(title: const Text('System status'), subtitle: Text('All green • $environmentLabel'), trailing: ToreBadge(label: environmentLabel, color: environmentColor)),
            SwitchListTile(value: true, onChanged: writeAllowed ? (_) {} : null, title: const Text('Module ENTRY enabled')),
            SwitchListTile(value: true, onChanged: writeAllowed ? (_) {} : null, title: const Text('Module MENU enabled')),
            ListTile(
              title: const Text('Urgency actions'),
              subtitle: Text(writeAllowed ? 'Access enabled' : 'Read-only mode'),
              trailing: const Icon(Icons.warning_amber),
            ),
            ListTile(title: const Text('QR Pack / Exports'), trailing: const Icon(Icons.ios_share), onTap: onOpenExports),
            ListTile(title: const Text('Runbook'), trailing: const Icon(Icons.menu_book), onTap: onOpenRunbook),
          ],
        ),
      );
}

class EntryStaffScreen extends StatelessWidget {
  const EntryStaffScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Entry Staff',
        connectivity: network,
        scopeBadges: const ['ORGA', 'ENTRY'],
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Container(
            height: 120,
            color: ToreTokens.surfaceAlt,
            child: const Center(child: Icon(Icons.qr_code_scanner, size: 52)),
          ),
          const SizedBox(height: ToreTokens.s8),
          Text('Counter: 244', style: ToreTypography.monoNumber(context, size: 24)),
          const SizedBox(height: ToreTokens.s8),
          const _EntryResultChip(status: 'OK', text: 'Entrée validée.'),
          const _EntryResultChip(status: 'DENIED', text: 'Accès refusé: billet déjà utilisé.'),
          const _EntryResultChip(status: 'ERROR', text: 'Lecture impossible: recommencez le scan.'),
          const SizedBox(height: ToreTokens.s8),
          const Text('Derniers 5 scans'),
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: 5,
            itemBuilder: (_, i) => ListTile(title: Text('Scan #${i + 1}'), subtitle: const Text('local cache only')),
          ),
        ]),
      );
}

class OrgaMenuAdminScreen extends StatelessWidget {
  const OrgaMenuAdminScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Menu Admin',
        connectivity: network,
        scopeBadges: const ['ORGA', 'MENU'],
        body: Column(children: [const ListTile(title: Text('Mojito'), subtitle: Text('Quick edit price')), SwitchListTile(value: true, onChanged: (_) {}, title: const Text('Stock enabled'))]),
      );
}

class OrgaPolymarketAdminScreen extends StatelessWidget {
  const OrgaPolymarketAdminScreen({super.key, required this.onSensitive, this.network = ConnectivityState.online});
  final Future<void> Function(String action) onSensitive;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Polymarket Admin',
        connectivity: network,
        scopeBadges: const ['ORGA', 'MARKET'],
        body: Column(children: [
          WriteGuardButton(network: network, onPressed: () => onSensitive('create_market'), label: 'Create'),
          const SizedBox(height: ToreTokens.s8),
          WriteGuardButton(network: network, onPressed: () => onSensitive('resolve_market'), label: 'Resolve'),
          const SizedBox(height: ToreTokens.s8),
          WriteGuardButton(network: network, onPressed: () => onSensitive('dispute_market'), label: 'Dispute'),
        ]),
      );
}

class OrgaUrgencyActionsScreen extends StatelessWidget {
  const OrgaUrgencyActionsScreen({super.key, required this.onSensitive, this.network = ConnectivityState.online});
  final Future<void> Function(String action) onSensitive;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Urgency Actions',
        connectivity: network,
        scopeBadges: const ['ORGA', 'URGENT'],
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          WriteGuardButton(network: network, onPressed: () => onSensitive('pause_event'), label: 'Pause event'),
          const SizedBox(height: ToreTokens.s8),
          WriteGuardButton(network: network, onPressed: () => onSensitive('freeze_event'), label: 'Freeze event', semanticsLabel: 'FREEZE'),
          const SizedBox(height: ToreTokens.s8),
          WriteGuardButton(network: network, onPressed: () => onSensitive('broadcast'), label: 'Broadcast message'),
          const SizedBox(height: ToreTokens.s12),
          Container(
            padding: const EdgeInsets.all(ToreTokens.s8),
            color: ToreTokens.surfaceAlt,
            child: const Text('DEV payload preview (whitelist):\n{"action":"pause_event","reason_code":"manual_override"}', style: ToreTypography.mono),
          ),
        ]),
      );
}

class _EntryResultChip extends StatelessWidget {
  const _EntryResultChip({required this.status, required this.text});
  final String status;
  final String text;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'OK' => Colors.green,
      'DENIED' => Colors.orange,
      _ => Colors.red,
    };
    return Container(
      padding: const EdgeInsets.all(ToreTokens.s12),
      margin: const EdgeInsets.only(bottom: ToreTokens.s8),
      color: color.withOpacity(.18),
      child: Row(children: [ToreBadge(label: status, color: color), const SizedBox(width: ToreTokens.s8), Expanded(child: Text(text))]),
    );
  }
}
