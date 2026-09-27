import 'package:dio/dio.dart';

import 'api_exception.dart';
import '../../shared/utils/runtime_write_guard.dart';

class ToreUiErrorCopy {
  const ToreUiErrorCopy({
    required this.code,
    required this.title,
    required this.message,
    required this.ctaLabel,
  });

  final String code;
  final String title;
  final String message;
  final String ctaLabel;
}

const Map<String, ToreUiErrorCopy> toreUiErrorCopy = {
  'qr_unknown': ToreUiErrorCopy(
    code: 'qr_unknown',
    title: 'QR inconnu',
    message: 'Code non reconnu. Scanne un QR TORÈ valide ou utilise la saisie.',
    ctaLabel: 'Réessayer',
  ),
  'qr_expired': ToreUiErrorCopy(
    code: 'qr_expired',
    title: 'QR expiré',
    message: 'Ce QR a expiré. Demande un nouveau code à l’accueil.',
    ctaLabel: 'Demander un nouveau QR',
  ),
  'qr_replay': ToreUiErrorCopy(
    code: 'qr_replay',
    title: 'QR déjà utilisé',
    message: 'Ce QR a déjà servi. Utilise un QR non consommé.',
    ctaLabel: 'Utiliser un autre QR',
  ),
  'module_off': ToreUiErrorCopy(
    code: 'module_off',
    title: 'Module indisponible',
    message: 'Le module est coupé pour cet événement.',
    ctaLabel: 'Retour au hub',
  ),
  'event_paused': ToreUiErrorCopy(
    code: 'event_paused',
    title: 'Événement en pause',
    message: 'Actions temporairement gelées. Réessaie dans quelques minutes.',
    ctaLabel: 'Compris',
  ),
  'backend_down': ToreUiErrorCopy(
    code: 'backend_down',
    title: 'Service indisponible',
    message: 'Serveur occupé. Réessaie dans un instant.',
    ctaLabel: 'Réessayer',
  ),
  'unauthenticated': ToreUiErrorCopy(
    code: 'unauthenticated',
    title: 'Connexion requise',
    message: 'Connecte-toi pour accéder à cette section.',
    ctaLabel: 'Se connecter',
  ),
  'not_found': ToreUiErrorCopy(
    code: 'not_found',
    title: 'Introuvable',
    message: 'Cette ressource n’est pas disponible.',
    ctaLabel: 'Retour',
  ),
  'invalid_request': ToreUiErrorCopy(
    code: 'invalid_request',
    title: 'Demande invalide',
    message: 'La demande envoyée n’est pas acceptée.',
    ctaLabel: 'OK',
  ),
  'offline_write_blocked': ToreUiErrorCopy(
    code: 'offline_write_blocked',
    title: 'Action bloquée hors ligne',
    message: 'Repasse en ligne pour confirmer cette action.',
    ctaLabel: 'OK',
  ),
};

String normalizeToreErrorCode(String? rawCode) {
  final code = (rawCode ?? '').trim().toLowerCase();
  switch (code) {
    case 'expired':
    case 'expired_qr':
      return 'qr_expired';
    case 'replay':
    case 'replay_qr':
      return 'qr_replay';
    case 'invalid_qr':
      return 'qr_unknown';
    case 'unauthorized':
    case 'missing_token':
      return 'unauthenticated';
    case 'forbidden':
      return 'module_off';
    case 'event_not_found':
    case 'not_found':
      return 'not_found';
    case 'validation_error':
    case 'unprocessable_entity':
      return 'invalid_request';
    case 'read_only':
    case 'offline':
      return 'offline_write_blocked';
    default:
      return code.isEmpty ? 'qr_unknown' : code;
  }
}

ToreUiErrorCopy resolveToreUiError(String? rawCode) {
  final normalized = normalizeToreErrorCode(rawCode);
  return toreUiErrorCopy[normalized] ?? toreUiErrorCopy['qr_unknown']!;
}

class ErrorMapper {
  static int? retryAfterSeconds(Object e) {
    if (e is! DioException) return null;
    if (e.response?.statusCode != 429) return null;
    final data = e.response?.data;
    if (data is Map) {
      final sec = (data['retry_after_seconds'] as num?)?.toInt();
      if (sec != null && sec > 0) return sec;
    }
    final header = e.response?.headers.value('retry-after');
    final parsed = int.tryParse((header ?? '').trim());
    if (parsed != null && parsed > 0) return parsed;
    return null;
  }

  static String _mapReason(String? reason) {
    // Keep the active runtime semantics stable. Historical rebuild aliases are
    // exposed separately through normalizeToreErrorCode/resolveToreUiError.
    switch (reason) {
      case 'event_paused':
        return 'Event en pause. Réessaie dans un instant.';
      case 'module_off':
        return 'Fonction désactivée pour cet event.';
      case 'revoked':
        return 'Accès révoqué. Contacte un manager.';
      case 'rate_limited':
        return 'Trop de requêtes, réessaie.';
      case 'forbidden':
        return 'Action non autorisée.';
      case 'read_only':
        return 'Event en lecture seule pour le moment.';
      case 'frozen':
        return 'Les participations sont temporairement suspendues.';
      case 'insufficient_balance':
      case 'insuff_toggle':
        return 'Solde de Credits insuffisant.';
      case 'already_resolved':
        return 'Room déjà clôturée.';
      case 'expired':
      case 'invalid':
      case 'invalid_qr':
        return 'QR expiré.';
      default:
        return '';
    }
  }

  /// Converts any thrown error into a user-friendly message.
  static String message(Object e) {
    if (e is ApiException) {
      final detail = e.details;
      if (detail is Map && detail['detail'] is Map) {
        final reason = (detail['detail'] as Map)['reason']?.toString();
        final mapped = _mapReason(reason);
        if (mapped.isNotEmpty) return mapped;
      }
      return e.message;
    }

    if (e is DioException) {
      switch (e.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.receiveTimeout:
        case DioExceptionType.sendTimeout:
          return 'Délai dépassé. Vérifie ta connexion.';
        case DioExceptionType.connectionError:
          return 'Connexion impossible. Vérifie ta connexion.';
        case DioExceptionType.badCertificate:
          return 'Certificat TLS invalide.';
        case DioExceptionType.cancel:
          return 'Requête annulée.';
        case DioExceptionType.badResponse:
          final code = e.response?.statusCode;
          final data = e.response?.data;
          if (data is Map && data['detail'] is Map) {
            final reason = (data['detail'] as Map)['reason']?.toString();
            final mapped = _mapReason(reason);
            if (mapped.isNotEmpty) return mapped;
          }
          if (code == 401) {
            return 'Non authentifié. Connecte-toi pour continuer.';
          }
          if (code == 403) {
            return 'Accès refusé.';
          }
          if (code == 404) {
            return 'Ressource introuvable.';
          }
          if (code == 429) {
            final retryAfter = retryAfterSeconds(e);
            if (retryAfter != null) {
              return 'Trop de requêtes. Réessaie dans ${retryAfter}s.';
            }
            return 'Trop de requêtes. Attends quelques secondes puis réessaie.';
          }
          if (code != null && code >= 500) {
            return 'Serveur indisponible. Réessaie.';
          }
          return 'Erreur serveur ($code).';
        case DioExceptionType.unknown:
          return 'Erreur réseau. Réessaie.';
      }
    }

    return 'Une erreur est survenue.';
  }

  static bool isNotFound(Object e) {
    final code = _statusCode(e);
    return code == 404;
  }

  static bool isForbidden(Object e) {
    final code = _statusCode(e);
    return code == 401 || code == 403;
  }

  static bool isOffline(Object e) {
    if (e is DioException) {
      return e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout;
    }
    return false;
  }

  static String? runtimeBlockedMessage(Object e) {
    final reason = _reasonFromError(e);
    final normalized = normalizeRuntimeBlockReason(reason: reason);
    if (normalized == null) return null;
    return writeBlockedReasonMessage(normalized);
  }

  static String? _reasonFromError(Object e) {
    if (e is ApiException) {
      final detail = e.details;
      if (detail is Map && detail['detail'] is Map) {
        return (detail['detail'] as Map)['reason']?.toString();
      }
    }
    if (e is DioException) {
      final data = e.response?.data;
      if (data is Map && data['detail'] is Map) {
        return (data['detail'] as Map)['reason']?.toString();
      }
    }
    return null;
  }

  static int? _statusCode(Object e) {
    if (e is ApiException) return e.statusCode;
    if (e is DioException) {
      final wrapped = e.error;
      if (wrapped is ApiException) return wrapped.statusCode;
      return e.response?.statusCode;
    }
    return null;
  }
}
