import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/network_state_provider.dart';
import '../domain/operational_models.dart';
import 'operational_providers.dart';

class BarOperationalHubScreen extends ConsumerStatefulWidget {
  const BarOperationalHubScreen({super.key, required this.capability});

  final ScopedCapability capability;

  @override
  ConsumerState<BarOperationalHubScreen> createState() =>
      _BarOperationalHubScreenState();
}

class _BarOperationalHubScreenState
    extends ConsumerState<BarOperationalHubScreen> {
  final Set<int> _busyOrders = {};
  final Set<int> _busyItems = {};

  @override
  Widget build(BuildContext context) {
    final barId = widget.capability.barId!;
    final hub = ref.watch(barOperationalHubProvider(barId));
    final orders = ref.watch(barOperationalOrdersProvider(barId));
    final menu = ref.watch(barOperationalMenuProvider(barId));
    final network = ref.watch(networkStatusProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(operationalCapabilitiesProvider);
        ref.invalidate(barOperationalHubProvider(barId));
        ref.invalidate(barOperationalMenuProvider(barId));
        final _ = await ref.refresh(barOperationalOrdersProvider(barId).future);
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(widget.capability.displayName,
              style: Theme.of(context).textTheme.headlineSmall),
          Text('${widget.capability.role} · ${widget.capability.source}'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              Chip(label: Text('Réseau : ${network.name}')),
              for (final action in widget.capability.actions)
                Chip(label: Text(action.split('.').last)),
            ],
          ),
          hub.when(
            loading: () => const LinearProgressIndicator(),
            error: (_, __) => const ListTile(
                leading: Icon(Icons.error_outline),
                title: Text('Bar opérationnel indisponible')),
            data: (result) => ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.storefront_outlined),
              title: Text(
                  'État partenaire : ${((result.data['bar'] as Map?)?['partner_status'] ?? '—')}'),
              subtitle: Text(result.isFromCache
                  ? 'Donnée locale · lecture seule'
                  : 'Synchronisé : ${result.cachedAt ?? 'maintenant'}'),
            ),
          ),
          const Divider(),
          Text('Aperçu', style: Theme.of(context).textTheme.titleLarge),
          orders.when(
            loading: () => const LinearProgressIndicator(),
            error: (_, __) => const Text('Aperçu indisponible'),
            data: (result) {
              final items =
                  (result.data['items'] as List? ?? const []).whereType<Map>();
              final active = items
                  .where((order) => const {'NEW', 'IN_PROGRESS', 'READY'}
                      .contains(order['status']?.toString()))
                  .length;
              final counts = <String, int>{};
              for (final order in items) {
                if (order['status'] == 'CANCELLED') continue;
                for (final item
                    in (order['items'] as List? ?? const []).whereType<Map>()) {
                  final name = item['name']?.toString() ?? '';
                  if (name.isNotEmpty) {
                    counts[name] = (counts[name] ?? 0) +
                        ((item['qty'] as num?)?.toInt() ?? 0);
                  }
                }
              }
              final top = counts.entries.toList()
                ..sort((a, b) => b.value.compareTo(a.value));
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.receipt_long_outlined),
                    title: Text('$active commandes actives'),
                    subtitle: Text(result.isFromCache
                        ? 'Données locales · lecture seule'
                        : 'Sur les ${items.length} dernières commandes'),
                  ),
                  if (top.isNotEmpty)
                    Text(
                        'Produits principaux : ${top.take(3).map((entry) => '${entry.key} (${entry.value})').join(', ')}'),
                ],
              );
            },
          ),
          const Divider(),
          Text('Menu produits', style: Theme.of(context).textTheme.titleLarge),
          menu.when(
            loading: () => const LinearProgressIndicator(),
            error: (_, __) => const ListTile(title: Text('Menu indisponible')),
            data: (result) {
              final items = (result.data['items'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => item.cast<String, dynamic>());
              if (items.isEmpty) {
                return const ListTile(title: Text('Aucun produit'));
              }
              return Column(children: [
                if (result.isFromCache)
                  const ListTile(title: Text('Menu local · lecture seule')),
                for (final item in items) _menuItem(item, result.isFromCache),
              ]);
            },
          ),
          const Divider(),
          Text('Commandes', style: Theme.of(context).textTheme.titleLarge),
          orders.when(
            loading: () => const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator())),
            error: (_, __) => ListTile(
              leading: const Icon(Icons.error_outline),
              title: const Text('Commandes indisponibles'),
              trailing: IconButton(
                onPressed: () =>
                    ref.invalidate(barOperationalOrdersProvider(barId)),
                icon: const Icon(Icons.refresh),
              ),
            ),
            data: (result) {
              final items = (result.data['items'] as List? ?? const [])
                  .whereType<Map>()
                  .map((item) => item.cast<String, dynamic>());
              if (items.isEmpty) {
                return const ListTile(title: Text('Aucune commande active'));
              }
              return Column(
                children: [
                  if (result.isFromCache)
                    const ListTile(
                        leading: Icon(Icons.cloud_off_outlined),
                        title: Text(
                            'Dernière liste locale — actions désactivées')),
                  for (final order in items)
                    _orderCard(order, result.isFromCache),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _menuItem(Map<String, dynamic> item, bool fromCache) {
    final id = (item['id'] as num).toInt();
    final available = item['available'] == true;
    final stock = item['stock_status']?.toString() ?? 'IN';
    final stockLabel = switch (stock) {
      'LOW' => 'Stock faible',
      'OUT' => 'Rupture',
      _ => 'Disponible',
    };
    final price = (((item['price_cents'] as num?)?.toInt() ?? 0) / 100)
        .toStringAsFixed(2);
    final allowed = OperationalGuard.canPerform(
      capability: widget.capability,
      action: 'bar.manage_menu',
      mode: OperationalMode.bar,
      scopeId: widget.capability.barId!,
    );
    final canEdit = allowed &&
        ref.watch(networkStatusProvider) == NetworkState.online &&
        !fromCache &&
        !_busyItems.contains(id);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(item['name']?.toString() ?? 'Produit #$id'),
      subtitle: Text(
          '${item['category'] ?? ''} · $price € · ${available ? stockLabel : 'Rupture'}'),
      trailing: PopupMenuButton<String>(
        tooltip: 'Disponibilité',
        enabled: canEdit,
        onSelected: (value) => _updateItem(item, value),
        itemBuilder: (_) => const [
          PopupMenuItem(value: 'IN', child: Text('Disponible')),
          PopupMenuItem(value: 'LOW', child: Text('Stock faible')),
          PopupMenuItem(value: 'OUT', child: Text('Rupture')),
        ],
      ),
    );
  }

  Future<void> _updateItem(Map<String, dynamic> item, String stock) async {
    final id = (item['id'] as num).toInt();
    if (_busyItems.contains(id) ||
        ref.read(networkStatusProvider) != NetworkState.online ||
        !OperationalGuard.canPerform(
          capability: widget.capability,
          action: 'bar.manage_menu',
          mode: OperationalMode.bar,
          scopeId: widget.capability.barId!,
        )) return;
    setState(() => _busyItems.add(id));
    try {
      await ref.read(operationalRepositoryProvider).updateBarMenuAvailability(
            barId: widget.capability.barId!,
            itemId: id,
            available: stock != 'OUT',
            stockStatus: stock,
            expectedVersion: (item['version'] as num).toInt(),
            idempotencyKey:
                'mobile-menu-$id-${DateTime.now().microsecondsSinceEpoch}',
          );
      ref.invalidate(barOperationalMenuProvider(widget.capability.barId!));
    } catch (_) {
      ref.invalidate(operationalCapabilitiesProvider);
      ref.invalidate(barOperationalMenuProvider(widget.capability.barId!));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Mise à jour refusée ou menu modifié'),
        ));
      }
    } finally {
      if (mounted) setState(() => _busyItems.remove(id));
    }
  }

  Widget _orderCard(Map<String, dynamic> order, bool fromCache) {
    final orderId = (order['id'] as num).toInt();
    final status = (order['status'] ?? 'NEW').toString();
    final next = switch (status) {
      'NEW' => 'accept',
      'IN_PROGRESS' => 'ready',
      'READY' => 'complete',
      _ => null,
    };
    final online = ref.watch(networkStatusProvider) == NetworkState.online;
    final allowed = OperationalGuard.canPerform(
        capability: widget.capability,
        action: 'bar.manage_orders',
        mode: OperationalMode.bar,
        scopeId: widget.capability.barId!);
    return Card(
      child: ListTile(
        title: Text('Commande #$orderId · $status'),
        subtitle: Text('${order['total_tickets'] ?? 0} Credits'),
        trailing: next == null
            ? const Icon(Icons.check_circle_outline)
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FilledButton(
                    onPressed: allowed &&
                            online &&
                            !fromCache &&
                            !_busyOrders.contains(orderId)
                        ? () => _transition(orderId, next)
                        : null,
                    child: _busyOrders.contains(orderId)
                        ? const SizedBox.square(
                            dimension: 18, child: CircularProgressIndicator())
                        : Text(next.toUpperCase()),
                  ),
                  if (status == 'NEW' || status == 'IN_PROGRESS')
                    IconButton(
                      tooltip: 'Annuler',
                      onPressed: allowed &&
                              online &&
                              !fromCache &&
                              !_busyOrders.contains(orderId)
                          ? () => _cancel(orderId)
                          : null,
                      icon: const Icon(Icons.cancel_outlined),
                    ),
                ],
              ),
      ),
    );
  }

  Future<void> _cancel(int orderId) async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Annuler la commande'),
            content: TextField(
              controller: controller,
              decoration: const InputDecoration(labelText: 'Motif obligatoire'),
            ),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Retour')),
              FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Annuler la commande')),
            ],
          ),
        ) ??
        false;
    final reason = controller.text.trim();
    controller.dispose();
    if (!confirmed || reason.length < 3) return;
    await _transition(orderId, 'cancel', reason: reason);
  }

  Future<void> _transition(int orderId, String action, {String? reason}) async {
    if (_busyOrders.contains(orderId)) return;
    setState(() => _busyOrders.add(orderId));
    try {
      await ref.read(operationalRepositoryProvider).transitionOrder(
            barId: widget.capability.barId!,
            orderId: orderId,
            action: action,
            reason: reason,
            idempotencyKey:
                'mobile-order-$orderId-$action-${DateTime.now().microsecondsSinceEpoch}',
          );
      ref.invalidate(barOperationalOrdersProvider(widget.capability.barId!));
    } catch (_) {
      ref.invalidate(operationalCapabilitiesProvider);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Transition refusée ou accès expiré')));
      }
    } finally {
      if (mounted) setState(() => _busyOrders.remove(orderId));
    }
  }
}
