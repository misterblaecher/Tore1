import 'rebuild_types.dart';
import 'safe_parsing.dart';

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
        eventId: safeGetString(map, 'eventId', fallback: 'event_unknown', aliases: const ['event_id']),
        eventState: mapBackendStateAlias(safeGetString(map, 'eventState', fallback: 'DRAFT', aliases: const ['event_state'])),
        moduleStates: safeGetMap(map, 'moduleStates', aliases: const ['module_states']).map(
          (k, v) => MapEntry(k, _moduleStateFrom(v)),
        ),
        syncedAt: tryParseDateTime(map['syncedAt'], fallback: DateTime.now()),
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

ModuleState _moduleStateFrom(Object? value) {
  final name = value?.toString() ?? '';
  for (final state in ModuleState.values) {
    if (state.name == name) return state;
  }
  return ModuleState.off;
}
