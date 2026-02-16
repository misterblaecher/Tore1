import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../network/providers.dart';
import '../network/token_storage.dart';
import 'auth_models.dart';
import 'auth_repository.dart';

enum AuthStatus { loading, guest, authenticated, unauthenticated }

class AuthSessionState {
  final AuthStatus status;
  final AppUser? user;

  const AuthSessionState._(this.status, {this.user});

  const AuthSessionState.loading() : this._(AuthStatus.loading);
  const AuthSessionState.guest() : this._(AuthStatus.guest);
  const AuthSessionState.unauthenticated() : this._(AuthStatus.unauthenticated);
  const AuthSessionState.authenticated(AppUser? user) : this._(AuthStatus.authenticated, user: user);

  bool get isGuest => status == AuthStatus.guest;
  bool get isAuthed => status == AuthStatus.authenticated;
}

class AuthSessionNotifier extends StateNotifier<AuthSessionState> {
  AuthSessionNotifier(this.ref) : super(const AuthSessionState.loading()) {
    bootstrap();
  }

  final Ref ref;

  AuthRepository get _repo => AuthRepository(ref.read(apiClientProvider));
  TokenStorage get _storage => _repo.api.tokenStorage;

  Future<void> bootstrap() async {
    state = const AuthSessionState.loading();
    final token = await _storage.readToken();
    final guestMode = await _storage.readGuestModeEnabled();

    if (token != null && token.isNotEmpty) {
      final me = await _repo.tryMe();
      state = AuthSessionState.authenticated(me);
      return;
    }
    state = guestMode ? const AuthSessionState.guest() : const AuthSessionState.unauthenticated();
  }

  Future<void> continueAsGuest() async {
    final existing = await _storage.readGuestDeviceId();
    await _storage.writeGuestModeEnabled(true);
    await _storage.writeGuestDeviceId(existing ?? _newGuestDeviceId());
    state = const AuthSessionState.guest();
  }

  Future<void> loginWithEmail({required String email, required String token}) async {
    final tokens = await _repo.verifyEmailLink(email: email, token: token);
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

  Future<void> logout() async {
    final guestId = await _storage.readGuestDeviceId();
    await _storage.clear();
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
}

final authSessionProvider = StateNotifierProvider<AuthSessionNotifier, AuthSessionState>((ref) {
  return AuthSessionNotifier(ref);
});
