import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/safety/safety_cache.dart';

void main() {
  test('cache store and restore works', () async {
    SharedPreferences.setMockInitialValues({});
    const store = SafetyCacheStore();
    await store.write('safety_state_42', {'enabled': true, 'orgaPhone': '123'});

    final entry = await store.read('safety_state_42');
    expect(entry, isNotNull);
    expect(entry!.payload['enabled'], isTrue);
    expect(entry.lastSyncAt, isNotNull);
  });

  test('expired cache returns null', () async {
    final expired = DateTime.now().toUtc().subtract(const Duration(minutes: 2)).toIso8601String();
    SharedPreferences.setMockInitialValues({
      'safety_history_42': jsonEncode({
        'payload': {'items': []},
        'exp': expired,
        'lastSyncAt': expired,
      }),
    });

    const store = SafetyCacheStore();
    final entry = await store.read('safety_history_42');
    expect(entry, isNull);
  });
}
