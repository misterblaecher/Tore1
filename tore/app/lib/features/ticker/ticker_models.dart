class TickerItem {
  final String id;
  final String type;
  final DateTime ts;
  final String severity;
  final String? moduleKey;
  final TickerPayload payload;

  const TickerItem({
    required this.id,
    required this.type,
    required this.ts,
    required this.severity,
    required this.moduleKey,
    required this.payload,
  });

  static TickerItem fromJson(Map<String, dynamic> m) {
    final ts = DateTime.tryParse((m['ts'] ?? '').toString()) ?? DateTime.now();
    final type = (m['type'] ?? 'broadcast').toString();
    final payload =
        Map<String, dynamic>.from((m['payloadCompact'] as Map?) ?? const {});
    return TickerItem(
      id: (m['id'] ?? '').toString(),
      type: type,
      ts: ts,
      severity: (m['severity'] ?? 'info').toString(),
      moduleKey: m['moduleKey']?.toString(),
      payload: TickerPayload.from(type, payload),
    );
  }
}

sealed class TickerPayload {
  const TickerPayload();

  static TickerPayload from(String type, Map<String, dynamic> payload) {
    switch (type) {
      case 'gift':
        return GiftTickerPayload(
          amount: (payload['amount'] as num?)?.toInt() ?? 0,
          fromLabel: (payload['fromLabel'] ?? '').toString(),
          toLabel: (payload['toLabel'] ?? '').toString(),
        );
      case 'price':
        return PriceTickerPayload(
          drinkName: (payload['drinkName'] ?? '').toString(),
          fromPrice: (payload['fromPrice'] as num?)?.toInt() ?? 0,
          toPrice: (payload['toPrice'] as num?)?.toInt() ?? 0,
          direction: (payload['direction'] ?? '').toString(),
        );
      case 'order':
        return OrderTickerPayload(
          kind: (payload['kind'] ?? '').toString(),
          orderId: (payload['orderId'] ?? '').toString(),
          status: (payload['status'] ?? '').toString(),
          totalTickets: (payload['totalTickets'] as num?)?.toInt() ?? 0,
          userLabel: payload['userLabel']?.toString(),
        );
      case 'broadcast':
      default:
        return BroadcastTickerPayload(
          message: (payload['message'] ?? '').toString(),
          level: (payload['level'] ?? 'info').toString(),
        );
    }
  }
}

class BroadcastTickerPayload extends TickerPayload {
  final String message;
  final String level;
  const BroadcastTickerPayload({required this.message, required this.level});
}

class OrderTickerPayload extends TickerPayload {
  final String kind;
  final String orderId;
  final String status;
  final int totalTickets;
  final String? userLabel;
  const OrderTickerPayload(
      {required this.kind,
      required this.orderId,
      required this.status,
      required this.totalTickets,
      this.userLabel});
}

class PriceTickerPayload extends TickerPayload {
  final String drinkName;
  final int fromPrice;
  final int toPrice;
  final String direction;
  const PriceTickerPayload(
      {required this.drinkName,
      required this.fromPrice,
      required this.toPrice,
      required this.direction});
}

class GiftTickerPayload extends TickerPayload {
  final int amount;
  final String fromLabel;
  final String toLabel;
  const GiftTickerPayload(
      {required this.amount, required this.fromLabel, required this.toLabel});
}

class TickerPage {
  final List<TickerItem> items;
  final String? nextCursor;

  const TickerPage({required this.items, required this.nextCursor});
}
