import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/qr/presentation/code_entry_sheet.dart';

void main() {
  test('mapping preview to login action', () {
    expect(previewNeedsLogin({'actionHint': 'LOGIN_REQUIRED'}, isAuthed: false),
        isTrue);
    expect(previewNeedsLogin({'actionHint': 'LOGIN_REQUIRED'}, isAuthed: true),
        isFalse);
  });

  test('mapping preview to public event navigation', () {
    final id = previewPublicEventId(
        {'kind': 'event_public', 'deeplink': 'tore://open?type=event&id=42'});
    expect(id, 42);
    expect(previewPublicEventId({'kind': 'join'}), isNull);
  });

  test('suffix rendering helper', () {
    expect(formatSuffix('ABCDEFGH'), '…CDEFGH');
    expect(formatSuffix('ABCD-EF'), 'ABCDEF');
  });

  test('copy value null fallback hint', () {
    expect(
        previewCopyHint({'copyValue': null, 'copyHint': 'Connexion requise'}),
        'Connexion requise');
    expect(previewCopyHint({'copyValue': null}), 'Ouvre TORÈ → Entrer un code');
  });
}
