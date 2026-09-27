import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/events/domain/event_create_models.dart';

void main() {
  test('parse share payload', () {
    final payload = EventSharePayload.fromJson({
      'deeplink': 'tore://event/join?event_id=12',
      'https_link': 'https://app.tore/events/12',
      'qr_payload_join': 'tore://join_event?event_id=12',
      'event_code': 'ABC123',
    });

    expect(payload.deeplink, contains('tore://'));
    expect(payload.httpsLink, startsWith('https://'));
    expect(payload.eventCode, 'ABC123');
  });

  test('wizard state step transitions', () {
    const initial = CreateWizardState(step: 0);
    final next = initial.next();
    final prev = next.prev();

    expect(next.step, 1);
    expect(prev.step, 0);
  });

  test(
    'payload keeps host, visibility and module API keys with public content',
    () {
      final start = DateTime(2026, 10, 3, 20, 30);
      final end = DateTime(2026, 10, 4, 2);
      final payload = buildEventCreatePayload(
        name: '  Concert  ',
        start: start,
        end: end,
        visibility: 'PRIVATE',
        hostType: 'orga',
        hostId: '42',
        venueName: ' Salle ',
        venueAddress: ' Rue du Test ',
        modulesOn: modulesForPreset('Concert'),
        isFree: false,
        price: '8,50',
        description: '  Une belle soirée.  ',
      );

      expect(payload['name'], 'Concert');
      expect(payload['startAt'], start.toUtc().toIso8601String());
      expect(payload['endAt'], end.toUtc().toIso8601String());
      expect(payload['host_type'], 'orga');
      expect(payload['host_id'], '42');
      expect(payload['visibility'], 'PRIVATE');
      expect(payload['venue'], {'name': 'Salle', 'address': 'Rue du Test'});
      expect(payload['entry_price_cents'], 850);
      expect(payload['currency'], 'EUR');
      expect(payload['public_description'], 'Une belle soirée.');
      expect(payload['modulesOn']['music'], true);
      expect(payload['modulesOn']['hunt'], false);
      expect(payload['rulesFlags'], isEmpty);
    },
  );

  test('free event ignores price and user host has no orga id', () {
    final start = DateTime.utc(2026, 10, 3, 20);
    final payload = buildEventCreatePayload(
      name: 'Open',
      start: start,
      end: start.add(const Duration(hours: 2)),
      visibility: 'PUBLIC',
      hostType: 'user',
      venueName: '',
      venueAddress: '',
      modulesOn: {'entry': true},
      isFree: true,
      price: 'invalid',
      description: '',
    );
    expect(payload['entry_price_cents'], 0);
    expect(payload.containsKey('host_id'), false);
    expect(payload['modulesOn'], {'entry': true});
  });

  test('critical event creation validations', () {
    final start = DateTime.utc(2026, 10, 3, 20);
    String? validate({
      DateTime? end,
      String name = 'Event',
      bool isFree = true,
      String price = '',
      String description = '',
    }) => validateEventCreate(
      name: name,
      start: start,
      end: end ?? start.add(const Duration(hours: 2)),
      isFree: isFree,
      price: price,
      description: description,
    );

    expect(validate(name: ' '), isNotNull);
    expect(validate(end: start), contains('fin'));
    expect(
      validate(end: start.subtract(const Duration(minutes: 1))),
      isNotNull,
    );
    expect(validate(isFree: false, price: '0'), isNotNull);
    expect(validate(isFree: false, price: '5,123'), isNotNull);
    expect(validate(isFree: false, price: '5,20'), isNull);
    expect(validate(description: 'x' * 281), isNotNull);
    expect(validate(description: 'x' * 280), isNull);
  });

  test('preset keys stay stable and cover every module', () {
    for (final preset in eventModulePresets.keys) {
      expect(modulesForPreset(preset).keys, eventModuleLabels.keys);
    }
    expect(modulesForPreset('Animation')['hunt'], true);
    expect(eventModuleLabels['polymarket_event'], 'Pronostics');
  });
}
