import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/menu_market/presentation/cart_state.dart';

void main() {
  test('cart retains an order intent until items, account, or event change', () {
    final cart = CartController();
    addTearDown(cart.dispose);
    cart.addOrIncrement(itemId: 1, barId: 8, name: 'Eau', ticketCost: 1);
    String key({String userId = 'a', int eventId = 4}) =>
        cart.orderIdempotencyKey(eventId: eventId, userId: userId);
    final original = key();
    expect(key(), original);
    cart.increment(1);
    expect(key(), isNot(original));
    final changed = key();
    expect(key(userId: 'b'), isNot(changed));
    final otherUser = key(userId: 'b');
    expect(key(userId: 'b', eventId: 5), isNot(otherUser));
  });

  test('a completed order receives a new key for identical future items', () {
    final cart = CartController();
    addTearDown(cart.dispose);
    cart.addOrIncrement(itemId: 1, barId: 8, name: 'Eau', ticketCost: 1);
    final first = cart.orderIdempotencyKey(eventId: 4, userId: 'a');
    cart.clear();
    cart.addOrIncrement(itemId: 1, barId: 8, name: 'Eau', ticketCost: 1);
    expect(cart.orderIdempotencyKey(eventId: 4, userId: 'a'), isNot(first));
  });
}
