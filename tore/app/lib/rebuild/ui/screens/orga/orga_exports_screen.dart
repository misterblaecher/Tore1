import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../config/app_environment.dart';
import '../../../config/link_builder.dart';
import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class OrgaExportsScreen extends StatelessWidget {
  const OrgaExportsScreen({
    super.key,
    required this.eventId,
    required this.environment,
    required this.moduleStates,
    required this.onOpenInApp,
    this.backendPack,
  });

  final String eventId;
  final AppEnvironment environment;
  final Map<String, ModuleState> moduleStates;
  final Future<void> Function(String url) onOpenInApp;
  final Map<String, dynamic>? backendPack;

  @override
  Widget build(BuildContext context) {
    final links = _buildLinks();
    final hasValidLinks = links.values.any(_isValidUrl);
    return ScreenScaffold(
      title: 'QR Pack & Exports',
      scopeBadges: const ['ORGA', 'EXPORTS'],
      body: ListView(
        shrinkWrap: true,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('QR pack',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s8),
                    if (hasValidLinks)
                      ...links.entries.map(
                        (e) => ListTile(
                          title: Text(e.key),
                          subtitle: Text(e.value),
                          trailing: Wrap(
                            spacing: 4,
                            children: [
                              IconButton(
                                  onPressed: () => onOpenInApp(e.value),
                                  icon: const Icon(Icons.open_in_browser),
                                  tooltip: 'Open in app'),
                              IconButton(
                                  onPressed: () => _openUrl(context, e.value),
                                  icon: const Icon(Icons.open_in_new),
                                  tooltip: 'Open externally'),
                            ],
                          ),
                        ),
                      ),
                    if (hasValidLinks)
                      FilledButton(
                          onPressed: () => _copyLinks(context, links),
                          child: const Text('Copy QR links')),
                    if (!hasValidLinks)
                      const BlockedStateView(
                          title: 'Export not available',
                          message: 'Aucun lien export valide reçu du backend.'),
                  ]),
            ),
          ),
          const SizedBox(height: ToreTokens.s8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('End of night exports',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s8),
                    _exportAction(context, 'Entry counts CSV',
                        '/partner/portal/orga/events/$eventId/exports/entry-counts.csv'),
                    _exportAction(context, 'Ledger summary PDF',
                        '/partner/portal/orga/events/$eventId/exports/ledger-summary.pdf'),
                    _exportAction(context, 'Orders summary CSV',
                        '/partner/portal/orga/events/$eventId/exports/orders-summary.csv'),
                  ]),
            ),
          ),
          if (backendPack == null)
            const Padding(
              padding: EdgeInsets.only(top: ToreTokens.s8),
              child: BlockedStateView(
                  title: 'Export not available',
                  message:
                      'Le backend ne fournit pas encore de pack exportable pour cet événement.'),
            ),
        ],
      ),
    );
  }

  Widget _exportAction(BuildContext context, String label, String path) {
    final url = _apiBaseUrl(environment) + path;
    final valid = _isValidUrl(url);
    return ListTile(
      title: Text(label),
      subtitle: Text(url),
      trailing: valid
          ? TextButton(
              onPressed: () => _openUrl(context, url),
              child: const Text('Open'))
          : const Text('Unavailable'),
    );
  }

  Map<String, String> _buildLinks() {
    final fromBackend =
        (backendPack?['links'] as Map?)?.cast<String, dynamic>();
    if (fromBackend != null && fromBackend.isNotEmpty) {
      return fromBackend.map((k, v) => MapEntry(k, v.toString()));
    }
    final links = LinkBuilder(environment);
    final out = <String, String>{
      'Join QR (https)': links.event(eventId),
      'Join QR (tore://)': links.appEvent(eventId),
      if (moduleStates['orga_entry_mode'] != ModuleState.off) ...{
        'Entry Staff QR (https)': links.qr('entry:$eventId'),
        'Entry Staff QR (tore://)': links.appQr('entry:$eventId'),
      },
      if (moduleStates['orga_menu_admin'] != ModuleState.off) ...{
        'Menu QR (https)': links.menu('event', eventId),
        'Menu QR (tore://)': links.appMenu('event', eventId),
      },
      if (moduleStates['bar_dashboard'] != ModuleState.off) ...{
        'Staff Bar QR (https)': links.bar(eventId),
        'Staff Bar QR (tore://)': links.appBar(eventId),
      },
      if (moduleStates['user_wifi'] != ModuleState.off) ...{
        'WiFi QR (https)': links.qr('wifi:$eventId'),
        'WiFi QR (tore://)': links.appQr('wifi:$eventId'),
      },
    };
    return out;
  }

  Future<void> _openUrl(BuildContext context, String value) async {
    if (!_isValidUrl(value)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Lien export invalide ou indisponible.')));
      return;
    }
    final uri = Uri.parse(value);
    final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!launched) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Impossible d’ouvrir ce lien export.')));
    }
  }

  bool _isValidUrl(String value) {
    final uri = Uri.tryParse(value);
    return uri != null &&
        ((uri.scheme == 'http' || uri.scheme == 'https') &&
                uri.host.isNotEmpty ||
            uri.scheme == 'tore');
  }

  void _copyLinks(BuildContext context, Map<String, String> links) {
    final text = links.entries
        .where((e) => _isValidUrl(e.value))
        .map((e) => '${e.key}: ${e.value}')
        .join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('QR links copied.')));
  }

  String _apiBaseUrl(AppEnvironment env) {
    switch (env) {
      case AppEnvironment.dev:
        return 'https://dev-api.tore.app';
      case AppEnvironment.stage:
        return 'https://stage-api.tore.app';
      case AppEnvironment.prod:
        return 'https://api.tore.app';
    }
  }
}
