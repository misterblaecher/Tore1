enum CodeEntryKind { join, event, staffInvite, staffBackup, orgaInvite, unknown }

class CodeEntryResolution {
  const CodeEntryResolution({
    required this.kind,
    this.code,
    this.eventId,
    this.source,
  });

  final CodeEntryKind kind;
  final String? code;
  final int? eventId;
  final Uri? source;

  bool get isKnown => kind != CodeEntryKind.unknown;
}

class CodeEntryDetector {
  const CodeEntryDetector();

  CodeEntryResolution detect(String raw) {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) return const CodeEntryResolution(kind: CodeEntryKind.unknown);

    final uri = Uri.tryParse(trimmed);
    if (uri != null) {
      final isOpen = (uri.scheme == 'tore' && uri.host == 'open') ||
          (uri.scheme == 'https' && uri.host == 'app.tore.be' && uri.path == '/open');
      if (isOpen) {
        final type = (uri.queryParameters['type'] ?? '').toLowerCase();
        final code = normalizeManualCode(uri.queryParameters['code'] ?? '');
        final id = int.tryParse(uri.queryParameters['id'] ?? uri.queryParameters['eventId'] ?? '');
        return switch (type) {
          'join' => CodeEntryResolution(kind: CodeEntryKind.join, code: code, source: uri),
          'event' => CodeEntryResolution(kind: CodeEntryKind.event, eventId: id, source: uri),
          'staff_invite' => CodeEntryResolution(kind: CodeEntryKind.staffInvite, code: code, source: uri),
          'staff_backup' => CodeEntryResolution(kind: CodeEntryKind.staffBackup, code: code, eventId: id, source: uri),
          'orga_invite' => CodeEntryResolution(kind: CodeEntryKind.orgaInvite, code: code, source: uri),
          _ => const CodeEntryResolution(kind: CodeEntryKind.unknown),
        };
      }
    }

    final compact = normalizeManualCode(trimmed);
    final splitBackup = compact.split(':');
    if (splitBackup.length == 2) {
      final eventId = int.tryParse(splitBackup.first);
      if (eventId != null && splitBackup.last.length >= 6) {
        return CodeEntryResolution(kind: CodeEntryKind.staffBackup, eventId: eventId, code: splitBackup.last);
      }
    }
    if (compact.length == 6) return CodeEntryResolution(kind: CodeEntryKind.join, code: compact);
    if (compact.length == 8) return CodeEntryResolution(kind: CodeEntryKind.staffInvite, code: compact);
    if (compact.length >= 10) return CodeEntryResolution(kind: CodeEntryKind.orgaInvite, code: compact);
    return const CodeEntryResolution(kind: CodeEntryKind.unknown);
  }

}

String normalizeManualCode(String value) {
  final compact = value
      .trim()
      .replaceAll(RegExp(r'[\s\n\r\t]+'), '')
      .replaceAll('-', '');
  return compact.toUpperCase().replaceAll(RegExp(r'[^A-Z0-9:]'), '');
}
