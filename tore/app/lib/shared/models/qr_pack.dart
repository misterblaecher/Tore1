class QrPack {
  final int eventId;
  final Map<String, String> qrs;

  const QrPack({
    required this.eventId,
    required this.qrs,
  });

  factory QrPack.fromJson(Map<String, dynamic> json) {
    final rawQrs = Map<String, dynamic>.from(json['qrs'] as Map? ?? {});
    return QrPack(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      qrs: rawQrs.map((key, value) => MapEntry(key, value.toString())),
    );
  }
}
