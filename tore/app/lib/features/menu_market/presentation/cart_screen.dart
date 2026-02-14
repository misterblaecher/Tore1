import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/error_mapper.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_cta.dart';
import '../../../ui/components/tore_divider.dart';
import '../../../ui/components/tore_list_row.dart';
import '../../orders/presentation/order_qr_screen.dart';
import 'cart_state.dart';

class CartScreen extends ConsumerStatefulWidget {
  const CartScreen({
    super.key,
    required this.eventId,
    required this.tickets,
    required this.eventState,
  });

  final int eventId;
  final int? tickets;
  final String eventState;

  @override
  ConsumerState<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends ConsumerState<CartScreen> {
  bool _submitting = false;

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider(widget.eventId));
    final controller = ref.read(cartProvider(widget.eventId).notifier);
    final userId = ref.watch(userIdProvider);
    final runtimeWriteBlocked = isWriteBlockedByEventState(widget.eventState);
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    final writeBlocked = isWriteBlocked(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeBlocked: runtimeWriteBlocked);
    final insufficientBalance = widget.tickets != null && cart.totalTickets > widget.tickets!;
    final canConfirm = !cart.isEmpty &&
        !writeBlocked &&
        !insufficientBalance &&
        userId != null &&
        !_submitting;

    return Scaffold(
      appBar: AppBar(title: const Text('Panier')),
      body: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            if (writeBlocked)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: ServiceLimitedBanner(message: writeBlockedMessage(readOnly: readOnly, degradedBlocked: degradedBlocked, runtimeState: widget.eventState)),
              ),
            if (insufficientBalance)
              const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: ServiceLimitedBanner(message: 'Tickets insuffisants pour confirmer ce panier.'),
              ),
            ToreCard(
              child: Column(
                children: [
                  ToreListRow(
                    title: 'Articles',
                    trailing: Text(cart.totalItems.toString()),
                  ),
                  const ToreDivider(),
                  ToreListRow(
                    title: 'Total',
                    trailing: Text('🎟️ ${cart.totalTickets}'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Expanded(
              child: cart.isEmpty
                  ? const Center(child: Text('Panier vide. Ajoute un article depuis le menu.'))
                  : ListView.separated(
                      itemCount: cart.lines.length,
                      separatorBuilder: (_, __) => const ToreDivider(),
                      itemBuilder: (context, index) {
                        final line = cart.lines[index];
                        return ToreListRow(
                          title: '${line.name} ×${line.qty}',
                          subtitle: '${line.ticketCost} tickets/unité',
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                onPressed: () => controller.decrement(line.itemId),
                                icon: const Icon(Icons.remove_circle_outline),
                              ),
                              IconButton(
                                onPressed: () => controller.increment(line.itemId),
                                icon: const Icon(Icons.add_circle_outline),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
            ),
            const SizedBox(height: 8),
            ToreCTA(
              label: _submitting ? 'Confirmation...' : 'Confirmer',
              busy: _submitting,
              onPressed: canConfirm ? () => _confirmOrder(context, userId: userId!, cart: cart) : null,
            ),
            const SizedBox(height: 8),
            ToreCTA(
              label: 'Vider',
              style: ToreCTAStyle.secondary,
              onPressed: (cart.isEmpty || writeBlocked) ? null : controller.clear,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmOrder(BuildContext context, {required String userId, required CartState cart}) async {
    setState(() => _submitting = true);
    try {
      final api = ref.read(apiProvider);
      final barId = cart.lines.first.barId;
      final key = 'cart-${widget.eventId}-$userId-${DateTime.now().millisecondsSinceEpoch}';
      final order = await api.createOrder(
        barId: barId,
        eventId: widget.eventId,
        userId: userId,
        paymentMode: 'tickets',
        items: cart.lines
            .map(
              (line) => {
                'item_id': line.itemId,
                'qty': line.qty,
              },
            )
            .toList(),
        idempotencyKey: key,
      );
      final orderId = (order['id'] as num?)?.toInt() ?? int.tryParse(order['id']?.toString() ?? '');
      if (orderId == null || !context.mounted) return;

      ref.read(cartProvider(widget.eventId).notifier).clear();
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => OrderQrScreen(orderId: orderId)),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_friendlyError(e))),
      );
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  String _friendlyError(Object error) {
    if (error is DioException) {
      if (error.type == DioExceptionType.connectionTimeout || error.type == DioExceptionType.receiveTimeout) {
        return 'Timeout réseau. Réessaie.';
      }
      if (error.response?.statusCode == 429) {
        return 'Trop de requêtes. Réessaie dans quelques secondes.';
      }
      final data = error.response?.data;
      if (data is Map && data['detail'] is Map) {
        final detail = Map<String, dynamic>.from(data['detail'] as Map);
        final reason = detail['reason']?.toString();
        if (reason == 'insufficient_balance') return 'Pas assez de tickets.';
      }
    }
    final runtimeMessage = ErrorMapper.runtimeBlockedMessage(error);
    return runtimeMessage ?? ErrorMapper.message(error);
  }
}
