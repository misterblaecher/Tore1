import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/community/community_models.dart';
import 'package:tore/features/community/data/orga_events_cache.dart';
import 'package:tore/features/events/presentation/create_event_wizard_screen.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('OrgaEventSummary parsing keeps publication/runtime/date fields', () {
    final event = MyEventSummary.fromJson({
      'id': 44,
      'name': 'Night',
      'startAt': '2026-05-11T18:30:00Z',
      'endAt': '2026-05-12T01:30:00Z',
      'publicationStatus': 'PUBLISHED',
      'visibility': 'PUBLIC',
      'eventState': 'DEGRADED',
      'modulesOn': {'entry': true},
    });

    expect(event.id, 44);
    expect(event.publicationStatus, 'PUBLISHED');
    expect(event.visibility, 'PUBLIC');
    expect(event.status, 'DEGRADED');
    expect(event.startAt.toUtc().hour, 18);
  });

  test('orga events cache ttl store/restore', () async {
    SharedPreferences.setMockInitialValues({});
    final cache = OrgaEventsCache(ttl: const Duration(seconds: 0));
    await cache.savePublic(9, {
      'items': [
        {'id': 1, 'name': 'Cached'}
      ]
    });

    final (payload, isStale) = await cache.readPublic(9);
    expect(payload?['items'], isNotNull);
    expect(isStale, isTrue);
  });

  test('wizard prefill host orga selection transition', () {
    final noPrefill = resolveCreateEventHostPrefill(
        prefillOrga: null, prefillHostOrgaId: null);
    expect(noPrefill.$1, 'user');
    expect(noPrefill.$2, isNull);

    final withPrefill = resolveCreateEventHostPrefill(prefillHostOrgaId: 12);
    expect(withPrefill.$1, 'orga');
    expect(withPrefill.$2, '12');
  });
}
