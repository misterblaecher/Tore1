import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';
import 'package:tore/features/events/domain/event_public_view.dart';
import 'package:tore/shared/models/bar.dart';

void main() {
  test('rich public models parse real media, access, location and branding',
      () {
    final event = DiscoveryEvent.fromJson({
      'id': 8,
      'name': 'Nuit publique',
      'starts_at': '2030-05-10T20:00:00Z',
      'ends_at': '2030-05-11T01:00:00Z',
      'status': 'UPCOMING',
      'entry_price_cents': 900,
      'shortDescription': 'Une vraie description.',
      'bannerUrl': 'https://cdn.tore.be/event.jpg',
      'eventType': 'soirée',
      'capacity': 400,
      'accessType': 'TICKET',
      'currency': 'EUR',
      'lat': 50.64,
      'lng': 5.57,
    });
    final bar = Bar.fromJson({
      'id': 2,
      'name': 'Le Bar',
      'city': 'Liège',
      'bannerUrl': 'https://cdn.tore.be/bar.jpg',
      'primaryColor': '#ba1733',
      'modules': ['menu', 'wallet'],
    });

    expect(event.imageUrl, 'https://cdn.tore.be/event.jpg');
    expect(event.capacity, 400);
    expect(event.lat, 50.64);
    expect(bar.primaryColor, '#BA1733');
    expect(bar.modules, ['menu', 'wallet']);
  });

  test('unsafe media and invalid colors are ignored', () {
    final event = EventPublicView.fromJson({
      'id': 8,
      'name': 'Nuit publique',
      'links': {},
      'flags': {},
      'pricing': {},
      'accessPolicy': {},
      'venue': {},
      'host': {},
      'bannerUrl': 'file:///secret',
    });
    final bar = Bar.fromJson({
      'id': 2,
      'name': 'Le Bar',
      'city': 'Liège',
      'logoUrl': 'javascript:alert(1)',
      'primaryColor': 'ruby',
    });

    expect(event.imageUrl, isNull);
    expect(bar.logoUrl, isNull);
    expect(bar.primaryColor, isNull);
  });
}
