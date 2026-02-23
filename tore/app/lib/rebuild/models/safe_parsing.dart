DateTime tryParseDateTime(Object? value, {DateTime? fallback}) {
  if (value is DateTime) return value;
  final parsed = DateTime.tryParse(value?.toString() ?? '');
  return parsed ?? fallback ?? DateTime.fromMillisecondsSinceEpoch(0);
}

String safeGetString(Map<String, dynamic> map, String key, {String fallback = '', List<String> aliases = const <String>[]}) {
  for (final k in <String>[key, ...aliases]) {
    final value = map[k];
    if (value == null) continue;
    final asString = value.toString().trim();
    if (asString.isNotEmpty) return asString;
  }
  return fallback;
}

int safeGetInt(Map<String, dynamic> map, String key, {int fallback = 0, List<String> aliases = const <String>[]}) {
  for (final k in <String>[key, ...aliases]) {
    final value = map[k];
    if (value is int) return value;
    if (value is num) return value.toInt();
    final parsed = int.tryParse(value?.toString() ?? '');
    if (parsed != null) return parsed;
  }
  return fallback;
}

Map<String, dynamic> safeGetMap(Map<String, dynamic> map, String key, {Map<String, dynamic> fallback = const <String, dynamic>{}, List<String> aliases = const <String>[]}) {
  for (final k in <String>[key, ...aliases]) {
    final value = map[k];
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return value.cast<String, dynamic>();
  }
  return fallback;
}

List<dynamic> safeGetList(Map<String, dynamic> map, String key, {List<dynamic> fallback = const <dynamic>[], List<String> aliases = const <String>[]}) {
  for (final k in <String>[key, ...aliases]) {
    final value = map[k];
    if (value is List<dynamic>) return value;
    if (value is Iterable) return value.toList(growable: false);
  }
  return fallback;
}
