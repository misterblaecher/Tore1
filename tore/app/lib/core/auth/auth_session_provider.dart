import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'auth_state_signal.dart';
import '../network/api_endpoints.dart';
import '../network/providers.dart';
import '../network/token_storage.dart';
import '../../shared/cache/cache_store.dart';
import 'auth_models.dart';
import 'auth_repository.dart';

enum AuthStatus {
  unknown,
  loading,
  guest,
  authenticated,
  unauthenticated,
  bootstrapError
}

class AuthSessionState {
  final AuthStatus status;
  final AppUser? user;
  final String? message;
  final bool isOfflineError;

  const AuthSessionState._(this.status,
      {this.user, this.message, this.isOfflineError = false});

  const AuthSessionState.unknown() : this._(AuthStatus.unknown);
  const AuthSessionState.loading() : this._(AuthStatus.loading);
  const AuthSessionState.guest() : this._(AuthStatus.guest);
  const AuthSessionState.unauthenticated({String? message})
      : this._(AuthStatus.unauthenticated, message: message);
  const AuthSessionState.authenticated(AppUser? user)
      : this._(AuthStatus.authenticated, user: user);
  const AuthSessionState.bootstrapError(String message,
      {bool isOfflineError = false})
      : this._(AuthStatus.bootstrapError,
            message: message, isOfflineError: isOfflineError);

  bool get isGuest => status == AuthStatus.guest;
  bool get isAuthed => status == AuthStatus.authenticated;
}

class AuthSessionNotifier extends StateNotifier<AuthSessionState> {
  AuthSessionNotifier(this.ref, {bool autoBootstrap = true})
      : super(const AuthSessionState.unknown()) {
    _signalSub = AuthStateSignal.instance.onUnauthenticated.listen((_) {
      markUnauthenticated();
    });
    if (autoBootstrap) bootstrap();
  }

  final Ref ref;
  late final StreamSubscription<void> _signalSub;

  AuthRepository get _repo => AuthRepository(ref.read(apiClientProvider));
  TokenStorage get _storage => _repo.api.tokenStorage;

  Future<void> bootstrap() async {
    state = const AuthSessionState.loading();
    try {
      debugPrint('[auth][bootstrap] start');
      debugPrint('[auth][bootstrap] load token');
      final token = await _storage.readToken();
      final guestMode = await _storage.readGuestModeEnabled();

      if (token == null || token.isEmpty) {
        debugPrint(
            '[auth][bootstrap] no token -> ${guestMode ? 'guest mode' : 'unauthenticated'}');
        state = guestMode
            ? const AuthSessionState.guest()
            : const AuthSessionState.unauthenticated();
        return;
      }

      debugPrint('[auth][bootstrap] token found -> /auth/me');
      final me = await _repo.tryMe().timeout(const Duration(seconds: 9),
          onTimeout: () => throw TimeoutException('auth bootstrap timeout'));
      if (me == null) {
        debugPrint('[auth][bootstrap] /auth/me unauthenticated');
        await markUnauthenticated();
      } else {
        debugPrint('[auth][bootstrap] /auth/me ok');
        state = AuthSessionState.authenticated(me);
      }
    } on TimeoutException {
      debugPrint('[auth][bootstrap] timeout');
      state = const AuthSessionState.bootstrapError(
          'Connexion impossible. Vérifie ton réseau.',
          isOfflineError: true);
    } on DioException catch (e) {
      final networkError = e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.sendTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.connectionError;
      final status = e.response?.statusCode;
      debugPrint('[auth][bootstrap] dio fail type=${e.type} status=$status');
      if (status == 401 || status == 403) {
        state = const AuthSessionState.unauthenticated();
        return;
      }
      final message = networkError
          ? 'Connexion impossible. Vérifie ton réseau.'
          : 'Session indisponible. Réessaie.';
      state = AuthSessionState.bootstrapError(message,
          isOfflineError: networkError);
    } catch (err) {
      debugPrint('[auth][bootstrap] fail $err');
      state = const AuthSessionState.bootstrapError(
          'Session indisponible. Réessaie.');
    }
  }

  Future<void> continueAsGuest() async {
    final existing = await _storage.readGuestDeviceId();
    final guestDeviceId = existing ?? _newGuestDeviceId();

    final response = await _repo.api.dio.post(
      ApiEndpoints.authGuest,
      data: {'display_name': 'Invité'},
      options: Options(extra: {'skipAuth': true}),
    );
    final data = (response.data is Map)
        ? (response.data as Map).cast<String, dynamic>()
        : const <String, dynamic>{};
    final token = (data['token'] ?? data['access_token'] ?? '').toString();
    if (token.isEmpty) {
      throw Exception('Réponse /auth/guest invalide (token manquant).');
    }

    await _storage.writeToken(token);
    await _storage.writeGuestModeEnabled(true);
    await _storage.writeGuestDeviceId(guestDeviceId);
    state = const AuthSessionState.guest();
  }

  Future<void> loginWithEmail(
      {required String email, required String token}) async {
    final tokens = await _repo.verifyEmailOtp(email: email, code: token);
    await _completeLogin(tokens);
  }

  Future<void> loginWithGoogle() async {
    const webClientId = String.fromEnvironment('TORE_GOOGLE_WEB_CLIENT_ID');
    if (kIsWeb && webClientId.isEmpty) {
      throw Exception(
          'Connexion Google non configurée sur cette version. Continue en invité ou par email.');
    }
    final googleSignIn = GoogleSignIn(
      scopes: const ['email'],
      clientId: kIsWeb ? webClientId : null,
    );
    final account = await googleSignIn.signIn();
    if (account == null) {
      throw Exception('Connexion Google annulée.');
    }
    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Google idToken indisponible.');
    }
    final tokens = await _repo.loginWithGoogle(idToken);
    await _completeLogin(tokens);
  }

  Future<void> refreshSession() async {
    await bootstrap();
  }

  Future<void> logout() async {
    final guestId = await _storage.readGuestDeviceId();
    await _storage.clear();
    await CacheStore().clearAllPrivate();
    if (guestId != null && guestId.isNotEmpty) {
      await _storage.writeGuestDeviceId(guestId);
    }
    state = const AuthSessionState.unauthenticated();
  }

  Future<void> markUnauthenticated() async {
    final guestId = await _storage.readGuestDeviceId();
    await _storage.clearAuthToken();
    await CacheStore().clearAllPrivate();
    if (guestId != null && guestId.isNotEmpty) {
      await _storage.writeGuestDeviceId(guestId);
    }
    state = const AuthSessionState.unauthenticated(
        message: 'Session expirée. Connecte-toi à nouveau.');
  }

  Future<void> _completeLogin(AuthTokens tokens) async {
    await _storage.writeTokens(
        accessToken: tokens.accessToken, refreshToken: tokens.refreshToken);
    await _storage.writeGuestModeEnabled(false);
    final me = await _repo.tryMe();
    if (me == null) {
      await markUnauthenticated();
      return;
    }
    state = AuthSessionState.authenticated(me);
  }

  String _newGuestDeviceId() {
    final r = Random();
    final stamp = DateTime.now().millisecondsSinceEpoch;
    return 'guest-$stamp-${r.nextInt(0x100000000).toRadixString(16)}';
  }

  @override
  void dispose() {
    _signalSub.cancel();
    super.dispose();
  }
}

final authSessionProvider =
    StateNotifierProvider<AuthSessionNotifier, AuthSessionState>((ref) {
  return AuthSessionNotifier(ref);
});
