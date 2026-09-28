import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/qr/qr_parser.dart';
import 'package:tore/core/qr/qr_validator.dart';
import 'package:tore/features/qr/qr_resolve_service.dart';

void main() {
  final parser = QrParser();

  QrResolveResult validResult() => const QrResolveResult(
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
      );

  group('QrValidator', () {
    test('expired QR stays blocked before server verification', () async {
      final payload = parser.parse('tore://join_event?event_id=1&exp=1');
      final validator = QrValidator(resolveRaw: (_) async => validResult());

      final result = await validator.validate(
        payload,
        requireServerVerification: true,
      );
      expect(result.status, QrValidationStatus.expired);
      expect(result.isOk, isFalse);
    });

    test('ok when backend verifies the QR', () async {
      final payload = parser.parse('tore://join_event?event_id=1');
      final validator = QrValidator(resolveRaw: (_) async => validResult());

      final result = await validator.validate(
        payload,
        requireServerVerification: true,
      );
      expect(result.status, QrValidationStatus.ok);
    });

    test('Entry offline stays pending', () async {
      final payload = parser.parse('tore://join_event?event_id=1');
      final validator = QrValidator(resolveRaw: (_) async => validResult());

      final result = await validator.validate(
        payload,
        tryBackend: false,
        requireServerVerification: true,
      );

      expect(result.status, QrValidationStatus.pending);
      expect(result.isOk, isFalse);
      expect(result.isPending, isTrue);
    });

    test('Entry online resolver failure is not accepted', () async {
      final payload = parser.parse('tore://join_event?event_id=1');
      final validator =
          QrValidator(resolveRaw: (_) async => throw StateError('resolver down'));

      final result = await validator.validate(
        payload,
        requireServerVerification: true,
      );

      expect(result.status, QrValidationStatus.pending);
      expect(result.isOk, isFalse);
    });

    test('sensitive QR resolver failure never succeeds', () async {
      final payload =
          parser.parse('tore://staff_entry?event_id=1&token=staff-token');
      final validator =
          QrValidator(resolveRaw: (_) async => throw StateError('resolver down'));

      expect(qrTypeRequiresServerVerification(payload.type), isTrue);
      final result = await validator.validate(
        payload,
        requireServerVerification:
            qrTypeRequiresServerVerification(payload.type),
      );

      expect(result.status, QrValidationStatus.pending);
      expect(result.isOk, isFalse);
    });

    test('non-sensitive navigation QR keeps resolver-down fallback', () async {
      final payload = parser.parse('tore://bar_profile?bar_id=12');
      final validator =
          QrValidator(resolveRaw: (_) async => throw StateError('resolver down'));

      expect(qrTypeRequiresServerVerification(payload.type), isFalse);
      final result = await validator.validate(
        payload,
        requireServerVerification:
            qrTypeRequiresServerVerification(payload.type),
      );

      expect(result.status, QrValidationStatus.ok);
      expect(result.isOk, isTrue);
    });

    test('revoked QR stays blocked when resolver answers revoked', () async {
      final payload =
          parser.parse('tore://staff_entry?event_id=1&token=revoked-token');
      final validator = QrValidator(
        resolveRaw: (_) async => const QrResolveResult(
          valid: false,
          type: 'staff_entry',
          eventId: 1,
          barId: null,
          token: null,
          orderId: null,
          routeFront: null,
          reason: 'revoked',
          requiredRole: null,
          grantedRole: null,
        ),
      );

      final result = await validator.validate(
        payload,
        requireServerVerification: true,
      );

      expect(result.status, QrValidationStatus.revoked);
      expect(result.isOk, isFalse);
    });

    test('sensitive QR policy covers staff, order and claim flows', () {
      expect(qrTypeRequiresServerVerification(QrType.staffEntry), isTrue);
      expect(qrTypeRequiresServerVerification(QrType.staffBar), isTrue);
      expect(qrTypeRequiresServerVerification(QrType.staffInvite), isTrue);
      expect(qrTypeRequiresServerVerification(QrType.staffBackup), isTrue);
      expect(qrTypeRequiresServerVerification(QrType.order), isTrue);
      expect(qrTypeRequiresServerVerification(QrType.hunt), isTrue);
    });
  });
}
