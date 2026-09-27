import 'package:flutter_test/flutter_test.dart';
import 'package:tore/shared/models/event_config.dart';

void main() {
  test('ticker ON alone is available', () {
    final config = EventConfig.fromJson({
      'event_id': 1,
      'ticker_enabled': true,
      'menu_enabled': false,
      'wallet_enabled': false,
      'polymarket_enabled': false,
    });

    expect(config.tickerEnabled, isTrue);
  });

  test('ticker OFF stays unavailable when other modules are ON', () {
    final config = EventConfig.fromJson({
      'event_id': 1,
      'ticker_enabled': false,
      'menu_enabled': true,
      'wallet_enabled': true,
      'polymarket_enabled': true,
    });

    expect(config.tickerEnabled, isFalse);
  });

  test('other modules do not imply ticker availability', () {
    final config = EventConfig.fromJson({
      'event_id': 1,
      'ticker_enabled': false,
      'menu_enabled': true,
      'wallet_enabled': false,
      'polymarket_enabled': false,
    });

    expect(config.tickerEnabled, isFalse);
  });
}
