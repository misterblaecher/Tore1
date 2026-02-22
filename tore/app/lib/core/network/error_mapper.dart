import 'package:dio/dio.dart';

import 'api_exception.dart';
import '../../shared/utils/runtime_write_guard.dart';

class ErrorMapper {
  static String _mapReason(String? reason) {
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
        return 'Trading temporairement gelé.';
      case 'insufficient_balance':
      case 'insuff_toggle':
        return 'Solde tickets insuffisant.';
      case 'already_resolved':
        return 'Marché déjà résolu.';
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
      final wrapped = e.error;
      if (wrapped is ApiException) {
        return wrapped.message;
      }

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
          if (code == 401) return 'Session expirée. Reconnexion en cours...';
          if (code == 403) return 'Accès refusé.';
          if (code == 404) return 'Ressource introuvable.';
          if (code == 429) return 'Trop de requêtes. Attends quelques secondes puis réessaie.';
          if (code != null && code >= 500) return 'Serveur indisponible. Réessaie.';
          return 'Erreur serveur ($code).';
        case DioExceptionType.unknown:
        default:
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
