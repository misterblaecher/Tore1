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
  switch ((code ?? 'qr_unknown').toLowerCase()) {
    case 'qr_unknown':
    case 'invalid_qr':
      return const ErrorModel(code: 'qr_unknown', message: 'QR inconnu. Vérifiez le code ou essayez la saisie manuelle.');
    case 'expired':
    case 'expired_qr':
      return const ErrorModel(code: 'expired', message: 'Ce QR est expiré. Demandez un nouveau QR pour continuer.');
    case 'replay':
    case 'replay_qr':
      return const ErrorModel(code: 'replay', message: 'QR déjà utilisé. Utilisez un QR non consommé.');
    case 'module_off':
      return const ErrorModel(code: 'module_off', message: 'Ce module est désactivé pour le moment.');
    case 'event_paused':
      return const ErrorModel(code: 'event_paused', message: 'Événement en pause. Réessayez dès la reprise.');
    case 'backend_down':
      return const ErrorModel(code: 'backend_down', message: 'Service temporairement indisponible. Réessayez dans quelques instants.');
    case 'forbidden':
      return const ErrorModel(code: 'forbidden', message: 'Ce QR ne vous autorise pas à accéder à cette section.');
    default:
      return ErrorModel(code: code ?? 'qr_unknown', message: 'Impossible de traiter ce QR pour l’instant.');
  }
}
