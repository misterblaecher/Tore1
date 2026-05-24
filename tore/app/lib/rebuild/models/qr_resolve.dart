import 'error_model.dart';
import 'safe_parsing.dart';

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
        type: safeGetString(json, 'type', fallback: 'unknown'),
        eventId: int.tryParse(
            safeGetString(json, 'event_id', aliases: const ['eventId'])),
        routeFront: (() {
          final route =
              safeGetString(json, 'route_front', aliases: const ['routeFront']);
          return route.isEmpty ? null : route;
        })(),
        reason: (() {
          final value = safeGetString(json, 'reason');
          return value.isEmpty ? null : value;
        })(),
      );
}

class UiCopy {
  const UiCopy(
      {required this.title, required this.message, required this.ctaLabel});
  final String title;
  final String message;
  final String ctaLabel;
}

const Map<String, UiCopy> uiCopyMapping = {
  'qr_unknown': UiCopy(
      title: 'QR inconnu',
      message:
          'Code non reconnu. Scannez un QR TORÈ valide ou utilisez la saisie.',
      ctaLabel: 'Réessayer'),
  'qr_expired': UiCopy(
      title: 'QR expiré',
      message: 'Ce QR a expiré. Demandez un nouveau code à l’accueil.',
      ctaLabel: 'Demander un nouveau QR'),
  'qr_replay': UiCopy(
      title: 'QR déjà utilisé',
      message: 'Ce QR a déjà servi. Utilisez un QR non consommé.',
      ctaLabel: 'Utiliser un autre QR'),
  'module_off': UiCopy(
      title: 'Module indisponible',
      message: 'Le module est coupé pour cet événement.',
      ctaLabel: 'Retour au hub'),
  'event_paused': UiCopy(
      title: 'Événement en pause',
      message: 'Actions temporairement gelées. Reprenez dans quelques minutes.',
      ctaLabel: 'Compris'),
  'backend_down': UiCopy(
      title: 'Service indisponible',
      message: 'Serveur occupé. Réessayez dans un instant.',
      ctaLabel: 'Réessayer'),
  'offline_write_blocked': UiCopy(
      title: 'Action bloquée hors ligne',
      message: 'Repassez en ligne pour confirmer cette action.',
      ctaLabel: 'OK'),
};

String normalizeUiCode(String? code) {
  switch ((code ?? '').toLowerCase()) {
    case 'expired':
    case 'expired_qr':
      return 'qr_expired';
    case 'replay':
    case 'replay_qr':
      return 'qr_replay';
    case 'invalid_qr':
      return 'qr_unknown';
    default:
      return (code == null || code.isEmpty) ? 'qr_unknown' : code.toLowerCase();
  }
}

UiCopy resolveUiCopy(String? code) =>
    uiCopyMapping[normalizeUiCode(code)] ?? uiCopyMapping['qr_unknown']!;

ErrorModel mapQrReasonToError(String? code) {
  final normalized = normalizeUiCode(code);
  final copy = resolveUiCopy(normalized);
  return ErrorModel(code: normalized, message: copy.message);
}
