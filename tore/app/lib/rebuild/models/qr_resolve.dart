import 'error_model.dart';

class QrResolve {
  const QrResolve({
    required this.valid,
    required this.type,
    this.eventId,
    this.routeFront,
    this.reason,
  });

  final bool valid;
  final String type;
  final int? eventId;
  final String? routeFront;
  final String? reason;

  bool get isError => !valid;

  static QrResolve fromJson(Map<String, dynamic> json) => QrResolve(
        valid: json['valid'] == true,
        type: (json['type'] as String?) ?? 'unknown',
        eventId: json['event_id'] as int?,
        routeFront: json['route_front'] as String?,
        reason: json['reason'] as String?,
      );
}

ErrorModel mapQrReasonToError(String? code) {
  switch ((code ?? 'invalid_qr').toLowerCase()) {
    case 'invalid_qr':
      return const ErrorModel(code: 'invalid_qr', message: 'QR non reconnu.');
    case 'expired_qr':
      return const ErrorModel(code: 'expired_qr', message: 'Ce QR est expiré.');
    case 'replay_qr':
      return const ErrorModel(code: 'replay_qr', message: 'Ce QR a déjà été utilisé.');
    case 'module_off':
      return const ErrorModel(code: 'module_off', message: 'Module indisponible.');
    case 'forbidden':
      return const ErrorModel(code: 'forbidden', message: 'Accès refusé pour ce QR.');
    case 'event_paused':
      return const ErrorModel(code: 'event_paused', message: 'Événement temporairement en pause.');
    default:
      return ErrorModel(code: code ?? 'invalid_qr', message: 'Impossible de traiter ce QR.');
  }
}
