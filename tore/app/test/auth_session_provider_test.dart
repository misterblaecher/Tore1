import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/core/auth/auth_session_provider.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  SharedPreferences.setMockInitialValues({});
  test('AuthSessionState transitions guest -> authenticated', () {
    const guest = AuthSessionState.guest();
    expect(guest.isGuest, true);
    expect(guest.isAuthed, false);

    const authed = AuthSessionState.authenticated(null);
    expect(authed.isAuthed, true);
    expect(authed.isGuest, false);
  });

  test('Provider boots in unknown or loading state', () {
    final container = ProviderContainer();
    final state = container.read(authSessionProvider);
    expect([AuthStatus.unknown, AuthStatus.loading], contains(state.status));
  });
}
