import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/shared/cache/cache_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('private profile caches are namespaced by user id', () async {
    final cache = CacheStore();
    expect(cache.ownerKey('user-a'), isNot(cache.ownerKey('user-b')));
    expect(cache.capabilitiesKey('user-a'),
        isNot(cache.capabilitiesKey('user-b')));
    expect(cache.affiliationsKey('user-a'),
        isNot(cache.affiliationsKey('user-b')));
    expect(cache.operationsKey('user-a', 'event', 1, 'hub'),
        isNot(cache.operationsKey('user-b', 'event', 1, 'hub')));

    await cache.setJson(cache.ownerKey('user-a'), {'name': 'Alice'});
    await cache.setJson(cache.ownerKey('user-b'), {'name': 'Bob'});
    expect((await cache.getJson(cache.ownerKey('user-a')))!['name'], 'Alice');
    expect((await cache.getJson(cache.ownerKey('user-b')))!['name'], 'Bob');
  });

  test('logout invalidation removes every private namespace, not public data',
      () async {
    final cache = CacheStore();
    await cache.setJson(cache.publicKey('profile-public'), {'id': 'public'});
    await cache.setJson(cache.ownerKey('user-a'), {'id': 'owner'});
    await cache.setJson(cache.capabilitiesKey('user-a'), {'modes': {}});
    await cache.setJson(cache.affiliationsKey('user-a'), {'items': []});
    await cache
        .setJson(cache.operationsKey('user-a', 'event', 1, 'hub'), {'id': 1});
    await cache.setJson(
        cache.operationsContextKey('user-a'), {'mode': 'orga', 'scope_id': 1});

    await cache.clearAllPrivate();

    expect(await cache.getJson(cache.ownerKey('user-a')), isNull);
    expect(await cache.getJson(cache.capabilitiesKey('user-a')), isNull);
    expect(await cache.getJson(cache.affiliationsKey('user-a')), isNull);
    expect(
        await cache.getJson(cache.operationsKey('user-a', 'event', 1, 'hub')),
        isNull);
    expect(await cache.getJson(cache.operationsContextKey('user-a')), isNull);
    expect(await cache.getJson(cache.publicKey('profile-public')), isNotNull);
  });
}
