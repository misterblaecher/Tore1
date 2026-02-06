import 'package:dio/dio.dart';

import 'api_exception.dart';

class ErrorMapper {
  /// Converts any thrown error into a user-friendly message.
  static String message(Object e) {
    if (e is ApiException) {
      // Backend provided message
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
          if (code == 401) return 'Session expirée. Reconnexion en cours...';
          if (code == 403) return 'Accès refusé.';
          if (code == 404) return 'Ressource introuvable.';
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
