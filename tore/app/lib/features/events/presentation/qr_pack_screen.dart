import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../shared/models/qr_pack.dart';
import 'events_providers.dart';

class QrPackScreen extends ConsumerWidget {
  const QrPackScreen({super.key, required this.eventId, this.eventName});

  final int eventId;
  final String? eventName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final packAsync = ref.watch(qrPackProvider(eventId));
    return Scaffold(
      appBar: AppBar(
        title: Text(eventName == null ? 'QR Pack' : 'QR Pack • $eventName'),
      ),
      body: packAsync.when(
        data: (pack) => _QrPackBody(pack: pack),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const Center(child: Text('Impossible de charger le QR pack.')),
      ),
    );
  }
}

class _QrPackBody extends StatelessWidget {
  const _QrPackBody({required this.pack});

  final QrPack pack;

  @override
  Widget build(BuildContext context) {
    final items = [
      _QrItem(label: 'Join QR', value: pack.qrs['join'] ?? ''),
      _QrItem(label: 'Menu QR', value: pack.qrs['menu'] ?? ''),
      _QrItem(label: 'Entry QR', value: pack.qrs['entry'] ?? ''),
      _QrItem(label: 'Admin Config QR', value: pack.qrs['admin_config'] ?? ''),
      _QrItem(label: 'Staff Entry QR', value: pack.qrs['staff_entry'] ?? ''),
    ];

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: items.length,
      separatorBuilder: (_, __) => const SizedBox(height: 16),
      itemBuilder: (context, index) {
        final item = items[index];
        return _QrCard(item: item);
      },
    );
  }
}

class _QrItem {
  final String label;
  final String value;

  const _QrItem({required this.label, required this.value});
}

class _QrCard extends StatelessWidget {
  const _QrCard({required this.item});

  final _QrItem item;

  @override
  Widget build(BuildContext context) {
    final canRender = item.value.isNotEmpty;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(item.label, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Center(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: canRender
                    ? QrImageView(
                        data: item.value,
                        size: 180,
                        backgroundColor: Colors.white,
                      )
                    : const Text('QR indisponible'),
              ),
            ),
            const SizedBox(height: 12),
            SelectableText(
              item.value.isEmpty ? 'Lien manquant' : item.value,
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                TextButton.icon(
                  onPressed: canRender
                      ? () async {
                          await Clipboard.setData(ClipboardData(text: item.value));
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('${item.label} copié.')),
                          );
                        }
                      : null,
                  icon: const Icon(Icons.copy_outlined),
                  label: const Text('Copier'),
                ),
                TextButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Partage: bientôt.')),
                    );
                  },
                  icon: const Icon(Icons.share_outlined),
                  label: const Text('Partager'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
