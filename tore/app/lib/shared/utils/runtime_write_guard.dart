bool isWriteBlockedByEventState(String? state) {
  final normalized = (state ?? '').trim().toUpperCase();
  return normalized == 'PAUSE' ||
      normalized == 'PAUSED' ||
      normalized == 'READ_ONLY' ||
      normalized == 'FROZEN' ||
      normalized == 'CLOSED';
}

String? normalizeRuntimeBlockReason({String? state, String? reason}) {
  final normalizedReason = (reason ?? '').trim().toLowerCase();
  if (normalizedReason == 'event_paused' || normalizedReason == 'paused') return 'event_paused';
  if (normalizedReason == 'read_only') return 'read_only';
  if (normalizedReason == 'frozen') return 'frozen';
  if (normalizedReason == 'closed' || normalizedReason == 'event_closed') return 'closed';

  final normalizedState = (state ?? '').trim().toUpperCase();
  if (normalizedState == 'PAUSE' || normalizedState == 'PAUSED') return 'event_paused';
  if (normalizedState == 'READ_ONLY') return 'read_only';
  if (normalizedState == 'FROZEN') return 'frozen';
  if (normalizedState == 'CLOSED') return 'closed';
  return null;
}

String writeBlockedReasonMessage(String? state) {
  switch (normalizeRuntimeBlockReason(state: state)) {
    case 'event_paused':
      return 'Event en pause: les actions sont temporairement bloquées.';
    case 'read_only':
      return 'Event en lecture seule: impossible de valider pour le moment.';
    case 'frozen':
      return 'Event gelé: les actions sont désactivées temporairement.';
    case 'closed':
      return 'Event fermé: cette action n’est plus disponible.';
    default:
      return 'Action indisponible pour le moment.';
  }
}
