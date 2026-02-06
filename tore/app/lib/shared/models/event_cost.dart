class EventCost {
  final int id;
  final int? eventId;
  final String label;
  final int amountCents;
  final String category;
  final String? createdAt;
  final String? createdByUserId;

  const EventCost({
    required this.id,
    required this.eventId,
    required this.label,
    required this.amountCents,
    required this.category,
    required this.createdAt,
    required this.createdByUserId,
  });

  factory EventCost.fromJson(Map<String, dynamic> json) {
    return EventCost(
      id: (json['id'] as num?)?.toInt() ?? 0,
      eventId: (json['event_id'] as num?)?.toInt(),
      label: json['label']?.toString() ?? '',
      amountCents: (json['amount_cents'] as num?)?.toInt() ?? 0,
      category: json['category']?.toString() ?? 'other',
      createdAt: json['created_at']?.toString(),
      createdByUserId: json['created_by_user_id']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    final payload = <String, dynamic>{
      'id': id,
      'label': label,
      'amount_cents': amountCents,
      'category': category,
      'created_at': createdAt,
      'created_by_user_id': createdByUserId,
    };
    if (eventId != null) {
      payload['event_id'] = eventId;
    }
    return payload;
  }
}
