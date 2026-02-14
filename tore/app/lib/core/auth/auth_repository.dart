import 'package:dio/dio.dart';

import '../network/api_client.dart';
import '../network/api_endpoints.dart'; // ✅ AJOUTE ÇA
import 'auth_models.dart';

class AuthRepository {
  final ApiClient api;

  AuthRepository(this.api);

  /// Assure qu'un token guest existe (persisté). Si le token est invalide (401),
  /// on en recrée un automatiquement.
  Future<AppUser> ensureGuestSession({String? displayName}) async {
    final token = await api.tokenStorage.readToken();
    if (token != null && token.isNotEmpty) {
      final me = await _tryMe();
      if (me != null) return me;
      await api.tokenStorage.clear();
    }

    // Créer un guest
      final r = await api.dio.post(
        ApiEndpoints.authGuest,
        data: {
          if (displayName != null) 'display_name': displayName,
        },
      );

    final data = (r.data as Map).cast<String, dynamic>();
    final newToken = (data['token'] ?? '').toString();
    if (newToken.isEmpty) {
      throw Exception('Token manquant dans /auth/guest');
    }
    await api.tokenStorage.writeToken(newToken);

    final userJson =
        (data['user'] as Map?)?.cast<String, dynamic>() ?? <String, dynamic>{};
    return AppUser.fromJson(userJson);
  }

  Future<AppUser> getMe() async {
    final r = await api.dio.get(ApiEndpoints.authMe);
    final data = (r.data as Map).cast<String, dynamic>();
    return AppUser.fromJson(data);
  }

  Future<AppUser> patchMe({
    String? displayName,
    String? avatarUrl,
    String? addressText,
    bool? showAddress,
    bool? showAvatar,
    bool? showIdentityToStaff,
  }) async {
    final payload = <String, dynamic>{
      if (displayName != null) 'display_name': displayName,
      if (avatarUrl != null) 'avatar_url': avatarUrl,
      if (addressText != null) 'address_text': addressText,
      if (showAddress != null) 'show_address': showAddress,
      if (showAvatar != null) 'show_avatar': showAvatar,
      if (showIdentityToStaff != null) 'show_identity_to_staff': showIdentityToStaff,
    };

    final r = await api.dio.patch(ApiEndpoints.authMe, data: payload);
    final data = (r.data as Map).cast<String, dynamic>();
    return AppUser.fromJson(data);
  }

  Future<AppUser?> _tryMe() async {
    try {
      return await getMe();
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) return null;
      rethrow;
    }
  }
}
