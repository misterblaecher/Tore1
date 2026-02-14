import 'package:flutter_riverpod/flutter_riverpod.dart';

enum TickerFilter { all, prices, orders, events, alerts }

final tickerFilterProvider = StateProvider.family<TickerFilter, int>((ref, eventId) => TickerFilter.all);

extension TickerFilterLabel on TickerFilter {
  String get label {
    switch (this) {
      case TickerFilter.all:
        return 'Tous';
      case TickerFilter.prices:
        return 'Prices';
      case TickerFilter.orders:
        return 'Orders';
      case TickerFilter.events:
        return 'Events';
      case TickerFilter.alerts:
        return 'Alerts';
    }
  }
}
