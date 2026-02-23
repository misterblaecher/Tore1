import 'rebuild_types.dart';

class EventContext {
  const EventContext({
    required this.eventId,
    required this.eventState,
    required this.moduleStates,
    required this.syncedAt,
  });

  final String eventId;
  final EventState eventState;
  final Map<String, ModuleState> moduleStates;
  final DateTime syncedAt;

  Map<String, dynamic> toJson() => {
        'eventId': eventId,
        'eventState': eventState.name,
        'moduleStates': moduleStates.map((k, v) => MapEntry(k, v.name)),
        'syncedAt': syncedAt.toIso8601String(),
      };

  static EventContext fromJson(Map<String, dynamic> map) => EventContext(
        eventId: map['eventId'] as String,
        eventState: EventState.values.byName(map['eventState'] as String),
        moduleStates: (map['moduleStates'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ModuleState.values.byName(v as String)),
        ),
        syncedAt: DateTime.parse(map['syncedAt'] as String),
      );
}

EventState mapBackendStateAlias(String raw) {
  switch (raw.toUpperCase()) {
    case 'RUNNING':
    case 'LIVE':
      return EventState.live;
    case 'PAUSE':
    case 'PAUSED':
      return EventState.paused;
    case 'CLOSED':
    case 'ENDED':
      return EventState.ended;
    case 'READ_ONLY':
    case 'FROZEN':
      return EventState.readOnly;
    default:
      return EventState.draft;
  }
}
