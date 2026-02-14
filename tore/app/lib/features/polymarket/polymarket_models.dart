class CursorPage<T> {
  final List<T> items;
  final String? nextCursor;

  const CursorPage({required this.items, required this.nextCursor});
}

class MarketLite {
  final int id;
  final String question;
  final String status;
  final String scope;
  final double yesPrice;
  final double noPrice;
  final int volume;
  final int myPositionYes;
  final int myPositionNo;
  final int myPositionTotal;
  final int? eventId;

  const MarketLite({
    required this.id,
    required this.question,
    required this.status,
    required this.scope,
    required this.yesPrice,
    required this.noPrice,
    required this.volume,
    required this.myPositionYes,
    required this.myPositionNo,
    required this.myPositionTotal,
    required this.eventId,
  });

  factory MarketLite.fromJson(Map<String, dynamic> json) {
    int _i(dynamic v) => (v as num?)?.toInt() ?? 0;
    double _d(dynamic v) => (v as num?)?.toDouble() ?? 0;
    return MarketLite(
      id: _i(json['id']),
      question: json['question']?.toString() ?? '',
      status: json['status']?.toString() ?? 'live',
      scope: json['scope']?.toString() ?? 'global',
      yesPrice: _d(json['yes_price']),
      noPrice: _d(json['no_price']),
      volume: _i(json['volume']),
      myPositionYes: _i(json['my_position_yes']),
      myPositionNo: _i(json['my_position_no']),
      myPositionTotal: _i(json['my_total']),
      eventId: (json['event_id'] as num?)?.toInt(),
    );
  }
}

class MarketDetail extends MarketLite {
  final String? outcome;

  const MarketDetail({
    required super.id,
    required super.question,
    required super.status,
    required super.scope,
    required super.yesPrice,
    required super.noPrice,
    required super.volume,
    required super.myPositionYes,
    required super.myPositionNo,
    required super.myPositionTotal,
    required super.eventId,
    required this.outcome,
  });

  factory MarketDetail.fromJson(Map<String, dynamic> json) {
    final lite = MarketLite.fromJson(json);
    return MarketDetail(
      id: lite.id,
      question: lite.question,
      status: lite.status,
      scope: lite.scope,
      yesPrice: lite.yesPrice,
      noPrice: lite.noPrice,
      volume: lite.volume,
      myPositionYes: lite.myPositionYes,
      myPositionNo: lite.myPositionNo,
      myPositionTotal: lite.myPositionTotal,
      eventId: lite.eventId,
      outcome: json['resolved_outcome']?.toString(),
    );
  }
}

class PositionRow {
  final int marketId;
  final String question;
  final int yesTotal;
  final int noTotal;
  final int total;
  final String status;
  final String? outcome;
  final double? pnl;

  const PositionRow({
    required this.marketId,
    required this.question,
    required this.yesTotal,
    required this.noTotal,
    required this.total,
    required this.status,
    required this.outcome,
    required this.pnl,
  });

  factory PositionRow.fromJson(Map<String, dynamic> json) {
    final sideTotals = (json['side_totals'] is Map)
        ? Map<String, dynamic>.from(json['side_totals'] as Map)
        : <String, dynamic>{};
    final yes = (sideTotals['yes'] as num?)?.toInt() ?? 0;
    final no = (sideTotals['no'] as num?)?.toInt() ?? 0;
    return PositionRow(
      marketId: (json['market_id'] as num?)?.toInt() ?? 0,
      question: json['question']?.toString() ?? '',
      yesTotal: yes,
      noTotal: no,
      total: yes + no,
      status: json['status']?.toString() ?? 'live',
      outcome: json['resolved_outcome']?.toString(),
      pnl: (json['pnl'] as num?)?.toDouble(),
    );
  }
}

class TradeRow {
  final String? rawId;
  final int? marketId;
  final String? kind;
  final String? outcome;
  final String side;
  final int amount;
  final DateTime ts;
  final String status;

  const TradeRow({
    required this.rawId,
    required this.marketId,
    required this.kind,
    required this.outcome,
    required this.side,
    required this.amount,
    required this.ts,
    required this.status,
  });

  String get id {
    if (rawId != null && rawId!.isNotEmpty) return rawId!;
    final normalizedSide = side.isNotEmpty ? side : (outcome ?? 'unknown');
    return '${marketId ?? 0}|${ts.toUtc().toIso8601String()}|${kind ?? 'trade'}|$normalizedSide|$amount';
  }

  factory TradeRow.fromJson(Map<String, dynamic> json) {
    final rawTs = json['created_at']?.toString();
    return TradeRow(
      rawId: json['id']?.toString(),
      marketId: (json['market_id'] as num?)?.toInt(),
      kind: json['kind']?.toString() ?? json['type']?.toString(),
      outcome: json['outcome']?.toString(),
      side: json['side']?.toString() ?? 'yes',
      amount: (json['amount_cents'] as num?)?.toInt() ?? 0,
      ts: DateTime.tryParse(rawTs ?? '') ?? DateTime.now(),
      status: json['status']?.toString() ?? 'filled',
    );
  }
}

class MarketDetailResponse {
  final MarketDetail market;
  final List<TradeRow> myHistory;
  final String? nextCursor;

  const MarketDetailResponse({required this.market, required this.myHistory, required this.nextCursor});

  factory MarketDetailResponse.fromJson(Map<String, dynamic> json) {
    final marketJson = (json['market'] is Map)
        ? Map<String, dynamic>.from(json['market'] as Map)
        : <String, dynamic>{};
    final history = ((json['my_history'] as List?) ?? const [])
        .map((e) => TradeRow.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return MarketDetailResponse(
      market: MarketDetail.fromJson(marketJson),
      myHistory: history,
      nextCursor: json['next_cursor']?.toString(),
    );
  }
}
