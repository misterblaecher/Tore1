import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/glossary/glossary_cache.dart';

void main() {
  test('cache store and restore works', () async {
    SharedPreferences.setMockInitialValues({});
    const store = GlossaryCacheStore();
    await store.write('glossary_committees_public', {
      'items': [
        {'id': 1, 'name': 'Comité A'}
      ]
    });

    final entry = await store.read('glossary_committees_public');
    expect(entry, isNotNull);
    expect((entry!.payload['items'] as List).length, 1);
    expect(entry.status.isStale, isFalse);
  });

  test('expired cache is stale', () async {
    final old = DateTime.now()
        .toUtc()
        .subtract(const Duration(days: 8))
        .toIso8601String();
    SharedPreferences.setMockInitialValues({
      'glossary_public_settings_9': jsonEncode({
        'payload': {'publicEnabled': true, 'availableTags': []},
        'lastSyncAt': old,
        'ttlSeconds': const Duration(days: 7).inSeconds,
      }),
    });

    const store = GlossaryCacheStore();
    final entry = await store.read('glossary_public_settings_9');
    expect(entry, isNotNull);
    expect(entry!.status.isStale, isTrue);
  });
}
