class CreatedEvent {
  final int eventId;
  final String name;
  final String startsAt;
  final String endsAt;
  final int? barId;

  const CreatedEvent({
    required this.eventId,
    required this.name,
    required this.startsAt,
    required this.endsAt,
    required this.barId,
  });

  factory CreatedEvent.fromJson(Map<String, dynamic> json) {
    return CreatedEvent(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startsAt: (json['starts_at'] ?? '').toString(),
      endsAt: (json['ends_at'] ?? '').toString(),
      barId: (json['bar_id'] as num?)?.toInt(),
    );
  }
}
