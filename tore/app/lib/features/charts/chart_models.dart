class MenuDrinkMeta {
  final int drinkId;
  final String name;
  final String type;
  final int basePriceCents;
  final int effectivePriceCents;

  const MenuDrinkMeta({
    required this.drinkId,
    required this.name,
    required this.type,
    required this.basePriceCents,
    required this.effectivePriceCents,
  });

  double get effectivePriceEuro => effectivePriceCents / 100.0;
  double get basePriceEuro => basePriceCents / 100.0;

  double get changePct {
    if (basePriceCents == 0) return 0;
    return ((effectivePriceCents - basePriceCents) / basePriceCents) * 100.0;
  }

  static MenuDrinkMeta fromMenuRow(Map<String, dynamic> d) {
    final drinkId = (d['drink_id'] as int?) ?? 0;
    final name = (d['name'] ?? '').toString();
    final type = (d['type'] ?? '').toString();
    final base = (d['base_price_cents'] as int?) ?? 0;
    final eff = (d['effective_price_cents'] as int?) ?? base;
    return MenuDrinkMeta(
      drinkId: drinkId,
      name: name.isEmpty ? '(Sans nom)' : name,
      type: type,
      basePriceCents: base,
      effectivePriceCents: eff,
    );
  }
}

class PricePoint {
  final DateTime ts;
  final int priceCents;

  const PricePoint({required this.ts, required this.priceCents});

  double get priceEuro => priceCents / 100.0;

  /// Attempts to parse a wide range of possible backend shapes.
  static PricePoint? tryParse(dynamic row) {
    if (row == null) return null;
    if (row is num) {
      return PricePoint(ts: DateTime.now(), priceCents: row.toInt());
    }
    if (row is Map) {
      final m = Map<String, dynamic>.from(row);
      // timestamp variants
      final tRaw = m['ts'] ?? m['t'] ?? m['timestamp'] ?? m['time'];
      DateTime ts = DateTime.now();
      if (tRaw is String) {
        ts = DateTime.tryParse(tRaw) ?? DateTime.now();
      } else if (tRaw is int) {
        // assume unix seconds or ms
        ts = tRaw > 2000000000
            ? DateTime.fromMillisecondsSinceEpoch(tRaw)
            : DateTime.fromMillisecondsSinceEpoch(tRaw * 1000);
      } else if (tRaw is double) {
        final v = tRaw.toInt();
        ts = v > 2000000000
            ? DateTime.fromMillisecondsSinceEpoch(v)
            : DateTime.fromMillisecondsSinceEpoch(v * 1000);
      }

      // price variants: point or OHLC
      final pRaw = m['price_cents'] ??
          m['price'] ??
          m['cents'] ??
          m['close_cents'] ??
          m['c'] ??
          m['close'];

      if (pRaw is num) {
        return PricePoint(ts: ts, priceCents: pRaw.toInt());
      }
      if (pRaw is String) {
        final asNum = num.tryParse(pRaw);
        if (asNum != null) {
          return PricePoint(ts: ts, priceCents: asNum.toInt());
        }
      }
    }
    return null;
  }
}

class WalletHistoryEntry {
  final String id;
  final DateTime ts;
  final String type;
  final int delta;
  final int? balanceAfter;
  final String? note;
  final String? orderId;

  const WalletHistoryEntry({
    required this.id,
    required this.ts,
    required this.type,
    required this.delta,
    this.balanceAfter,
    this.note,
    this.orderId,
  });

  static WalletHistoryEntry fromJson(Map<String, dynamic> m) {
    final id = (m['id'] ?? m['uuid'] ?? m['tx_id'] ?? '').toString();
    final tRaw = m['ts'] ?? m['timestamp'] ?? m['time'];
    DateTime ts = DateTime.now();
    if (tRaw is String) ts = DateTime.tryParse(tRaw) ?? DateTime.now();
    if (tRaw is int) {
      ts = tRaw > 2000000000
          ? DateTime.fromMillisecondsSinceEpoch(tRaw)
          : DateTime.fromMillisecondsSinceEpoch(tRaw * 1000);
    }
    final type = (m['type'] ?? m['kind'] ?? 'unknown').toString();
    final deltaRaw = m['delta'] ?? m['amount'] ?? m['change'] ?? 0;
    final delta = (deltaRaw is num) ? deltaRaw.toInt() : int.tryParse(deltaRaw.toString()) ?? 0;
    final balRaw = m['balance_after'] ?? m['balance'] ?? m['after'];
    final balanceAfter = (balRaw is num) ? balRaw.toInt() : (balRaw == null ? null : int.tryParse(balRaw.toString()));
    final note = m['note']?.toString() ?? m['message']?.toString();
    final orderId = m['order_id']?.toString();
    return WalletHistoryEntry(
      id: id,
      ts: ts,
      type: type,
      delta: delta,
      balanceAfter: balanceAfter,
      note: note,
      orderId: orderId,
    );
  }
}

class TickerItem {
  final String type;
  final DateTime ts;
  final String title;
  final String? subtitle;
  final Map<String, dynamic> payload;

  const TickerItem({
    required this.type,
    required this.ts,
    required this.title,
    this.subtitle,
    required this.payload,
  });

  static TickerItem fromJson(Map<String, dynamic> m) {
    final type = (m['type'] ?? m['kind'] ?? 'event').toString();
    final tRaw = m['ts'] ?? m['timestamp'] ?? m['time'];
    DateTime ts = DateTime.now();
    if (tRaw is String) ts = DateTime.tryParse(tRaw) ?? DateTime.now();
    if (tRaw is int) {
      ts = tRaw > 2000000000
          ? DateTime.fromMillisecondsSinceEpoch(tRaw)
          : DateTime.fromMillisecondsSinceEpoch(tRaw * 1000);
    }

    String title = (m['title'] ?? m['message'] ?? type).toString();
    String? subtitle = m['subtitle']?.toString();

    final payload = (m['payload'] is Map)
        ? Map<String, dynamic>.from(m['payload'] as Map)
        : Map<String, dynamic>.from(m);

    // Best-effort titles for common shapes
    if (title == type) {
      if (type == 'order') {
        final drink = payload['drink_name'] ?? payload['name'] ?? 'Commande';
        final qty = payload['qty'] ?? payload['quantity'];
        title = qty != null ? 'Commande ×$qty — $drink' : 'Commande — $drink';
      } else if (type == 'move' || type == 'price_move') {
        final drink = payload['drink_name'] ?? payload['name'] ?? 'Boisson';
        final pct = payload['pct'] ?? payload['change_pct'] ?? payload['change'];
        title = pct != null ? '$drink ${pct.toString()}%' : 'Variation — $drink';
      } else if (type == 'leaderboard') {
        title = 'Classement mis à jour';
      } else if (type == 'checkin') {
        final drink = payload['drink_name'] ?? payload['name'] ?? 'Check-in';
        title = 'Check-in — $drink';
      }
    }
    return TickerItem(type: type, ts: ts, title: title, subtitle: subtitle, payload: payload);
  }
}
