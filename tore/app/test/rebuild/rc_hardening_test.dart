import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/models/safe_parsing.dart';
import 'package:tore/rebuild/services/client_log.dart';
import 'package:tore/theme/tokens.dart';

void main() {
  test('scrubber redacts auth headers, jwt, query params, and contact fields',
      () {
    final input = <String, dynamic>{
      'authorization': 'Bearer super.secret.token',
      'url': 'https://api.tore.app/x?token=abc123&auth=xyz',
      'email': 'person@example.com',
      'phone': '+33 6 12 34 56 78',
      'user_id': 'usr_123456789',
      'note': 'reach me at person@example.com with jwt eyJabc.def.ghi',
    };

    final out = scrubJsonMap(input);
    expect(out['authorization'], '[redacted]');
    expect((out['url'] as String),
        anyOf(contains('[redacted]'), contains('%5Bredacted%5D')));
    expect(out['email'], '[redacted]');
    expect(out['phone'], '[redacted]');
    expect((out['user_id'] as String), contains('***'));
    expect((out['note'] as String), isNot(contains('person@example.com')));
    expect((out['note'] as String), isNot(contains('eyJabc.def.ghi')));
  });

  test('safe parsing utilities return defaults for missing/unexpected values',
      () {
    final data = <String, dynamic>{
      'count': 'not-int',
      'nested': 'oops',
      'items': 'oops',
      'when': 'invalid-date',
    };

    expect(safeGetString(data, 'missing', fallback: 'fallback'), 'fallback');
    expect(safeGetInt(data, 'count', fallback: 7), 7);
    expect(safeGetMap(data, 'nested'), isEmpty);
    expect(safeGetList(data, 'items'), isEmpty);
    expect(
        tryParseDateTime(data['when'],
            fallback: DateTime.fromMillisecondsSinceEpoch(0)),
        DateTime.fromMillisecondsSinceEpoch(0));
  });

  test('event state helper and spacing rhythm tokens stay stable', () {
    expect(EventState.live.isLive, isTrue);
    expect(EventState.paused.isLive, isFalse);

    expect(ToreSpace.s2, 8.0);
    expect(ToreSpace.s3, 12.0);
    expect(ToreSpace.s4, 16.0);
    expect(ToreSpace.s6, 24.0);
  });
}
