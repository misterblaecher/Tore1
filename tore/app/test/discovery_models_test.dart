import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/discovery/domain/discovery_models.dart';

void main() {
  test('discovery query maps supported filters to backend parameters', () {
    const query = DiscoveryQuery(
      search: '  Cercle  ',
      status: DiscoveryStatus.tonight,
      city: ' Liège ',
      barId: 3,
      structureId: 9,
    );

    expect(query.toQueryParameters(), {
      'query': 'Cercle',
      'status': 'TONIGHT',
      'city': 'Liège',
      'bar_id': 3,
      'structure_id': 9,
      'limit': 100,
    });
  });

  test('discovery event parses real metadata without fixture fallbacks', () {
    final event = DiscoveryEvent.fromJson({
      'id': 18,
      'name': 'Bal des sciences',
      'starts_at': '2030-05-10T20:00:00Z',
      'ends_at': '2030-05-11T02:00:00Z',
      'status': 'UPCOMING',
      'eventState': 'LIVE',
      'entry_price_cents': 650,
      'bar_id': 2,
      'barName': 'Reflektor',
      'city': 'Liège',
      'venue': 'Quai 22',
      'host': {'type': 'orga', 'name': 'Cercle X'},
      'modulesOn': ['menu', 'polymarket'],
    });

    expect(event.id, 18);
    expect(event.hostName, 'Cercle X');
    expect(event.barName, 'Reflektor');
    expect(event.modules, contains('polymarket'));
    expect(event.isFree, isFalse);
  });
}
