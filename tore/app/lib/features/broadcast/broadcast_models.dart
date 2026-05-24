class BroadcastItem {
  const BroadcastItem({
    required this.id,
    required this.message,
    required this.level,
    required this.createdAt,
  });

  final int id;
  final String message;
  final String level;
  final DateTime createdAt;

  factory BroadcastItem.fromJson(Map<String, dynamic> json) {
    return BroadcastItem(
      id: (json['id'] as num?)?.toInt() ?? 0,
      message: (json['message'] ?? '').toString(),
      level: (json['level'] ?? 'info').toString(),
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ??
          DateTime.now(),
    );
  }
}
