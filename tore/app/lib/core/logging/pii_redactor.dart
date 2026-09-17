/// Pure redaction helpers for diagnostics and client-side logs.
///
/// This intentionally does not persist logs. It only migrates the useful PII
/// scrubbing behaviour from the historical rebuild logger into the canonical
/// runtime.
Map<String, dynamic> scrubLogFields(Map<String, dynamic> fields) {
  return fields.map((key, value) {
    final normalizedKey = key.toLowerCase();
    if (_isSensitiveKey(normalizedKey)) {
      return MapEntry(key, '[redacted]');
    }
    if (value is Map) {
      return MapEntry(
        key,
        scrubLogFields(Map<String, dynamic>.from(value)),
      );
    }
    if (value is List) {
      return MapEntry(
        key,
        value
            .map((item) => item is Map
                ? scrubLogFields(Map<String, dynamic>.from(item))
                : item is String
                    ? redactFreeText(item)
                    : item)
            .toList(growable: false),
      );
    }
    if (normalizedKey.contains('user') && value is String) {
      return MapEntry(key, _maskIdentifier(value));
    }
    if (value is String) {
      final redacted = normalizedKey.contains('url')
          ? scrubUrlQueryParams(value)
          : redactFreeText(value);
      return MapEntry(
          key,
          redacted.length > 180
              ? '${redacted.substring(0, 180)}...'
              : redacted);
    }
    return MapEntry(key, value);
  });
}

String scrubUrlQueryParams(String rawUrl) {
  final uri = Uri.tryParse(rawUrl);
  if (uri == null || !uri.hasQuery) return redactFreeText(rawUrl);
  final scrubbed = <String, String>{};
  for (final entry in uri.queryParameters.entries) {
    scrubbed[entry.key] = _isSensitiveKey(entry.key.toLowerCase())
        ? '[redacted]'
        : redactFreeText(entry.value);
  }
  return uri.replace(queryParameters: scrubbed).toString();
}

String redactFreeText(String input) {
  var out = input;
  out = out.replaceAll(
    RegExp(r'Bearer\s+[A-Za-z0-9\-\._~\+\/=]+', caseSensitive: false),
    'Bearer [redacted]',
  );
  out = out.replaceAll(
    RegExp(r'([?&](token|auth|key|authorization|secret)=)[^&\s]+',
        caseSensitive: false),
    r'$1[redacted]',
  );
  out = out.replaceAll(
    RegExp(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',
        caseSensitive: false),
    '[redacted-email]',
  );
  out = out.replaceAll(
    RegExp(r'\+?[0-9][0-9\s().-]{7,}[0-9]'),
    '[redacted-phone]',
  );
  out = out.replaceAll(
    RegExp(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'),
    '[redacted-jwt]',
  );
  return out;
}

bool _isSensitiveKey(String key) {
  const blockedFragments = <String>{
    'email',
    'phone',
    'name',
    'token',
    'password',
    'address',
    'authorization',
    'auth',
    'jwt',
    'secret',
    'bearer',
    'api_key',
    'apikey',
  };
  return blockedFragments.any(key.contains);
}

String _maskIdentifier(String value) {
  final clean = value.trim();
  if (clean.length <= 6) return '[redacted]';
  return '${clean.substring(0, 3)}***${clean.substring(clean.length - 3)}';
}
