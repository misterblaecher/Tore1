import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/qr/qr_parser.dart';
import 'package:tore/core/qr/qr_validator.dart';
import 'package:tore/features/qr/qr_resolve_service.dart';

void main() {
  final parser = QrParser();

  group('QrValidator', () {
    test('expired if local expiry is passed', () async {
      final payload = parser.parse('tore://join_event?event_id=1&exp=1');
      final validator = QrValidator(
        resolveRaw: (_) async => const QrResolveResult(
          valid: true,
          type: 'join_event',
          eventId: 1,
          barId: null,
          token: null,
          orderId: null,
          routeFront: null,
          reason: null,
          requiredRole: null,
          grantedRole: null,
        ),
      );

      final result = await validator.validate(payload);
      expect(result.status, QrValidationStatus.expired);
    });

    test('ok when not expired and backend valid', () async {
      final payload = parser.parse('tore://join_event?event_id=1');
      final validator = QrValidator(
        resolveRaw: (_) async => const QrResolveResult(
          valid: true,
          type: 'join_event',
          eventId: 1,
          barId: null,
          token: null,
          orderId: null,
          routeFront: null,
          reason: null,
          requiredRole: null,
          grantedRole: null,
        ),
      );

      final result = await validator.validate(payload);
      expect(result.status, QrValidationStatus.ok);
    });

    test('recognized QR stays pending without server verification', () async {
      final payload =
          parser.parse('tore://join_event?event_id=1&sig=unverified');
      final validator =
          QrValidator(resolveRaw: (_) async => throw StateError('offline'));

      final result = await validator.validate(payload);
      expect(result.status, QrValidationStatus.pending);
      expect(result.isOk, isFalse);
      expect(result.isPending, isTrue);
      expect((await validator.validate(payload, tryBackend: false)).isPending,
          isTrue);
    });
  });
}
