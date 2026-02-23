import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class OrgaExportsScreen extends StatelessWidget {
  const OrgaExportsScreen({
    super.key,
    required this.eventId,
    required this.moduleStates,
    this.backendPack,
  });

  final String eventId;
  final Map<String, ModuleState> moduleStates;
  final Map<String, dynamic>? backendPack;

  @override
  Widget build(BuildContext context) {
    final links = _buildLinks();
    return ScreenScaffold(
      title: 'QR Pack & Exports',
      scopeBadges: const ['ORGA', 'EXPORTS'],
      body: ListView(
        shrinkWrap: true,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('QR pack', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: ToreTokens.s8),
                ...links.entries.map((e) => ListTile(title: Text(e.key), subtitle: Text(e.value), trailing: IconButton(onPressed: () => _openUrl(context, e.value), icon: const Icon(Icons.open_in_new)))),
                FilledButton(onPressed: () => _copyLinks(context, links), child: const Text('Copy QR links')),
              ]),
            ),
          ),
          const SizedBox(height: ToreTokens.s8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('End of night exports', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: ToreTokens.s8),
                _exportAction(context, 'Entry counts CSV', '/partner/portal/orga/events/$eventId/exports/entry-counts.csv'),
                _exportAction(context, 'Ledger summary PDF', '/partner/portal/orga/events/$eventId/exports/ledger-summary.pdf'),
                _exportAction(context, 'Orders summary CSV', '/partner/portal/orga/events/$eventId/exports/orders-summary.csv'),
              ]),
            ),
          ),
          if (backendPack == null)
            const Padding(
              padding: EdgeInsets.only(top: ToreTokens.s8),
              child: BlockedStateView(title: 'Export not available', message: 'Le backend ne fournit pas encore de pack exportable pour cet événement.'),
            ),
        ],
      ),
    );
  }

  Widget _exportAction(BuildContext context, String label, String path) {
    final url = 'https://api.tore.app$path';
    return ListTile(
      title: Text(label),
      subtitle: Text(url),
      trailing: TextButton(onPressed: () => _openUrl(context, url), child: const Text('Open')),
    );
  }

  Map<String, String> _buildLinks() {
    final fromBackend = (backendPack?['links'] as Map?)?.cast<String, dynamic>();
    if (fromBackend != null && fromBackend.isNotEmpty) {
      return fromBackend.map((k, v) => MapEntry(k, v.toString()));
    }
    final base = 'https://tore.app/e/$eventId';
    final out = <String, String>{
      'Join QR': '$base/join',
      if (moduleStates['orga_entry_mode'] != ModuleState.off) 'Entry Staff QR': '$base/entry-staff',
      if (moduleStates['orga_menu_admin'] != ModuleState.off) 'Menu QR': '$base/menu',
      if (moduleStates['bar_dashboard'] != ModuleState.off) 'Staff Bar QR': '$base/bar-staff',
      if (moduleStates['user_wifi'] != ModuleState.off) 'WiFi QR': '$base/wifi',
    };
    return out;
  }

  Future<void> _openUrl(BuildContext context, String value) async {
    final uri = Uri.parse(value);
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  void _copyLinks(BuildContext context, Map<String, String> links) {
    final text = links.entries.map((e) => '${e.key}: ${e.value}').join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('QR links copied.')));
  }
}
