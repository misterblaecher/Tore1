bool isWriteBlockedByEventState(String? state) {
  final normalized = (state ?? '').trim().toUpperCase();
  return normalized == 'PAUSE' ||
      normalized == 'PAUSED' ||
      normalized == 'READ_ONLY' ||
      normalized == 'FROZEN' ||
      normalized == 'CLOSED';
}

String writeBlockedReasonMessage(String? state) {
  switch ((state ?? '').trim().toUpperCase()) {
    case 'PAUSE':
    case 'PAUSED':
      return 'Event en pause: les actions sont temporairement bloquées.';
    case 'READ_ONLY':
      return 'Event en lecture seule: impossible de valider pour le moment.';
    case 'FROZEN':
      return 'Event gelé: les actions sont désactivées temporairement.';
    case 'CLOSED':
      return 'Event fermé: cette action n’est plus disponible.';
    default:
      return 'Action indisponible pour le moment.';
  }
}

