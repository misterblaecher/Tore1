enum BarEventStatus { live, today, upcoming, ended }

class EventSummary {
  const EventSummary({
    required this.id,
    required this.barId,
    required this.name,
    required this.startAt,
    required this.endAt,
    required this.status,
    this.venue,
    this.shortName,
    this.eventState,
    this.modulesOn,
  });

  final int id;
  final int? barId;
  final String name;
  final DateTime startAt;
  final DateTime endAt;
  final BarEventStatus status;
  final String? venue;
  final String? shortName;
  final String? eventState;
  final Map<String, bool>? modulesOn;

  factory EventSummary.fromJson(Map<String, dynamic> json) {
    final startRaw = json['startAt'] ?? json['starts_at'] ?? json['startsAt'];
    final endRaw = json['endAt'] ?? json['ends_at'] ?? json['endsAt'];
    final startAt =
        _parseDateTime(startRaw) ?? DateTime.fromMillisecondsSinceEpoch(0);
    final endAt = _parseDateTime(endRaw) ?? startAt;

    final statusRaw = (json['status'] ?? '').toString().toUpperCase();
    final computedStatus = _statusFromClock(startAt: startAt, endAt: endAt);

    return EventSummary(
      id: (json['id'] as num?)?.toInt() ?? 0,
      barId: (json['bar_id'] as num?)?.toInt(),
      name: (json['name'] ?? '').toString(),
      startAt: startAt,
      endAt: endAt,
      status: _statusFromString(statusRaw) ?? computedStatus,
      venue: _optionalText(json['venue']),
      shortName: _optionalText(json['shortName'] ?? json['short_name']),
      eventState: _optionalText(json['eventState'] ?? json['event_state']),
      modulesOn: _readModulesOn(json['modulesOn'] ?? json['modules_on']),
    );
  }

  bool get isLive => status == BarEventStatus.live;

  bool isToday({DateTime? now}) {
    final localNow = now ?? DateTime.now();
    return startAt.year == localNow.year &&
        startAt.month == localNow.month &&
        startAt.day == localNow.day;
  }

  static DateTime? _parseDateTime(dynamic raw) {
    if (raw == null) return null;
    return DateTime.tryParse(raw.toString())?.toLocal();
  }

  static String? _optionalText(dynamic value) {
    final text = value?.toString() ?? '';
    return text.trim().isEmpty ? null : text;
  }

  static Map<String, bool>? _readModulesOn(dynamic value) {
    if (value is! Map) return null;
    return value.map((key, item) => MapEntry(key.toString(), item == true));
  }

  static BarEventStatus? _statusFromString(String value) {
    switch (value) {
      case 'LIVE':
        return BarEventStatus.live;
      case 'UPCOMING':
        return BarEventStatus.upcoming;
      case 'ENDED':
        return BarEventStatus.ended;
      default:
        return null;
    }
  }

  static BarEventStatus _statusFromClock(
      {required DateTime startAt, required DateTime endAt}) {
    final now = DateTime.now();
    if (!startAt.isAfter(now) && !endAt.isBefore(now)) {
      return BarEventStatus.live;
    }
    if (startAt.isAfter(now)) {
      return BarEventStatus.upcoming;
    }
    return BarEventStatus.ended;
  }
}
