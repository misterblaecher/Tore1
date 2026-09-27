import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/widgets/offline_fallback_screen.dart';
import '../../operations/domain/operational_models.dart';
import '../data/event_cost_service.dart';
import 'report_providers.dart';

class ReportScreen extends ConsumerStatefulWidget {
  const ReportScreen({super.key, required this.capability});

  final ScopedCapability capability;
  int get eventId => capability.eventId!;

  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  bool _savingCost = false;

  String _formatCents(int cents) {
    return '${(cents / 100).toStringAsFixed(2)} €';
  }

  int? _eurosToCents(String s) {
    final v = double.tryParse(s.replaceAll(',', '.'));
    if (v == null) return null;
    return (v * 100).round();
  }

  Future<void> _addCost(EventCostService service) async {
    if (_savingCost) return;
    if (ref.read(networkStatusProvider) != NetworkState.online) return;
    final draft = await _showCostDialog();
    if (draft == null) return;
    if (ref.read(networkStatusProvider) != NetworkState.online) return;

    setState(() => _savingCost = true);
    try {
      await service.createCost(
        eventId: widget.eventId,
        label: draft.label,
        amountCents: draft.amountCents,
        category: draft.category,
      );
      ref.invalidate(eventReportProvider(widget.eventId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Coût ajouté ✅')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _savingCost = false);
    }
  }

  Future<_CostDraft?> _showCostDialog() async {
    final labelCtrl = TextEditingController();
    final amountCtrl = TextEditingController();
    var category = 'stock';

    final draft = await showDialog<_CostDraft>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Ajouter un coût'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: labelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Label',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: amountCtrl,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(
                      labelText: 'Montant (€)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: category,
                    decoration: const InputDecoration(
                      labelText: 'Catégorie',
                      border: OutlineInputBorder(),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'stock', child: Text('Stock')),
                      DropdownMenuItem(
                          value: 'location', child: Text('Location')),
                      DropdownMenuItem(value: 'staff', child: Text('Staff')),
                      DropdownMenuItem(value: 'other', child: Text('Autre')),
                    ],
                    onChanged: (value) {
                      if (value == null) return;
                      setDialogState(() => category = value);
                    },
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: const Text('Annuler'),
                ),
                ElevatedButton(
                  onPressed: () {
                    final label = labelCtrl.text.trim();
                    final cents = _eurosToCents(amountCtrl.text.trim());
                    if (label.isEmpty || cents == null || cents <= 0) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                            content: Text('Montant ou label invalide')),
                      );
                      return;
                    }
                    Navigator.of(dialogContext).pop(
                      _CostDraft(
                          label: label, amountCents: cents, category: category),
                    );
                  },
                  child: const Text('Ajouter'),
                ),
              ],
            );
          },
        );
      },
    );

    labelCtrl.dispose();
    amountCtrl.dispose();
    return draft;
  }

  Future<void> _confirmDeleteCost(int costId, EventCostService service) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text('Supprimer ce coût ?'),
          content: const Text('Cette action est irréversible.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Annuler'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Supprimer'),
            ),
          ],
        );
      },
    );
    if (confirmed != true) return;
    if (ref.read(networkStatusProvider) != NetworkState.online) return;

    try {
      await service.deleteCost(eventId: widget.eventId, costId: costId);
      ref.invalidate(eventReportProvider(widget.eventId));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Coût supprimé ✅')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e')),
        );
      }
    }
  }

  Future<void> _copyToClipboard(String text, String label) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$label copié ✅')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!OperationalGuard.canViewReport(widget.capability, widget.eventId)) {
      return const Scaffold(body: Center(child: Text('Accès refusé au bilan')));
    }
    final reportAsync = ref.watch(eventReportProvider(widget.eventId));
    final costService = ref.watch(eventCostServiceProvider);
    final online = ref.watch(networkStatusProvider) == NetworkState.online;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Bilan soirée'),
      ),
      body: reportAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) {
          if (err is OfflineNoCacheException) {
            return OfflineFallbackScreen(
              title: 'Rapport indisponible hors ligne',
              message: 'Aucun rapport en cache pour cet event.',
              onRetry: () =>
                  ref.invalidate(eventReportProvider(widget.eventId)),
            );
          }
          return Center(
              child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Bilan indisponible'),
              TextButton(
                onPressed: () =>
                    ref.invalidate(eventReportProvider(widget.eventId)),
                child: const Text('Réessayer'),
              ),
            ],
          ));
        },
        data: (result) {
          final report = result.report;
          final isOffline = result.fromCache;
          final generatedAt = report.generatedAt != null
              ? DateTime.tryParse(report.generatedAt!)
              : null;
          final formattedGeneratedAt = generatedAt != null
              ? '${generatedAt.day.toString().padLeft(2, '0')}/'
                  '${generatedAt.month.toString().padLeft(2, '0')} '
                  '${generatedAt.hour.toString().padLeft(2, '0')}:'
                  '${generatedAt.minute.toString().padLeft(2, '0')}'
              : 'N/A';

          final items = [...report.sales.byItem]
            ..sort((a, b) => b.revenueCents.compareTo(a.revenueCents));
          final topItems = items.take(10).toList();

          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(eventReportProvider(widget.eventId));
              await ref.read(eventReportProvider(widget.eventId).future);
            },
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (isOffline)
                  Card(
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: ListTile(
                      leading: const Icon(Icons.cloud_off_outlined),
                      title: const Text('Mode hors ligne (lecture seule)'),
                      subtitle: Text('Dernière MAJ : $formattedGeneratedAt'),
                    ),
                  ),
                if (isOffline) const SizedBox(height: 12),
                _SectionTitle(title: 'Résumé'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        _MetricRow(
                          label: 'Commandes',
                          value: report.sales.totalOrders.toString(),
                        ),
                        const SizedBox(height: 8),
                        _MetricRow(
                          label: 'Recettes estimées',
                          value: _formatCents(report.sales.grossRevenueCents),
                        ),
                        const SizedBox(height: 8),
                        _MetricRow(
                          label: 'Coûts',
                          value: _formatCents(report.costs.totalCostCents),
                        ),
                        const SizedBox(height: 8),
                        _MetricRow(
                          label: 'Résultat estimé',
                          value: _formatCents(report.profit.grossProfitCents),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                _SectionTitle(title: 'Ventes par item (Top 10)'),
                if (topItems.isEmpty) const Text('Aucune vente enregistrée.'),
                if (topItems.isNotEmpty)
                  Card(
                    child: Column(
                      children: topItems
                          .map(
                            (item) => ListTile(
                              title: Text(item.name),
                              subtitle: Text('Qté: ${item.qty}'),
                              trailing: Text(_formatCents(item.revenueCents)),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                const SizedBox(height: 16),
                _SectionTitle(title: 'Ventes par catégorie'),
                if (report.sales.byCategory.isEmpty)
                  const Text('Aucune catégorie de vente.'),
                if (report.sales.byCategory.isNotEmpty)
                  Card(
                    child: Column(
                      children: report.sales.byCategory
                          .map(
                            (category) => ListTile(
                              title: Text(category.category),
                              subtitle: Text('Qté: ${category.qty}'),
                              trailing:
                                  Text(_formatCents(category.revenueCents)),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                const SizedBox(height: 16),
                _SectionTitle(title: 'Coûts'),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Total: ${_formatCents(report.costs.totalCostCents)}',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                    ),
                    ElevatedButton.icon(
                      onPressed: !online || isOffline || _savingCost
                          ? null
                          : () => _addCost(costService),
                      icon: _savingCost
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.add),
                      label: Text(_savingCost ? 'Ajout...' : 'Ajouter'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (report.costs.lines.isEmpty) const Text('Aucun coût saisi.'),
                if (report.costs.lines.isNotEmpty)
                  Card(
                    child: Column(
                      children: report.costs.lines
                          .map(
                            (cost) => ListTile(
                              title: Text(cost.label.isEmpty
                                  ? cost.category
                                  : cost.label),
                              subtitle: Text('Catégorie: ${cost.category}'),
                              trailing: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(_formatCents(cost.amountCents)),
                                  if (online && !isOffline)
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline),
                                      onPressed: () => _confirmDeleteCost(
                                          cost.id, costService),
                                    ),
                                ],
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                const SizedBox(height: 16),
                _SectionTitle(title: 'Exporter'),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    OutlinedButton.icon(
                      icon: const Icon(Icons.copy_outlined),
                      label: const Text('Copier JSON'),
                      onPressed: () => _copyToClipboard(
                        report.toPrettyJson(),
                        'JSON',
                      ),
                    ),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.copy_all_outlined),
                      label: const Text('Copier CSV'),
                      onPressed: () => _copyToClipboard(
                        report.toCsv(),
                        'CSV',
                      ),
                    ),
                    OutlinedButton.icon(
                      icon: const Icon(Icons.share_outlined),
                      label: const Text('Partager'),
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                              content: Text('Partage: bientôt disponible')),
                        );
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  const _MetricRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodyMedium),
        Text(value, style: Theme.of(context).textTheme.titleMedium),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium,
      ),
    );
  }
}

class _CostDraft {
  final String label;
  final int amountCents;
  final String category;

  const _CostDraft({
    required this.label,
    required this.amountCents,
    required this.category,
  });
}
