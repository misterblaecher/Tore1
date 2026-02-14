import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../../shared/widgets/api_status_badge.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import '../../../shared/widgets/offline_fallback_screen.dart';
import '../../../screens/organizer.dart';
import '../../wallet/presentation/wallet_screen.dart';
import '../../../screens/admin_prices.dart';
import '../../leaderboard/presentation/leaderboard_screen.dart';
import '../../orders/presentation/order_qr_screen.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../qr/presentation/module_unavailable_screen.dart';

class MenuScreen extends ConsumerStatefulWidget {
  const MenuScreen({super.key, required this.eventId});
  final int eventId;

  @override
  ConsumerState<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends ConsumerState<MenuScreen> {
  late Future<_MenuData> _future;
  bool _didLoadWithUser = false;
  final Map<int, bool> _ordering = <int, bool>{};

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_MenuData> _load() async {
    final api = ref.read(apiProvider);
    final userId = ref.read(userIdProvider);

    // Menu peut être consulté même si auth pas encore prête
    final menuResult = await api.menuWithCacheStatus(widget.eventId);
    final items = (menuResult.items).cast<Map<String, dynamic>>();
    var isOffline = menuResult.fromCache;

    if (userId == null) {
      return _MenuData(items: items, tickets: null, isOffline: isOffline);
    }

    int? tickets;
    try {
      final bal = await api.ticketBalance(eventId: widget.eventId, userId: userId);
      final ticketsValue = bal['balance'] ?? bal['tickets'] ?? bal['amount'] ?? bal['value'] ?? 0;
      tickets = (ticketsValue is num) ? ticketsValue.toInt() : int.tryParse(ticketsValue.toString()) ?? 0;
    } catch (_) {
      isOffline = true;
    }

    return _MenuData(items: items, tickets: tickets, isOffline: isOffline);
  }

  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  int _requiredTickets(Map<String, dynamic> d) {
    // Backend fields can vary; try a few.
    final v = d['ticket_cost'] ?? d['tickets_cost'] ?? d['price_tickets'] ?? d['ticket_price'];
    if (v is num) return v.toInt();
    if (v != null) return int.tryParse(v.toString()) ?? 1;
    return 1; // default: 1 ticket per item
  }

  Future<int?> _pickQty(BuildContext context) async {
    int qty = 1;
    return showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Quantité'),
        content: StatefulBuilder(
          builder: (ctx, setState) => Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                onPressed: qty <= 1 ? null : () => setState(() => qty -= 1),
                icon: const Icon(Icons.remove_circle_outline),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(qty.toString(), style: Theme.of(ctx).textTheme.headlineSmall),
              ),
              IconButton(
                onPressed: qty >= 10 ? null : () => setState(() => qty += 1),
                icon: const Icon(Icons.add_circle_outline),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(qty),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Déclenche auth/token dès l'ouverture
    ref.watch(meProvider);
    final api = ref.read(apiProvider);
    final userId = ref.watch(userIdProvider);
    final configAsync = ref.watch(eventConfigProvider(widget.eventId));
    final config = configAsync.maybeWhen(
      data: (value) => value,
      orElse: () => null,
    );
    final configOfflineLimited = configAsync.maybeWhen(
      error: (err, _) => err is OfflineNoCacheException,
      orElse: () => false,
    );

    if (config != null && !config.menuEnabled) {
      return const ModuleUnavailableScreen(
        title: 'Menu indisponible',
        message: 'Ce module est désactivé pour cet event.',
        reasonCode: 'module_off',
      );
    }

    // Si initState a chargé sans userId, on recharge une fois dès que le user arrive.
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
              // En revenant du wallet, on refresh tickets
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
            if (err is OfflineNoCacheException) {
              return OfflineFallbackScreen(
                title: 'Hors-ligne',
                message: 'Impossible de charger le menu sans réseau ni cache.',
                onRetry: _refresh,
              );
            }
            return Center(child: Text(ErrorMapper.message(err as Object)));
          }

          final data = snap.data ?? const _MenuData(items: [], tickets: null, isOffline: false);
          final items = data.items;
          final tickets = data.tickets;
          final isOffline = data.isOffline;

          final top = Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Row(
              children: [
                const ApiStatusBadge(),
                const Spacer(),
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
                    final isBusy = _ordering[itemId] == true;

                    return ListTile(
                      title: Text(name.isEmpty ? '(Sans nom)' : name),
                      subtitle: Text(subtitle),
                      trailing: SizedBox(
                        width: 130,
                        child: ElevatedButton(
                          onPressed: (itemId == 0 ||
                                  disabledBecauseAuth ||
                                  disabledBecauseOffline ||
                                  !hasEnoughTickets ||
                                  isBusy)
                              ? null
                              : () async {
                                  try {
                                    final uid = userId; // non-null ici
                                    if (uid == null) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('Auth en cours...')),
                                      );
                                      return;
                                    }

                                    final qty = await _pickQty(context) ?? 1;

                                    // Validate tickets with chosen quantity
                                    if (tickets != null && tickets < requiredTickets * qty) {
                                      if (!context.mounted) return;
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        SnackBar(content: Text('Tickets insuffisants (besoin: ${requiredTickets * qty})')),
                                      );
                                      return;
                                    }

                                    setState(() => _ordering[itemId] = true);
                                    try {
                                      final barIdRaw = d['bar_id'] ?? d['barId'];
                                      final resolvedBarId = (barIdRaw is num)
                                          ? barIdRaw.toInt()
                                          : int.tryParse(barIdRaw?.toString() ?? '') ?? 0;
                                      if (resolvedBarId <= 0) {
                                        throw Exception('bar_id manquant pour commander');
                                      }
                                      final idemKey = 'menu-${widget.eventId}-${itemId}-${DateTime.now().millisecondsSinceEpoch}';
                                      final order = await api.createOrder(
                                        barId: resolvedBarId,
                                        eventId: widget.eventId,
                                        userId: uid,
                                        paymentMode: 'tickets',
                                        items: [
                                          {'item_id': itemId, 'qty': qty},
                                        ],
                                        idempotencyKey: idemKey,
                                      );
                                      final orderId = (order['id'] as num?)?.toInt() ?? int.tryParse(order['id']?.toString() ?? '');
                                      if (context.mounted && orderId != null) {
                                        unawaited(Navigator.of(context).push(
                                          MaterialPageRoute(
                                            builder: (_) => OrderQrScreen(orderId: orderId),
                                          ),
                                        ));
                                      }
                                    } finally {
                                      if (mounted) {
                                        setState(() => _ordering[itemId] = false);
                                      }
                                    }

                                    if (!context.mounted) return;
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text('✅ Commande envoyée: $name (QR prêt)')),
                                    );

                                    // Refresh balance/menu
                                    _refresh();
                                  } catch (e) {
                                    if (!context.mounted) return;
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text('Erreur commande: ${ErrorMapper.message(e)}')),
                                    );
                                  }
                                },
                          child: Text(
                            disabledBecauseAuth
                                ? 'Auth...'
                                : (disabledBecauseOffline
                                    ? 'Hors-ligne'
                                    : (isBusy
                                        ? '...'
                                        : (!hasEnoughTickets ? 'Tickets ×$requiredTickets' : 'Commander'))),
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

  const _MenuData({
    required this.items,
    required this.tickets,
    required this.isOffline,
  });
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
