import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BarDashboardScreen extends StatelessWidget {
  const BarDashboardScreen(
      {super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Bar Dashboard',
        connectivity: network,
        scopeBadges: const ['BAR'],
        body: Column(children: [
          ListTile(
              title: const Text('Revenue today'),
              trailing:
                  Text('€ 2,430', style: ToreTypography.monoNumber(context))),
          const ListTile(title: Text('Orders live'), trailing: Text('18'))
        ]),
      );
}

class FullMenuAdminScreen extends StatelessWidget {
  const FullMenuAdminScreen(
      {super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Full Menu Admin',
        connectivity: network,
        scopeBadges: const ['BAR'],
        body: const Column(children: [
          ListTile(title: Text('Product editing shell')),
          ListTile(title: Text('Price + tags + stock'))
        ]),
      );
}

class ZonesQrAdminScreen extends StatelessWidget {
  const ZonesQrAdminScreen(
      {super.key,
      this.network = ConnectivityState.online,
      this.zones = const ['Zone A', 'Zone B']});
  final ConnectivityState network;
  final List<String> zones;

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Zones QR Admin',
        connectivity: network,
        scopeBadges: const ['BAR', 'GUARDED'],
        body: zones.isEmpty
            ? const EmptyStateView(message: 'Aucune zone QR configurée.')
            : ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: zones.length,
                itemBuilder: (_, i) => SwitchListTile(
                    value: true,
                    onChanged: (_) {},
                    title: Text('${zones[i]} enabled')),
              ),
        footer: FilledButton.icon(
            onPressed: zones.isEmpty ? null : () {},
            icon: const Icon(Icons.download),
            label: const Text('Exporter zones')),
      );
}

class AnalyticsScreen extends StatelessWidget {
  const AnalyticsScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Analytics',
        connectivity: network,
        scopeBadges: const ['BAR'],
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('Ventes par heure'),
          const SizedBox(height: ToreTokens.s8),
          _BarChartRow(label: '20h', value: .45, amount: '€ 420'),
          _BarChartRow(label: '21h', value: .72, amount: '€ 690'),
          _BarChartRow(label: '22h', value: .95, amount: '€ 910'),
          _BarChartRow(label: '23h', value: .64, amount: '€ 610'),
          const SizedBox(height: ToreTokens.s16),
          const Text('Top produits'),
          const ListTile(title: Text('Pils 25cl'), trailing: Text('148')),
          const ListTile(title: Text('Mojito'), trailing: Text('87')),
          const ListTile(title: Text('Soft'), trailing: Text('63')),
        ]),
      );
}

class _BarChartRow extends StatelessWidget {
  const _BarChartRow(
      {required this.label, required this.value, required this.amount});

  final String label;
  final double value;
  final String amount;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: ToreTokens.s8),
      child: Row(children: [
        SizedBox(width: 42, child: Text(label)),
        Expanded(
          child: LinearProgressIndicator(
            minHeight: 12,
            value: value,
            borderRadius: BorderRadius.circular(6),
          ),
        ),
        const SizedBox(width: ToreTokens.s8),
        Text(amount, style: ToreTypography.mono),
      ]),
    );
  }
}
