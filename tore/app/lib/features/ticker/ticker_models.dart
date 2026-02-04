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
