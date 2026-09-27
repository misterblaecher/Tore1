import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/qr/qr_resolve_service.dart';
import 'qr_parser.dart';

enum QrValidationStatus { ok, pending, expired, revoked, invalid, unknownType }

class QrValidationResult {
  const QrValidationResult({required this.status, this.reason});

  final QrValidationStatus status;
  final String? reason;

  bool get isOk => status == QrValidationStatus.ok;
  bool get isPending => status == QrValidationStatus.pending;
}

class QrValidator {
  QrValidator(
      {QrResolveService? resolver,
      Future<QrResolveResult> Function(String raw)? resolveRaw})
      : _resolver = resolver,
        _resolveRaw = resolveRaw;

  final QrResolveService? _resolver;
  final Future<QrResolveResult> Function(String raw)? _resolveRaw;

  Future<QrValidationResult> validate(QrPayload payload,
      {bool tryBackend = true}) async {
    if (payload.type == QrType.unknown) {
      return const QrValidationResult(
          status: QrValidationStatus.unknownType, reason: 'Type inconnu');
    }

    final expiry = payload.expiresAt;
    if (expiry != null && expiry.isBefore(DateTime.now())) {
      return const QrValidationResult(
          status: QrValidationStatus.expired, reason: 'expired');
    }

    final backend = tryBackend ? await _validateWithBackend(payload.raw) : null;
    return backend ??
        const QrValidationResult(
            status: QrValidationStatus.pending,
            reason: 'En attente de vérification serveur');
  }

  Future<QrValidationResult?> _validateWithBackend(String raw) async {
    try {
      final resolver = _resolveRaw;
      if (resolver == null && _resolver == null) return null;
      final result = await (resolver?.call(raw) ?? _resolver!.resolve(raw));
      if (result.valid)
        return const QrValidationResult(status: QrValidationStatus.ok);
      switch ((result.reason ?? '').toLowerCase()) {
        case 'expired':
          return const QrValidationResult(
              status: QrValidationStatus.expired, reason: 'expired');
        case 'revoked':
          return const QrValidationResult(
              status: QrValidationStatus.revoked, reason: 'revoked');
        case 'invalid':
        case 'invalid_qr':
          return const QrValidationResult(
              status: QrValidationStatus.invalid, reason: 'invalid_qr');
        default:
          return QrValidationResult(
              status: QrValidationStatus.invalid,
              reason: result.reason ?? 'invalid_qr');
      }
    } catch (_) {
      return null;
    }
  }
}

final qrValidatorProvider = Provider<QrValidator>((ref) {
  return QrValidator(resolver: ref.watch(qrResolveServiceProvider));
});
