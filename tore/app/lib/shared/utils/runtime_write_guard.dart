bool isWriteBlockedByEventState(String? state) {
  final normalized = (state ?? '').trim().toUpperCase();
  return normalized == 'PAUSE' ||
      normalized == 'PAUSED' ||
      normalized == 'MENU_ONLY' ||
      normalized == 'DEGRADED' ||
      normalized == 'READ_ONLY' ||
      normalized == 'FROZEN' ||
      normalized == 'CLOSED' ||
      normalized == 'ENDED';
}

String? eventWriteBlockedReason(String? state, {bool criticalOnly = true}) {
  final normalized = (state ?? '').trim().toUpperCase();
  if (normalized == 'PAUSE' || normalized == 'PAUSED') return 'Pause — commandes bloquées';
  if (normalized == 'MENU_ONLY') return 'Menu only — commandes bloquées';
  if (normalized == 'FROZEN') return 'FROZEN — aucune action';
  if (normalized == 'DEGRADED' && criticalOnly) return 'Réseau instable — actions sensibles bloquées';
  if (normalized == 'CLOSED' || normalized == 'ENDED') return 'Event terminé: cette action n’est plus disponible.';
  return null;
}

String? normalizeRuntimeBlockReason({String? state, String? reason}) {
  final normalizedReason = (reason ?? '').trim().toLowerCase();
  if (normalizedReason == 'event_paused' || normalizedReason == 'paused') return 'event_paused';
  if (normalizedReason == 'read_only') return 'read_only';
  if (normalizedReason == 'menu_only') return 'menu_only';
  if (normalizedReason == 'degraded') return 'degraded';
  if (normalizedReason == 'frozen') return 'frozen';
  if (normalizedReason == 'closed' || normalizedReason == 'event_closed' || normalizedReason == 'ended') return 'closed';

  final normalizedState = (state ?? '').trim().toUpperCase();
  if (normalizedState == 'PAUSE' || normalizedState == 'PAUSED') return 'event_paused';
  if (normalizedState == 'READ_ONLY') return 'read_only';
  if (normalizedState == 'MENU_ONLY') return 'menu_only';
  if (normalizedState == 'DEGRADED') return 'degraded';
  if (normalizedState == 'FROZEN') return 'frozen';
  if (normalizedState == 'CLOSED' || normalizedState == 'ENDED') return 'closed';
  return null;
}

String writeBlockedReasonMessage(String? state) {
  switch (normalizeRuntimeBlockReason(state: state)) {
    case 'event_paused':
      return 'Event en pause: les actions sont temporairement bloquées.';
    case 'read_only':
      return 'Event en lecture seule: impossible de valider pour le moment.';
    case 'menu_only':
      return 'Menu only: les commandes sont bloquées pour le moment.';
    case 'degraded':
      return 'Event dégradé: les actions sensibles sont temporairement bloquées.';
    case 'frozen':
      return 'Event gelé: les actions sont désactivées temporairement.';
    case 'closed':
      return 'Event fermé: cette action n’est plus disponible.';
    default:
      return 'Action indisponible pour le moment.';
  }
}
