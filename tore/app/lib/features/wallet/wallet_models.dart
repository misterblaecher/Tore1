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
    final delta = (deltaRaw is num)
        ? deltaRaw.toInt()
        : int.tryParse(deltaRaw.toString()) ?? 0;
    final balRaw = m['balance_after'] ?? m['balance'] ?? m['after'];
    final balanceAfter = (balRaw is num)
        ? balRaw.toInt()
        : (balRaw == null ? null : int.tryParse(balRaw.toString()));
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
