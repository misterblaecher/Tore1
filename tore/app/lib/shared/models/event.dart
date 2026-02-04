class Event {
  final int id;
  final String name;
  final String startsAt;

  const Event({
    required this.id,
    required this.name,
    required this.startsAt,
  });

  factory Event.fromJson(Map<String, dynamic> json) {
    return Event(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startsAt: (json['starts_at'] ?? json['startsAt'] ?? '').toString(),
    );
  }
}
