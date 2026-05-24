import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/qr/presentation/code_entry_detector.dart';

void main() {
  const detector = CodeEntryDetector();

  test('detects open links', () {
    final join =
        detector.detect('https://app.tore.be/open?type=join&code=ab-12 34');
    expect(join.kind, CodeEntryKind.join);
    expect(join.code, 'AB1234');

    final event = detector.detect('tore://open?type=event&id=42');
    expect(event.kind, CodeEntryKind.event);
    expect(event.eventId, 42);
  });

  test('normalizes manual codes (spaces/dashes/uppercase)', () {
    expect(normalizeManualCode(' ab-12\n 34 '), 'AB1234');
    expect(normalizeManualCode(' ev-nt\t99 '), 'EVNT99');
  });

  test('detects manual code formats', () {
    expect(detector.detect('ABC123').kind, CodeEntryKind.join);
    expect(detector.detect('A1B2C3D4').kind, CodeEntryKind.staffInvite);
    final backup = detector.detect('45:ABCD2345');
    expect(backup.kind, CodeEntryKind.staffBackup);
    expect(backup.eventId, 45);
  });
}
