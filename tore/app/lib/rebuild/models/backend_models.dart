class PagedResult<T> {
  const PagedResult({required this.items, this.nextCursor});

  final List<T> items;
  final String? nextCursor;
}

class MobileBootstrapDto {
  const MobileBootstrapDto({
    required this.eventKey,
    required this.eventApiId,
    this.barId,
    this.barName,
    this.eventName,
    this.source,
  });

  final String eventKey;
  final String eventApiId;
  final String? barId;
  final String? barName;
  final String? eventName;
  final String? source;

  static const fallback =
      MobileBootstrapDto(eventKey: 'event_42', eventApiId: '42', barId: '1');

  factory MobileBootstrapDto.fromJson(Map<String, dynamic> json) {
    final rawEventKey = (json['eventId'] ?? json['event_id'] ?? '').toString();
    final eventKey = _normalizeEventKey(rawEventKey);
    final rawApiId = (json['eventApiId'] ??
            json['event_api_id'] ??
            json['event_id'] ??
            _stripEventPrefix(eventKey))
        .toString();
    final eventApiId = _nonEmpty(rawApiId) ?? _stripEventPrefix(eventKey);
    return MobileBootstrapDto(
      eventKey: eventKey,
      eventApiId: eventApiId,
      barId: _nonEmpty((json['barId'] ?? json['bar_id'])?.toString()),
      barName: _nonEmpty((json['barName'] ?? json['bar_name'])?.toString()),
      eventName:
          _nonEmpty((json['eventName'] ?? json['event_name'])?.toString()),
      source: _nonEmpty(json['source']?.toString()),
    );
  }
}

String _normalizeEventKey(String raw) {
  final value = raw.trim();
  if (value.isEmpty || value == 'null') return 'event_42';
  return value.startsWith('event_') ? value : 'event_$value';
}

String _stripEventPrefix(String raw) =>
    raw.trim().replaceFirst(RegExp(r'^event_'), '');

String? _nonEmpty(String? raw) {
  final value = raw?.trim() ?? '';
  if (value.isEmpty || value == 'null') return null;
  return value;
}

class BarDto {
  const BarDto({required this.id, required this.name, this.city});

  final String id;
  final String name;
  final String? city;

  factory BarDto.fromJson(Map<String, dynamic> json) => BarDto(
        id: (json['id'] ?? json['bar_id'] ?? '').toString(),
        name: (json['name'] ?? json['title'] ?? 'Bar').toString(),
        city: json['city']?.toString(),
      );
}

class EventDto {
  const EventDto({required this.id, required this.title, this.state});

  final String id;
  final String title;
  final String? state;

  factory EventDto.fromJson(Map<String, dynamic> json) => EventDto(
        id: (json['id'] ?? json['event_id'] ?? '').toString(),
        title: (json['title'] ?? json['name'] ?? 'Event').toString(),
        state: json['state']?.toString(),
      );
}

class MenuItemDto {
  const MenuItemDto(
      {required this.id, required this.name, required this.price});

  final String id;
  final String name;
  final double price;

  factory MenuItemDto.fromJson(Map<String, dynamic> json) => MenuItemDto(
        id: (json['id'] ?? '').toString(),
        name: (json['name'] ?? json['label'] ?? 'Item').toString(),
        price: (json['price'] as num?)?.toDouble() ??
            (json['price_cents'] as num?)?.toDouble() ??
            0,
      );
}

class WalletDto {
  const WalletDto({required this.balance, required this.timeline});

  final double balance;
  final List<WalletTxDto> timeline;

  factory WalletDto.fromJson(Map<String, dynamic> json) {
    final entries = (json['entries'] ??
        json['rows'] ??
        json['items'] ??
        <dynamic>[]) as List<dynamic>;
    return WalletDto(
      balance: (json['balance'] as num?)?.toDouble() ?? 0,
      timeline: entries
          .whereType<Map<String, dynamic>>()
          .map(WalletTxDto.fromJson)
          .toList(),
    );
  }
}

class WalletTxDto {
  const WalletTxDto(
      {required this.id, required this.type, required this.delta});

  final String id;
  final String type;
  final double delta;

  factory WalletTxDto.fromJson(Map<String, dynamic> json) => WalletTxDto(
        id: (json['id'] ?? json['tx_id'] ?? '').toString(),
        type: (json['type'] ?? '').toString(),
        delta: (json['delta'] as num?)?.toDouble() ?? 0,
      );
}

class TickerItemDto {
  const TickerItemDto({required this.id, required this.message, this.ts});

  final String id;
  final String message;
  final String? ts;

  factory TickerItemDto.fromJson(Map<String, dynamic> json) => TickerItemDto(
        id: (json['id'] ?? '').toString(),
        message: (json['message'] ?? json['title'] ?? '').toString(),
        ts: json['ts']?.toString(),
      );
}

class PolymarketDto {
  const PolymarketDto({required this.id, required this.title});

  final String id;
  final String title;

  factory PolymarketDto.fromJson(Map<String, dynamic> json) => PolymarketDto(
      id: (json['id'] ?? '').toString(),
      title: (json['title'] ?? json['question'] ?? '').toString());
}

class EntryStatsDto {
  const EntryStatsDto({required this.approvedCount, required this.deniedCount});

  final int approvedCount;
  final int deniedCount;

  factory EntryStatsDto.fromJson(Map<String, dynamic> json) => EntryStatsDto(
        approvedCount: (json['approved_count'] as num?)?.toInt() ??
            (json['approved'] as num?)?.toInt() ??
            0,
        deniedCount: (json['denied_count'] as num?)?.toInt() ??
            (json['denied'] as num?)?.toInt() ??
            0,
      );
}

class OrderDto {
  const OrderDto({required this.id, required this.status});

  final String id;
  final String status;

  factory OrderDto.fromJson(Map<String, dynamic> json) => OrderDto(
      id: (json['id'] ?? '').toString(),
      status: (json['status'] ?? 'NEW').toString());
}

class ZoneDto {
  const ZoneDto({required this.id, required this.name, required this.enabled});

  final String id;
  final String name;
  final bool enabled;

  factory ZoneDto.fromJson(Map<String, dynamic> json) => ZoneDto(
        id: (json['id'] ?? '').toString(),
        name: (json['name'] ?? '').toString(),
        enabled: json['enabled'] == true,
      );
}
