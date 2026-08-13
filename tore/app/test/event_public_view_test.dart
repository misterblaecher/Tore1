import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/events/domain/event_public_view.dart';

void main() {
  test('parses EventPublicView payload', () {
    final view = EventPublicView.fromJson({
      'id': 12,
      'name': 'Bal des sciences',
      'startAt': '2026-01-01T20:00:00Z',
      'endAt': '2026-01-02T01:00:00Z',
      'eventState': 'LIVE',
      'modulesOn': ['menu', 'wallet'],
      'host': {'name': 'Cercle X', 'instagram': 'cerclex'},
      'venue': {'name': 'Hall A'},
      'pricing': {'entryPriceCents': 700, 'isFree': false},
      'accessPolicy': {
        'visibility': 'PUBLIC',
        'charterRequired': true,
        'charterVersion': 'v2'
      },
      'description': 'Une soirée scientifique.',
      'links': {
        'webUrl': 'https://app.tore.be/event/12',
        'openUrl': 'https://app.tore.be/open?type=event&id=12',
        'deeplink': 'tore://open?type=event&id=12'
      },
      'flags': {'canJoin': true},
    });

    expect(view.id, 12);
    expect(view.name, 'Bal des sciences');
    expect(view.modulesOn, contains('menu'));
    expect(view.canJoin, isTrue);
    expect(view.hostInstagram, 'cerclex');
    expect(view.entryPriceCents, 700);
    expect(view.charterRequired, isTrue);
    expect(view.charterVersion, 'v2');
    expect(view.description, 'Une soirée scientifique.');
  });
}
