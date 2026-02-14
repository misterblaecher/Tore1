import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../shared/widgets/api_status_badge.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/widgets/offline_fallback_screen.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../screens/organizer.dart';
import '../../wallet/presentation/wallet_screen.dart';
import '../../../screens/admin_prices.dart';
import '../../leaderboard/presentation/leaderboard_screen.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../qr/presentation/module_unavailable_screen.dart';
import 'cart_screen.dart';
import 'cart_state.dart';
import 'menu_item_detail_sheet.dart';

class MenuScreen extends ConsumerStatefulWidget {
  const MenuScreen({super.key, required this.eventId});
  final int eventId;

  @override
  ConsumerState<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends ConsumerState<MenuScreen> {
  late Future<_MenuData> _future;
  bool _didLoadWithUser = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_MenuData> _load() async {
    final api = ref.read(apiProvider);
    final userId = ref.read(userIdProvider);

    final event = await api.event(widget.eventId).timeout(const Duration(seconds: 6), onTimeout: () {
      throw const _MenuLoadTimeoutException();
    });
    final eventState = (event['state'] ?? event['status'] ?? event['event_state'] ?? 'LIVE').toString();

    final menuResult = await api.menuWithCacheStatus(widget.eventId).timeout(const Duration(seconds: 6), onTimeout: () {
      throw const _MenuLoadTimeoutException();
    });
    final items = (menuResult.items).cast<Map<String, dynamic>>();
    var isOffline = menuResult.fromCache;

    if (userId == null) {
      return _MenuData(items: items, tickets: null, isOffline: isOffline, eventState: eventState);
    }

    int? tickets;
    try {
      final bal = await api.ticketBalance(eventId: widget.eventId, userId: userId);
      final ticketsValue = bal['balance'] ?? bal['tickets'] ?? bal['amount'] ?? bal['value'] ?? 0;
      tickets = (ticketsValue is num) ? ticketsValue.toInt() : int.tryParse(ticketsValue.toString()) ?? 0;
    } catch (_) {
      isOffline = true;
    }

    return _MenuData(items: items, tickets: tickets, isOffline: isOffline, eventState: eventState);
  }

  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  int _requiredTickets(Map<String, dynamic> d) {
    final v = d['ticket_cost'] ?? d['tickets_cost'] ?? d['price_tickets'] ?? d['ticket_price'];
    if (v is num) return v.toInt();
    if (v != null) return int.tryParse(v.toString()) ?? 1;
    return 1;
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(meProvider);
    final userId = ref.watch(userIdProvider);
    final cart = ref.watch(cartProvider(widget.eventId));
    final configAsync = ref.watch(eventConfigProvider(widget.eventId));
    final config = configAsync.maybeWhen(
      data: (value) => value,
      orElse: () => null,
    );
    final configOfflineLimited = configAsync.maybeWhen(
      error: (err, _) => err is OfflineNoCacheException,
      orElse: () => false,
    );
    final readOnly = isReadOnly(ref);

    if (config != null && !config.menuEnabled) {
      return const ModuleUnavailableScreen(
        title: 'Menu indisponible',
        message: 'Ce module est désactivé pour cet event.',
        reasonCode: 'module_off',
      );
    }

    if (userId != null && !_didLoadWithUser) {
      _didLoadWithUser = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Menu — Event ${widget.eventId}'),
        actions: [
          if (kDebugMode)
            IconButton(
              tooltip: 'Organisateur',
              icon: const Icon(Icons.event_note_outlined),
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => OrganizerScreen(eventId: widget.eventId),
                  ),
                );
              },
            ),
          IconButton(
            tooltip: 'Portefeuille',
            icon: const Icon(Icons.account_balance_wallet_outlined),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => WalletScreen(eventId: widget.eventId),
                ),
              );
              _refresh();
            },
          ),
          if (kDebugMode)
            IconButton(
              tooltip: 'Prix (Admin)',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => AdminPricesScreen(eventId: widget.eventId),
                  ),
                );
              },
            ),
          IconButton(
            tooltip: 'Classement',
            icon: const Icon(Icons.emoji_events_outlined),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => LeaderboardScreen(eventId: widget.eventId),
                ),
              );
            },
          ),
        ],
      ),
      body: FutureBuilder<_MenuData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snap.hasError) {
            final err = snap.error;
            if (err is _MenuLoadTimeoutException) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Text('Réseau lent. Impossible de charger le menu.'),
                      const SizedBox(height: 10),
                      OutlinedButton(onPressed: _refresh, child: const Text('Réessayer')),
                    ],
                  ),
                ),
              );
            }
            if (err is OfflineNoCacheException) {
              return OfflineFallbackScreen(
                title: 'Hors-ligne',
                message: 'Impossible de charger le menu sans réseau ni cache.',
                onRetry: _refresh,
              );
            }
            return Center(child: Text(ErrorMapper.message(err as Object)));
          }

          final data = snap.data ?? const _MenuData(items: [], tickets: null, isOffline: false, eventState: 'LIVE');
          final items = data.items;
          final tickets = data.tickets;
          final isOffline = data.isOffline;
          final writeBlocked = isWriteBlockedByEventState(data.eventState);
          final allWritesBlocked = isWriteBlocked(readOnly: readOnly, runtimeBlocked: writeBlocked);

          final top = Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Row(
              children: [
                const ApiStatusBadge(),
                const Spacer(),
                IconButton(
                  tooltip: 'Panier',
                  icon: Badge(
                    isLabelVisible: cart.totalItems > 0,
                    label: Text(cart.totalItems.toString()),
                    child: const Icon(Icons.shopping_cart_outlined),
                  ),
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => CartScreen(
                          eventId: widget.eventId,
                          tickets: tickets,
                          eventState: data.eventState,
                          isOffline: isOffline,
                        ),
                      ),
                    );
                  },
                ),
                if (tickets != null)
                  Chip(
                    label: Text('🎟️ $tickets'),
                  )
                else
                  const SizedBox.shrink(),
              ],
            ),
          );

          if (items.isEmpty) {
            return Column(
              children: [
                if (configOfflineLimited)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: _LimitedModeBanner(),
                  ),
                if (isOffline)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: _OfflineOrdersBanner(),
                  ),
                if (allWritesBlocked)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, runtimeState: data.eventState)),
                  ),
                top,
                const Expanded(child: Center(child: Text('Menu vide'))),
              ],
            );
          }

          return Column(
            children: [
              if (configOfflineLimited)
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: _LimitedModeBanner(),
                ),
              if (isOffline)
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: _OfflineOrdersBanner(),
                ),
              if (allWritesBlocked)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, runtimeState: data.eventState)),
                ),
              top,
              Expanded(
                child: ListView.separated(
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final d = items[i];

                    final itemId = ((d['id'] as int?) ?? (d['item_id'] as int?) ?? (d['drink_id'] as int?) ?? 0);
                    final name = (d['name'] ?? '').toString();
                    final type = (d['type'] ?? '').toString();
                    final base = (d['base_price_cents'] as int?) ?? 0;
                    final eff = (d['effective_price_cents'] as int?) ?? base;

                    final effPrice = (eff / 100.0).toStringAsFixed(2);
                    final subtitle = type.isEmpty ? 'Prix: $effPrice €' : '$type • $effPrice €';

                    final requiredTickets = _requiredTickets(d);
                    final hasEnoughTickets = tickets == null ? true : tickets >= requiredTickets;

                    final disabledBecauseAuth = userId == null;
                    final disabledBecauseOffline = isOffline;
                    final disabledBecauseEventState = allWritesBlocked;
                    final cartController = ref.read(cartProvider(widget.eventId).notifier);

                    return ListTile(
                      onTap: () {
                        showModalBottomSheet<void>(
                          context: context,
                          isScrollControlled: true,
                          builder: (_) => MenuItemDetailSheet(
                            item: d,
                            enabled: !(disabledBecauseAuth || disabledBecauseOffline || disabledBecauseEventState),
                            onAdd: (qty) {
                              cartController.addOrIncrement(
                                itemId: itemId,
                                barId: int.tryParse((d['bar_id'] ?? d['barId'] ?? '').toString()) ?? 0,
                                name: name,
                                subtitle: subtitle,
                                ticketCost: requiredTickets,
                                qty: qty,
                              );
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('$name ajouté au panier (x$qty)')),
                              );
                            },
                          ),
                        );
                      },
                      title: Text(name.isEmpty ? '(Sans nom)' : name),
                      subtitle: Text(subtitle),
                      trailing: SizedBox(
                        width: 130,
                        child: ElevatedButton(
                          onPressed: (itemId == 0 ||
                                  disabledBecauseAuth ||
                                  disabledBecauseOffline ||
                                  disabledBecauseEventState ||
                                  !hasEnoughTickets)
                              ? null
                              : () async {
                                  cartController.addOrIncrement(
                                    itemId: itemId,
                                    barId: int.tryParse((d['bar_id'] ?? d['barId'] ?? '').toString()) ?? 0,
                                    name: name,
                                    subtitle: subtitle,
                                    ticketCost: requiredTickets,
                                  );
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text('$name ajouté au panier')),
                                  );
                                },
                          child: Text(
                            disabledBecauseAuth
                                ? 'Auth...'
                                : (disabledBecauseOffline
                                    ? 'Hors-ligne'
                                    : (disabledBecauseEventState
                                        ? 'Bloqué'
                                        : (!hasEnoughTickets ? 'Tickets ×$requiredTickets' : 'Ajouter'))),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _MenuData {
  final List<Map<String, dynamic>> items;
  final int? tickets;
  final bool isOffline;
  final String eventState;

  const _MenuData({
    required this.items,
    required this.tickets,
    required this.isOffline,
    required this.eventState,
  });
}

class _MenuLoadTimeoutException implements Exception {
  const _MenuLoadTimeoutException();
}

class _OfflineOrdersBanner extends StatelessWidget {
  const _OfflineOrdersBanner();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.orange.shade100,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.cloud_off_outlined),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Hors-ligne : commandes désactivées.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LimitedModeBanner extends StatelessWidget {
  const _LimitedModeBanner();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.blueGrey.shade100,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.info_outline),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Mode limité : configuration indisponible.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
