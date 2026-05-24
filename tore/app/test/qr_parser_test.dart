import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/qr/qr_parser.dart';

void main() {
  final parser = QrParser();

  group('QrParser', () {
    test('parse join_event deeplink', () {
      final payload = parser.parse('tore://join_event?event_id=12');
      expect(payload.type, QrType.joinEvent);
      expect(payload.eventId, 12);
    });

    test('parse menu deeplink', () {
      final payload = parser.parse('tore://menu?event_id=12&bar_id=2');
      expect(payload.type, QrType.menu);
      expect(payload.eventId, 12);
      expect(payload.barId, 2);
    });

    test('parse staff entry', () {
      final payload = parser.parse('tore://staff_entry?event_id=5');
      expect(payload.type, QrType.staffEntry);
      expect(payload.eventId, 5);
    });

    test('parse staff bar', () {
      final payload = parser.parse('tore://bar_staff?event_id=5');
      expect(payload.type, QrType.staffBar);
    });

    test('parse wifi', () {
      final payload = parser.parse('tore://wifi?event_id=7');
      expect(payload.type, QrType.wifi);
    });

    test('parse hunt', () {
      final payload = parser.parse('tore://hunt?event_id=7&code=ABC');
      expect(payload.type, QrType.hunt);
    });

    test('parse battle', () {
      final payload = parser.parse('tore://battle?battle_id=9');
      expect(payload.type, QrType.battle);
      expect(payload.battleId, 9);
    });

    test('parse order', () {
      final payload = parser.parse('tore://order?order_id=17');
      expect(payload.type, QrType.order);
      expect(payload.orderId, 17);
    });

    test('parse polymarket', () {
      final payload = parser.parse('tore://polymarket?bet_id=44');
      expect(payload.type, QrType.polymarket);
      expect(payload.betId, 44);
    });

    test('parse open event deeplink', () {
      final payload = parser.parse('tore://open?type=event&id=21');
      expect(payload.type, QrType.joinEvent);
      expect(payload.eventId, 21);
    });

    test('parse https open deeplink compatibility', () {
      final payload = parser.parse('https://app.tore.be/open?type=event&id=21');
      expect(payload.type, QrType.joinEvent);
      expect(payload.eventId, 21);
    });
    test('parse open orga deeplink', () {
      final payload = parser.parse('tore://open?type=orga&id=7');
      expect(payload.type, QrType.orga);
      expect(payload.committeeId, 7);
    });

    test('parse open join code deeplink', () {
      final payload = parser.parse('tore://open?type=join&code=JOIN66');
      expect(payload.type, QrType.joinEvent);
      expect(payload.tokenId, 'JOIN66');
    });

    test('parse open staff invite deeplink', () {
      final payload = parser.parse('tore://open?type=staff_invite&code=ABC123');
      expect(payload.type, QrType.staffInvite);
      expect(payload.tokenId, 'ABC123');
    });

    test('parse open staff backup deeplink', () {
      final payload = parser
          .parse('tore://open?type=staff_backup&eventId=12&code=ABCD2345');
      expect(payload.type, QrType.staffBackup);
      expect(payload.eventId, 12);
      expect(payload.tokenId, 'ABCD2345');
    });

    test('parse open orga invite deeplink', () {
      final payload =
          parser.parse('tore://open?type=orga_invite&code=ABC123ZZ');
      expect(payload.type, QrType.orgaInvite);
      expect(payload.tokenId, 'ABC123ZZ');
    });
    test('parse json payload', () {
      final payload =
          parser.parse('{"type":"join_event","event_id":88,"exp":9999999999}');
      expect(payload.type, QrType.joinEvent);
      expect(payload.eventId, 88);
      expect(payload.expiresAt, isNotNull);
    });

    test('unknown on invalid format', () {
      final payload = parser.parse('not-a-qr');
      expect(payload.type, QrType.unknown);
      expect(payload.reason, 'format invalide');
    });
  });
}
