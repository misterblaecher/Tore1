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
}
