import 'package:flutter_riverpod/flutter_riverpod.dart';

class CartLine {
  final int itemId;
  final int barId;
  final String name;
  final String? subtitle;
  final int ticketCost;
  final int qty;

  const CartLine({
    required this.itemId,
    required this.barId,
    required this.name,
    required this.subtitle,
    required this.ticketCost,
    required this.qty,
  });

  CartLine copyWith({int? qty}) {
    return CartLine(
      itemId: itemId,
      barId: barId,
      name: name,
      subtitle: subtitle,
      ticketCost: ticketCost,
      qty: qty ?? this.qty,
    );
  }
}

class CartState {
  final List<CartLine> lines;

  const CartState({this.lines = const []});

  int get totalTickets => lines.fold(0, (sum, line) => sum + (line.ticketCost * line.qty));
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
            qty: qty,
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

  void clear() => state = const CartState();
}

final cartProvider = StateNotifierProvider.family<CartController, CartState, int>((ref, eventId) {
  return CartController();
});
