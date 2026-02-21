import 'package:dio/dio.dart';

import '../network/api_client.dart';
import '../network/api_endpoints.dart';
import 'auth_models.dart';

class AuthTokens {
  final String accessToken;
  final String refreshToken;

  const AuthTokens({required this.accessToken, required this.refreshToken});
}

class EmailRequestResult {
  final String? devToken;

  const EmailRequestResult({this.devToken});
}

class AuthRepository {
  final ApiClient api;

  AuthRepository(this.api);

  Future<AppUser> getMe() async {
    final r = await api.dio.get(ApiEndpoints.authMe);
    final data = (r.data as Map).cast<String, dynamic>();
    return AppUser.fromJson(data);
  }

  Future<AppUser?> tryMe() async {
    try {
      return await getMe();
    } on DioException catch (e) {
      final statusCode = e.response?.statusCode;
      if (statusCode == 401 || statusCode == 403) return null;
      rethrow;
    }
  }

  Future<AuthTokens> loginWithGoogle(String idToken) async {
    final r = await api.dio.post(ApiEndpoints.authGoogle, data: {'idToken': idToken});
    return _parseTokens(r.data);
  }

  Future<EmailRequestResult> requestEmailLink(String email) async {
    final r = await api.dio.post(ApiEndpoints.authEmailRequestLink, data: {'email': email});
    final data = (r.data is Map) ? (r.data as Map).cast<String, dynamic>() : const <String, dynamic>{};
    return EmailRequestResult(devToken: (data['token'] ?? data['dev_token'])?.toString());
  }

  Future<AuthTokens> verifyEmailLink({required String email, required String token}) async {
    final r = await api.dio.post(
      ApiEndpoints.authEmailVerifyLink,
      data: {'email': email, 'token': token},
    );
    return _parseTokens(r.data);
  }

  Future<void> upgradeGuest({required String guestDeviceId}) async {
    await api.dio.post(ApiEndpoints.authUpgradeGuest, data: {'guest_device_id': guestDeviceId});
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

  AuthTokens _parseTokens(dynamic rawData) {
    final data = (rawData as Map).cast<String, dynamic>();
    final access = (data['access_token'] ?? data['accessToken'] ?? '').toString();
    final refresh = (data['refresh_token'] ?? data['refreshToken'] ?? '').toString();
    if (access.isEmpty || refresh.isEmpty) {
      throw Exception('Réponse auth invalide: tokens manquants');
    }
    return AuthTokens(accessToken: access, refreshToken: refresh);
  }
}
