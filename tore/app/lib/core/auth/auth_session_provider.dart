import 'dart:async';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'auth_state_signal.dart';
import '../network/api_endpoints.dart';
import '../network/providers.dart';
import '../network/token_storage.dart';
import 'auth_models.dart';
import 'auth_repository.dart';

enum AuthStatus { unknown, loading, guest, authenticated, unauthenticated }

class AuthSessionState {
  final AuthStatus status;
  final AppUser? user;

  const AuthSessionState._(this.status, {this.user});

  const AuthSessionState.unknown() : this._(AuthStatus.unknown);
  const AuthSessionState.loading() : this._(AuthStatus.loading);
  const AuthSessionState.guest() : this._(AuthStatus.guest);
  const AuthSessionState.unauthenticated() : this._(AuthStatus.unauthenticated);
  const AuthSessionState.authenticated(AppUser? user) : this._(AuthStatus.authenticated, user: user);

  bool get isGuest => status == AuthStatus.guest;
  bool get isAuthed => status == AuthStatus.authenticated;
}

class AuthSessionNotifier extends StateNotifier<AuthSessionState> {
  AuthSessionNotifier(this.ref) : super(const AuthSessionState.unknown()) {
    _signalSub = AuthStateSignal.instance.onUnauthenticated.listen((_) {
      markUnauthenticated();
    });
    bootstrap();
  }

  final Ref ref;
  late final StreamSubscription<void> _signalSub;

  AuthRepository get _repo => AuthRepository(ref.read(apiClientProvider));
  TokenStorage get _storage => _repo.api.tokenStorage;

  Future<void> bootstrap() async {
    state = const AuthSessionState.loading();
    final token = await _storage.readToken();
    final guestMode = await _storage.readGuestModeEnabled();

    if (token != null && token.isNotEmpty) {
      final me = await _repo.tryMe();
      if (me == null) {
        state = const AuthSessionState.unauthenticated();
      } else {
        state = AuthSessionState.authenticated(me);
      }
      return;
    }
    state = guestMode ? const AuthSessionState.guest() : const AuthSessionState.unauthenticated();
  }

  Future<void> continueAsGuest() async {
    final existing = await _storage.readGuestDeviceId();
    final guestDeviceId = existing ?? _newGuestDeviceId();

    final response = await _repo.api.dio.post(
      ApiEndpoints.authGuest,
      data: {'display_name': 'Invité'},
      options: Options(extra: {'skipAuth': true}),
    );
    final data = (response.data is Map) ? (response.data as Map).cast<String, dynamic>() : const <String, dynamic>{};
    final token = (data['token'] ?? data['access_token'] ?? '').toString();
    if (token.isEmpty) {
      throw Exception('Réponse /auth/guest invalide (token manquant).');
    }

    await _storage.writeToken(token);
    await _storage.writeGuestModeEnabled(true);
    await _storage.writeGuestDeviceId(guestDeviceId);
    state = const AuthSessionState.guest();
  }

  Future<void> loginWithEmail({required String email, required String token}) async {
    final tokens = await _repo.verifyEmailOtp(email: email, code: token);
    await _completeLogin(tokens);
  }

  Future<void> loginWithGoogle() async {
    final googleSignIn = GoogleSignIn(scopes: const ['email']);
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
    if (guestId != null && guestId.isNotEmpty) {
      await _storage.writeGuestDeviceId(guestId);
    }
    state = const AuthSessionState.unauthenticated();
  }

  Future<void> markUnauthenticated() async {
    final guestId = await _storage.readGuestDeviceId();
    await _storage.clearAuthToken();
    if (guestId != null && guestId.isNotEmpty) {
      await _storage.writeGuestDeviceId(guestId);
    }
    state = const AuthSessionState.unauthenticated();
  }

  Future<void> _completeLogin(AuthTokens tokens) async {
    await _storage.writeTokens(accessToken: tokens.accessToken, refreshToken: tokens.refreshToken);
    await _storage.writeGuestModeEnabled(false);
    final me = await _repo.tryMe();
    state = AuthSessionState.authenticated(me);
  }

  String _newGuestDeviceId() {
    final r = Random();
    final stamp = DateTime.now().millisecondsSinceEpoch;
    return 'guest-$stamp-${r.nextInt(1 << 32).toRadixString(16)}';
  }

  @override
  void dispose() {
    _signalSub.cancel();
    super.dispose();
  }
}

final authSessionProvider = StateNotifierProvider<AuthSessionNotifier, AuthSessionState>((ref) {
  return AuthSessionNotifier(ref);
});
