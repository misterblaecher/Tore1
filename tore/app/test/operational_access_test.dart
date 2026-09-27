import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/operations/domain/operational_models.dart';
import 'package:tore/shared/cache/cache_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  ScopedCapability eventCapability(int id) => ScopedCapability(
        id: 'event:$id:staff:1',
        type: 'EVENT',
        scope: 'event:$id',
        eventId: id,
        role: 'ENTRY',
        actions: const {'event.view_ops', 'event.manage_entry'},
        source: 'EVENT_STAFF',
        event: {'id': id, 'name': 'Event $id'},
      );

  ScopedCapability barCapability(int id) => ScopedCapability(
        id: 'bar:$id:access:1',
        type: 'BAR',
        scope: 'bar:$id',
        barId: id,
        role: 'BARTENDER',
        actions: const {'bar.view_ops', 'bar.manage_orders'},
        source: 'PARTNER_ACCESS',
        bar: {'id': id, 'name': 'Bar $id'},
      );

  test('USER only has no operational mode', () {
    const capabilities = OperationalCapabilities(userId: 'user-only');
    expect(capabilities.canUseOrga, isFalse);
    expect(capabilities.canUseBar, isFalse);
    expect(
        OperationalGuard.canEnter(
            mode: OperationalMode.orga, scopeId: 1, capabilities: capabilities),
        isFalse);
  });

  test('event capability is deny-by-default and isolated to its scope', () {
    final capability = eventCapability(10);
    final capabilities =
        OperationalCapabilities(userId: 'staff', events: [capability]);
    expect(
        OperationalGuard.canPerform(
            capability: capability,
            action: 'event.manage_entry',
            mode: OperationalMode.orga,
            scopeId: 10),
        isTrue);
    expect(
        OperationalGuard.canPerform(
            capability: capability,
            action: 'event.manage_staff',
            mode: OperationalMode.orga,
            scopeId: 10),
        isFalse);
    expect(
        OperationalGuard.canEnter(
            mode: OperationalMode.orga,
            scopeId: 11,
            capabilities: capabilities),
        isFalse);
  });

  test('bilan access requires an admin-equivalent scoped capability', () {
    final entry = eventCapability(10);
    final manager = ScopedCapability.fromJson({
      ...entry.toJson(),
      'role': 'MANAGER',
    });
    expect(OperationalGuard.canViewReport(entry, 10), isFalse);
    expect(OperationalGuard.canViewReport(manager, 10), isTrue);
    expect(OperationalGuard.canViewReport(manager, 11), isFalse);
    final noOps = ScopedCapability.fromJson({
      ...manager.toJson(),
      'actions': <String>[],
    });
    expect(OperationalGuard.canViewReport(noOps, 10), isFalse);
  });

  test('bar A never opens bar B, including via direct/deep link guard', () {
    final capability = barCapability(20);
    final capabilities =
        OperationalCapabilities(userId: 'bar-user', bars: [capability]);
    expect(
        OperationalGuard.allowsDeepLink(
            capabilities: capabilities,
            mode: OperationalMode.bar,
            scopeId: 20,
            action: 'bar.manage_orders'),
        isTrue);
    expect(
        OperationalGuard.allowsDeepLink(
            capabilities: capabilities,
            mode: OperationalMode.bar,
            scopeId: 21,
            action: 'bar.manage_orders'),
        isFalse);
  });

  test('operational caches and selected context are namespaced per user/scope',
      () async {
    final cache = CacheStore();
    final a = cache.operationsKey('alice', 'event', 1, 'hub');
    final b = cache.operationsKey('alice', 'event', 2, 'hub');
    final c = cache.operationsKey('bob', 'event', 1, 'hub');
    expect({a, b, c}.length, 3);
    await cache.setJson(a, {'event': 'A'});
    await cache.setJson(b, {'event': 'B'});
    await cache.setJson(
        cache.operationsContextKey('alice'), {'mode': 'orga', 'scope_id': 999});

    // A persisted selection contains no actions and therefore cannot become
    // an authorization object by itself.
    final stored = await cache.getJson(cache.operationsContextKey('alice'));
    expect(stored?.containsKey('actions'), isFalse);

    await cache.clearPrivateForUser('alice');
    expect(await cache.getJson(a), isNull);
    expect(await cache.getJson(b), isNull);
    expect(await cache.getJson(cache.operationsContextKey('alice')), isNull);
  });

  test('uniform capability parser ignores a forged legacy mode flag', () {
    final parsed = OperationalCapabilities.fromJson({
      'user_id': 'user',
      'modes': {'organizer': true, 'bar': true},
      'events': [],
      'bars': [],
    });
    expect(parsed.canUseOrga, isFalse);
    expect(parsed.canUseBar, isFalse);
  });
}
