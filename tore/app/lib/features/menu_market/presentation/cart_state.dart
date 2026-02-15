import 'package:flutter_riverpod/flutter_riverpod.dart';

class CartLine {
  final int itemId;
  final int barId;
  final String name;
  final String? subtitle;
  final int ticketCost;
  final int feeTickets;
  final int qty;
  final bool? available;
  final String? stockStatus;

  const CartLine({
    required this.itemId,
    required this.barId,
    required this.name,
    required this.subtitle,
    required this.ticketCost,
    this.feeTickets = 0,
    required this.qty,
    this.available,
    this.stockStatus,
  });

  CartLine copyWith({int? qty, bool? available, String? stockStatus}) {
    return CartLine(
      itemId: itemId,
      barId: barId,
      name: name,
      subtitle: subtitle,
      ticketCost: ticketCost,
      feeTickets: feeTickets,
      qty: qty ?? this.qty,
      available: available ?? this.available,
      stockStatus: stockStatus ?? this.stockStatus,
    );
  }
}

class CartState {
  final List<CartLine> lines;

  const CartState({this.lines = const []});

  int get totalTickets => lines.fold(0, (sum, line) => sum + (line.ticketCost * line.qty));
  int get totalFeesTickets => lines.fold(0, (sum, line) => sum + (line.feeTickets * line.qty));
  int get totalEstimatedTickets => totalTickets + totalFeesTickets;
  int get totalItems => lines.fold(0, (sum, line) => sum + line.qty);
  bool get isEmpty => lines.isEmpty;
}

class CartController extends StateNotifier<CartState> {
  CartController() : super(const CartState());

  void addOrIncrement({
    required int itemId,
    required int barId,
    required String name,
    String? subtitle,
    required int ticketCost,
    int feeTickets = 0,
    bool? available,
    String? stockStatus,
    int qty = 1,
  }) {
    final index = state.lines.indexWhere((line) => line.itemId == itemId);
    if (index == -1) {
      state = CartState(
        lines: [
          ...state.lines,
          CartLine(
            itemId: itemId,
            barId: barId,
            name: name,
            subtitle: subtitle,
            ticketCost: ticketCost,
            feeTickets: feeTickets,
            qty: qty,
            available: available,
            stockStatus: stockStatus,
          ),
        ],
      );
      return;
    }

    final next = [...state.lines];
    final existing = next[index];
    next[index] = existing.copyWith(qty: (existing.qty + qty).clamp(1, 99));
    state = CartState(lines: next);
  }

  void increment(int itemId) {
    _updateQty(itemId, delta: 1);
  }

  void decrement(int itemId) {
    _updateQty(itemId, delta: -1);
  }

  void _updateQty(int itemId, {required int delta}) {
    final index = state.lines.indexWhere((line) => line.itemId == itemId);
    if (index == -1) return;
    final next = [...state.lines];
    final line = next[index];
    final qty = line.qty + delta;
    if (qty <= 0) {
      next.removeAt(index);
    } else {
      next[index] = line.copyWith(qty: qty.clamp(1, 99));
    }
    state = CartState(lines: next);
  }

  void remove(int itemId) {
    state = CartState(lines: state.lines.where((line) => line.itemId != itemId).toList());
  }

  void removeUnavailable() {
    state = CartState(
      lines: state.lines.where((line) {
        final status = line.stockStatus?.toUpperCase();
        final isOut = line.available == false || status == 'OUT';
        return !isOut;
      }).toList(),
    );
  }

  void clear() => state = const CartState();
}

final cartProvider = StateNotifierProvider.family<CartController, CartState, int>((ref, eventId) {
  return CartController();
});
