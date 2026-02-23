import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BarDashboardScreen extends StatelessWidget {
  const BarDashboardScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Bar Dashboard',
        connectivity: network,
        scopeBadges: const ['BAR'],
        body: Column(children: [
          ListTile(title: const Text('Revenue today'), trailing: Text('€ 2,430', style: ToreTypography.monoNumber(context))),
          const ListTile(title: Text('Orders live'), trailing: Text('18'))
        ]),
      );
}

class FullMenuAdminScreen extends StatelessWidget {
  const FullMenuAdminScreen({super.key, this.network = ConnectivityState.online});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Full Menu Admin',
        connectivity: network,
        scopeBadges: const ['BAR'],
        body: const Column(children: [ListTile(title: Text('Product editing shell')), ListTile(title: Text('Price + tags + stock'))]),
      );
}

class ZonesQrAdminScreen extends StatelessWidget {
  const ZonesQrAdminScreen({super.key, this.network = ConnectivityState.online, this.zones = const ['Zone A', 'Zone B']});
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
                itemBuilder: (_, i) => SwitchListTile(value: true, onChanged: (_) {}, title: Text('${zones[i]} enabled')),
              ),
        footer: FilledButton.icon(onPressed: zones.isEmpty ? null : () {}, icon: const Icon(Icons.download), label: const Text('Export zones (stub)')),
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
        body: Column(children: [const Text('Charts placeholder (no extra deps)'), Container(height: 120, color: ToreTokens.surfaceAlt), const SizedBox(height: ToreTokens.s8), Container(height: 120, color: ToreTokens.surfaceAlt)]),
      );
}
