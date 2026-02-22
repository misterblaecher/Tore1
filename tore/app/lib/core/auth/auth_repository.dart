import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

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
  final int expiresInSeconds;
  final int resendCooldownSeconds;

  const EmailRequestResult({this.devToken, this.expiresInSeconds = 600, this.resendCooldownSeconds = 30});
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

  Future<EmailRequestResult> requestEmailOtp(String email) async {
    try {
      final r = await api.dio.post(ApiEndpoints.authEmailRequestOtp, data: {'email': email});
      if (kDebugMode) {
        debugPrint('[auth][otp] response status=${r.statusCode} body=${r.data}');
      }
      final data = (r.data is Map) ? (r.data as Map).cast<String, dynamic>() : const <String, dynamic>{};
      return EmailRequestResult(
        devToken: (data['code'] ?? data['token'] ?? data['dev_token'])?.toString(),
        expiresInSeconds: (data['expires_in_seconds'] as num?)?.toInt() ?? 600,
        resendCooldownSeconds: (data['resend_cooldown_seconds'] as num?)?.toInt() ?? 30,
      );
    } on DioException catch (e) {
      if (kDebugMode) {
        debugPrint('[auth][otp] response status=${e.response?.statusCode} body=${e.response?.data}');
      }
      rethrow;
    }
  }

  Future<AuthTokens> verifyEmailOtp({required String email, required String code}) async {
    final r = await api.dio.post(
      ApiEndpoints.authEmailVerifyOtp,
      data: {'email': email, 'code': code},
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
    String? bio,
    String? visibility,
    bool? showIdentityInBar,
  }) async {
    final payload = <String, dynamic>{
      if (displayName != null) 'display_name': displayName,
      if (avatarUrl != null) 'avatar_url': avatarUrl,
      if (addressText != null) 'address_text': addressText,
      if (showAddress != null) 'show_address': showAddress,
      if (showAvatar != null) 'show_avatar': showAvatar,
      if (showIdentityToStaff != null) 'show_identity_to_staff': showIdentityToStaff,
      if (bio != null) 'bio': bio,
      if (visibility != null) 'visibility': visibility,
      if (showIdentityInBar != null) 'show_identity_in_bar': showIdentityInBar,
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
