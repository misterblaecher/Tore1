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

class EmailRateLimitException implements Exception {
  final int retryAfterSeconds;

  const EmailRateLimitException(this.retryAfterSeconds);
}

class EmailAuthException implements Exception {
  final String code;

  const EmailAuthException(this.code);
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
      if (statusCode == 401) return null;
      rethrow;
    }
  }

  Future<AuthTokens> loginWithGoogle(String idToken) async {
    final r =
        await api.dio.post(ApiEndpoints.authGoogle, data: {'idToken': idToken});
    return _parseTokens(r.data);
  }

  Future<EmailRequestResult> requestEmailOtp(String email) async {
    try {
      final r = await api.dio.post(
        ApiEndpoints.authEmailRequestOtp,
        data: {'email': email},
        options: Options(extra: {'skipRetry': true}),
      );
      final data = (r.data is Map)
          ? (r.data as Map).cast<String, dynamic>()
          : const <String, dynamic>{};
      final devToken =
          (data['otp_debug'] ?? data['devToken'] ?? data['code'])?.toString();
      return EmailRequestResult(
          devToken: devToken == null || devToken.isEmpty ? null : devToken);
    } on DioException catch (e) {
      final reason = _extractReason(e.response?.data);
      if (e.response?.statusCode == 429 || reason == 'rate_limited') {
        final data = (e.response?.data is Map)
            ? (e.response!.data as Map).cast<String, dynamic>()
            : const <String, dynamic>{};
        final nestedDetail = (data['detail'] is Map)
            ? (data['detail'] as Map).cast<String, dynamic>()
            : const <String, dynamic>{};
        final retryAfterFromBody =
            (nestedDetail['retry_after_seconds'] as num?)?.toInt() ??
                (data['retry_after_seconds'] as num?)?.toInt();
        final retryAfterFromHeader = int.tryParse(
            (e.response?.headers.value('retry-after') ?? '').trim());
        throw EmailRateLimitException(
            (retryAfterFromBody ?? retryAfterFromHeader ?? 30).clamp(1, 600));
      }
      if (reason != null) throw EmailAuthException(reason);
      rethrow;
    }
  }

  Future<AuthTokens> verifyEmailOtp(
      {required String email, required String code}) async {
    try {
      final r = await api.dio.post(ApiEndpoints.authEmailVerifyOtp,
          data: {'email': email, 'code': code});
      return _parseTokens(r.data);
    } on DioException catch (e) {
      final reason = _extractReason(e.response?.data);
      if (e.response?.statusCode == 429 || reason == 'too_many_attempts') {
        throw const EmailAuthException('too_many_attempts');
      }
      if (reason != null) throw EmailAuthException(reason);
      rethrow;
    }
  }

  Future<void> upgradeGuest({required String guestDeviceId}) async {
    await api.dio.post(ApiEndpoints.authUpgradeGuest,
        data: {'guest_device_id': guestDeviceId});
  }

  Future<RoleUpgradeRequest> requestRoleUpgrade(
      {required AccountMode mode, required String code}) async {
    final r = await api.dio.post(ApiEndpoints.authRoleRequestUpgrade, data: {
      'requested_mode': accountModeToJson(mode),
      'code': code,
    });
    final data = (r.data as Map).cast<String, dynamic>();
    return RoleUpgradeRequest.fromJson(
        (data['request'] as Map).cast<String, dynamic>());
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
      if (showIdentityToStaff != null)
        'show_identity_to_staff': showIdentityToStaff,
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
    final access =
        (data['access_token'] ?? data['accessToken'] ?? data['token'] ?? '')
            .toString();
    final refresh =
        (data['refresh_token'] ?? data['refreshToken'] ?? '').toString();
    if (access.isEmpty) {
      throw Exception('Réponse auth invalide: token manquant');
    }
    return AuthTokens(
        accessToken: access, refreshToken: refresh.isEmpty ? access : refresh);
  }

  String? _extractReason(dynamic payload) {
    if (payload is! Map) return null;
    final map = payload.cast<String, dynamic>();
    final detail = map['detail'];
    if (detail is Map) {
      final d = detail.cast<String, dynamic>();
      return (d['reason'] ?? d['code'])?.toString();
    }
    return (map['reason'] ?? map['code'])?.toString();
  }
}
