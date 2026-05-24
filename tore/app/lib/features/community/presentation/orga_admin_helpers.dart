String joinModeLabel(String raw) {
  switch (raw.toUpperCase()) {
    case 'FOLLOW_ONLY':
      return 'Suivi uniquement';
    case 'REQUEST_TO_JOIN':
      return 'Demande de rejoindre';
    default:
      return 'Adhésion ouverte';
  }
}

Map<String, dynamic> buildOrgaSettingsPayload({
  required Map<String, dynamic> initial,
  required String name,
  required String city,
  required String instagram,
  required String description,
  required String visibility,
  required String joinMode,
}) {
  final out = <String, dynamic>{};
  if (name.trim() != (initial['name'] ?? '').toString().trim())
    out['name'] = name.trim();
  if (city.trim() != (initial['city'] ?? '').toString().trim())
    out['city'] = city.trim();
  if (instagram.trim() != (initial['instagram_handle'] ?? '').toString().trim())
    out['instagram'] = instagram.trim();
  if (description.trim() != (initial['description'] ?? '').toString().trim())
    out['description'] = description.trim();
  if (visibility.toUpperCase() !=
      (initial['visibility'] ?? 'PUBLIC').toString().toUpperCase())
    out['visibility'] = visibility.toUpperCase();
  if (joinMode.toUpperCase() !=
      (initial['join_mode'] ?? 'OPEN_MEMBERSHIP').toString().toUpperCase())
    out['join_mode'] = joinMode.toUpperCase();
  return out;
}

Map<String, dynamic> buildRoleChangePayload(
    {required String role, required String reason}) {
  return {'role': role.toUpperCase(), 'reason': reason.trim()};
}
