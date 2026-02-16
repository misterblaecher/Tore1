import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/auth/auth_session_provider.dart';

void main() {
  test('AuthSessionState transitions guest -> authenticated', () {
    const guest = AuthSessionState.guest();
    expect(guest.isGuest, true);
    expect(guest.isAuthed, false);

    const authed = AuthSessionState.authenticated(null);
    expect(authed.isAuthed, true);
    expect(authed.isGuest, false);
  });

  test('Provider boots in loading state', () {
    final container = ProviderContainer();
    final state = container.read(authSessionProvider);
    expect(state.status, AuthStatus.loading);
  });
}
