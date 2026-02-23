import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/models/safe_parsing.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/routing/app_routes.dart';
import 'package:tore/rebuild/routing/qr_router.dart';
import 'package:tore/rebuild/services/client_log.dart';
import 'package:tore/rebuild/ui/theme/tore_theme.dart';

void main() {
  test('scrubber redacts auth headers, jwt, query params, and contact fields', () {
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
    expect((out['url'] as String), contains('[redacted]'));
    expect(out['email'], '[redacted]');
    expect(out['phone'], '[redacted]');
    expect((out['user_id'] as String), contains('***'));
    expect((out['note'] as String), isNot(contains('person@example.com')));
    expect((out['note'] as String), isNot(contains('eyJabc.def.ghi')));
  });

  test('safe parsing utilities return defaults for missing/unexpected values', () {
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
    expect(tryParseDateTime(data['when'], fallback: DateTime.fromMillisecondsSinceEpoch(0)), DateTime.fromMillisecondsSinceEpoch(0));
  });

  test('event state helper and spacing rhythm tokens stay stable', () {
    expect(EventState.live.isLive, isTrue);
    expect(EventState.paused.isLive, isFalse);

    expect(ToreTokens.s8, 8.0);
    expect(ToreTokens.s12, 12.0);
    expect(ToreTokens.s16, 16.0);
    expect(ToreTokens.s24, 24.0);
  });

  test('QR router no-throw fallback under fuzzed partial payloads', () {
    final router = QrRouter();
    final random = Random(42);

    for (var i = 0; i < 200; i++) {
      final map = <String, dynamic>{
        if (random.nextBool()) 'valid': random.nextBool(),
        if (random.nextBool()) 'type': random.nextBool() ? 'join_event' : random.nextInt(999),
        if (random.nextBool()) 'event_id': random.nextBool() ? random.nextInt(1000).toString() : null,
        if (random.nextBool()) 'route_front': random.nextBool() ? '/event/${random.nextInt(99)}' : random.nextInt(10),
        if (random.nextBool()) 'reason': random.nextBool() ? 'backend_down' : null,
      };

      expect(() => QrResolve.fromJson(map), returnsNormally);
      final resolved = QrResolve.fromJson(map);
      expect(() => router.targetFor(resolved), returnsNormally);
      final route = router.targetFor(resolved);
      expect(route.isNotEmpty, isTrue);
    }

    expect(router.targetFor(null), AppRoutes.blocked);
  });
}
