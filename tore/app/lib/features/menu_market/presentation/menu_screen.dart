import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/error_mapper.dart';
import '../../../screens/admin_prices.dart';
import '../../../screens/organizer.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/widgets/api_status_badge.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../../state.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../leaderboard/presentation/leaderboard_screen.dart';
import '../../qr/presentation/module_unavailable_screen.dart';
import '../../wallet/presentation/wallet_screen.dart';
import 'cart_screen.dart';
import 'cart_state.dart';
import 'menu_favorites_provider.dart';
import 'menu_item_availability.dart';
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
  bool _showFavoritesOnly = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_MenuData> _load() async {
    final api = ref.read(apiProvider);
    final userId = ref.read(userIdProvider);

    final event = await api.event(widget.eventId);
    final eventState = (event['state'] ?? event['status'] ?? event['event_state'] ?? 'LIVE').toString();

    final menuResult = await api.menuWithCacheStatus(widget.eventId);
    final items = menuResult.items.cast<Map<String, dynamic>>();
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
    final v = d['ticket_cost'] ?? d['tickets_cost'] ?? d['price_tickets'] ?? d['priceTickets'] ?? d['ticket_price'];
    if (v is num) return v.toInt();
    if (v != null) return int.tryParse(v.toString()) ?? 1;
    return 1;
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(meProvider);
    final userId = ref.watch(userIdProvider);
    final cart = ref.watch(cartProvider(widget.eventId));
    final favorites = ref.watch(menuFavoritesProvider(widget.eventId));
    final configAsync = ref.watch(eventConfigProvider(widget.eventId));
    final config = configAsync.maybeWhen(data: (value) => value, orElse: () => null);
    final configOfflineLimited = configAsync.maybeWhen(error: (err, _) => err is OfflineNoCacheException, orElse: () => false);
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
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrganizerScreen(eventId: widget.eventId)));
              },
            ),
          IconButton(
            tooltip: 'Portefeuille',
            icon: const Icon(Icons.account_balance_wallet_outlined),
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute(builder: (_) => WalletScreen(eventId: widget.eventId)));
              _refresh();
            },
          ),
          if (kDebugMode)
            IconButton(
              tooltip: 'Prix (Admin)',
              icon: const Icon(Icons.edit_outlined),
              onPressed: () {
                Navigator.of(context).push(MaterialPageRoute(builder: (_) => AdminPricesScreen(eventId: widget.eventId)));
              },
            ),
          IconButton(
            tooltip: 'Classement',
            icon: const Icon(Icons.emoji_events_outlined),
            onPressed: () {
              Navigator.of(context).push(MaterialPageRoute(builder: (_) => LeaderboardScreen(eventId: widget.eventId)));
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
            return Center(child: Text(ErrorMapper.message(err as Object)));
          }

          final data = snap.data ?? const _MenuData(items: [], tickets: null, isOffline: false, eventState: 'LIVE');
          final items = data.items;
          final tickets = data.tickets;
          final isOffline = data.isOffline;
          final runtimeWriteBlocked = isWriteBlockedByEventState(data.eventState);
          final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
          final allWritesBlocked = isWriteBlocked(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: runtimeWriteBlocked);
          final visibleItems = _showFavoritesOnly
              ? items.where((item) {
                  final id = ((item['id'] as int?) ?? (item['item_id'] as int?) ?? (item['drink_id'] as int?) ?? 0);
                  return favorites.contains(id);
                }).toList()
              : items;

          final top = Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
            child: Row(
              children: [
                ApiStatusBadge(isOffline: isOffline),
                const SizedBox(width: 8),
                Badge(
                  label: Text(cart.totalItems.toString()),
                  child: IconButton(
                    tooltip: 'Panier',
                    icon: const Icon(Icons.shopping_cart_outlined),
                    onPressed: () {
                      Navigator.of(context).push(
                        MaterialPageRoute(
                          builder: (_) => CartScreen(
                            eventId: widget.eventId,
                            tickets: tickets,
                            eventState: data.eventState,
                            menuItems: items,
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (tickets != null) Chip(label: Text('🎟️ $tickets')) else const SizedBox.shrink(),
                const SizedBox(width: 8),
                FilterChip(
                  label: const Text('Favoris'),
                  selected: _showFavoritesOnly,
                  onSelected: (_) => setState(() => _showFavoritesOnly = !_showFavoritesOnly),
                ),
              ],
            ),
          );

          if (visibleItems.isEmpty) {
            return Column(
              children: [
                if (configOfflineLimited)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: _LimitedModeBanner(),
                  ),
                if (allWritesBlocked)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                    child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeState: data.eventState)),
                  ),
                top,
                Expanded(child: Center(child: Text(_showFavoritesOnly ? 'Aucun favori.' : 'Menu vide'))),
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
              if (allWritesBlocked)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                  child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeState: data.eventState)),
                ),
              top,
              Expanded(
                child: ListView.separated(
                  itemCount: visibleItems.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final d = visibleItems[i];

                    final itemId = ((d['id'] as int?) ?? (d['item_id'] as int?) ?? (d['drink_id'] as int?) ?? 0);
                    final name = (d['name'] ?? '').toString();
                    final type = (d['type'] ?? '').toString();
                    final base = (d['base_price_cents'] as int?) ?? 0;
                    final eff = (d['effective_price_cents'] as int?) ?? base;
                    final effPrice = (eff / 100.0).toStringAsFixed(2);
                    final subtitle = type.isEmpty ? 'Prix: $effPrice €' : '$type • $effPrice €';

                    final requiredTickets = _requiredTickets(d);
                    final hasEnoughTickets = tickets == null ? true : tickets >= requiredTickets;
                    final stockState = menuItemStockState(d);
                    final isOut = stockState == MenuItemStockState.out;
                    final isLow = stockState == MenuItemStockState.low;
                    final isFavorite = favorites.contains(itemId);
                    final disabledBecauseAuth = userId == null;
                    final disabledBecauseOffline = isOffline || degradedBlocked;
                    final disabledBecauseEventState = allWritesBlocked;
                    final cartController = ref.read(cartProvider(widget.eventId).notifier);

                    return ListTile(
                      onTap: () {
                        showModalBottomSheet<void>(
                          context: context,
                          isScrollControlled: true,
                          builder: (_) => MenuItemDetailSheet(
                            item: d,
                            enabled: !(disabledBecauseAuth || disabledBecauseOffline || disabledBecauseEventState || isOut),
                            onAdd: (qty) {
                              cartController.addOrIncrement(
                                itemId: itemId,
                                barId: int.tryParse((d['bar_id'] ?? d['barId'] ?? '').toString()) ?? 0,
                                name: name,
                                subtitle: subtitle,
                                ticketCost: requiredTickets,
                                available: d['available'] as bool?,
                                stockStatus: (d['stockStatus'] ?? d['stock_status'])?.toString(),
                                feeTickets: (d['feeTickets'] as num?)?.toInt() ?? 0,
                                qty: qty,
                              );
                              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$name ajouté au panier (x$qty)')));
                            },
                          ),
                        );
                      },
                      title: Row(
                        children: [
                          Expanded(child: Text(name.isEmpty ? '(Sans nom)' : name)),
                          IconButton(
                            onPressed: itemId == 0 ? null : () => ref.read(menuFavoritesProvider(widget.eventId).notifier).toggle(itemId),
                            icon: Icon(isFavorite ? Icons.star : Icons.star_border),
                          ),
                        ],
                      ),
                      subtitle: Text(subtitle),
                      leading: isOut
                          ? const Chip(label: Text('RUPTURE'))
                          : (isLow ? const Chip(label: Text('LOW')) : null),
                      trailing: SizedBox(
                        width: 130,
                        child: ElevatedButton(
                          onPressed: (itemId == 0 || disabledBecauseAuth || disabledBecauseOffline || disabledBecauseEventState || isOut || !hasEnoughTickets)
                              ? null
                              : () {
                                  cartController.addOrIncrement(
                                    itemId: itemId,
                                    barId: int.tryParse((d['bar_id'] ?? d['barId'] ?? '').toString()) ?? 0,
                                    name: name,
                                    subtitle: subtitle,
                                    ticketCost: requiredTickets,
                                    available: d['available'] as bool?,
                                    stockStatus: (d['stockStatus'] ?? d['stock_status'])?.toString(),
                                    feeTickets: (d['feeTickets'] as num?)?.toInt() ?? 0,
                                  );
                                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$name ajouté au panier')));
                                },
                          child: Text(
                            disabledBecauseAuth
                                ? 'Auth...'
                                : (disabledBecauseOffline
                                    ? 'Hors-ligne'
                                    : (disabledBecauseEventState
                                        ? 'Bloqué'
                                        : (isOut ? 'RUPTURE' : (!hasEnoughTickets ? 'Tickets ×$requiredTickets' : 'Ajouter')))),
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
