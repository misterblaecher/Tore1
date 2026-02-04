class MarketDrink {
  final int drinkId;
  final String name;
  final String type;
  final int basePriceCents;
  final int effectivePriceCents;

  MarketDrink({
    required this.drinkId,
    required this.name,
    required this.type,
    required this.basePriceCents,
    required this.effectivePriceCents,
  });

  factory MarketDrink.fromJson(Map<String, dynamic> json) {
    return MarketDrink(
      drinkId: (json['drink_id'] as num).toInt(),
      name: (json['name'] ?? '').toString(),
      type: (json['type'] ?? '').toString(),
      basePriceCents: (json['base_price_cents'] as num).toInt(),
      effectivePriceCents: (json['effective_price_cents'] as num).toInt(),
    );
  }
}

class OrderItemIn {
  final int drinkId;
  final int qty;

  OrderItemIn({required this.drinkId, required this.qty});

  Map<String, dynamic> toJson() => {
        'drink_id': drinkId,
        'qty': qty,
      };
}
