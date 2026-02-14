class TickerItem {
  final String id;
  final String type;
  final DateTime ts;
  final String title;
  final String body;
  final String severity;
  final String? refKind;
  final String? refId;

  const TickerItem({
    required this.id,
    required this.type,
    required this.ts,
    required this.title,
    required this.body,
    required this.severity,
    required this.refKind,
    required this.refId,
  });

  static TickerItem fromJson(Map<String, dynamic> m) {
    final tRaw = m['ts'];
    final ts = tRaw is String ? (DateTime.tryParse(tRaw) ?? DateTime.now()) : DateTime.now();
    return TickerItem(
      id: (m['id'] ?? '').toString(),
      type: (m['type'] ?? 'event').toString(),
      ts: ts,
      title: (m['title'] ?? '').toString(),
      body: (m['body'] ?? '').toString(),
      severity: (m['severity'] ?? 'info').toString(),
      refKind: m['ref_kind']?.toString(),
      refId: m['ref_id']?.toString(),
    );
  }
}

class TickerPage {
  final List<TickerItem> items;
  final String? nextCursor;

  const TickerPage({required this.items, required this.nextCursor});
}
