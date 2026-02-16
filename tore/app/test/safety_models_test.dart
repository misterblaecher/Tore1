import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/safety/safety_models.dart';

void main() {
  test('parses safety state payload', () {
    final model = SafetyState.fromJson({
      'enabled': true,
      'orgaPhone': '+32470000000',
      'messageHint': 'Reste avec ton buddy',
      'myBuddy': {'userId': 'u-buddy', 'displayNameMasked': 'B***'},
      'myLastCheckin': {'type': 'OK', 'createdAt': '2026-01-01T10:00:00Z'},
      'buddyLastCheckin': {'type': 'PANIC', 'createdAt': '2026-01-01T10:05:00Z'},
    });

    expect(model.enabled, isTrue);
    expect(model.orgaPhone, '+32470000000');
    expect(model.myBuddy?.id, 'u-buddy');
    expect(model.myLastCheckin?.type, 'OK');
    expect(model.buddyLastCheckin?.type, 'PANIC');
  });

  test('parses safety history payload', () {
    final response = SafetyHistoryResponse.fromJson({
      'items': [
        {'id': 1, 'type': 'OK', 'createdAt': '2026-01-01T10:00:00Z'},
        {'id': 2, 'type': 'PANIC', 'createdAt': '2026-01-01T10:05:00Z'},
      ],
      'buddyLastCheckin': {'userId': 'u-buddy', 'type': 'OK', 'createdAt': '2026-01-01T10:07:00Z'},
    });

    expect(response.items.length, 2);
    expect(response.items.first.type, 'OK');
    expect(response.buddyLastCheckin?.type, 'OK');
  });
}
