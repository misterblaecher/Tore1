import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/network/token_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('stores and reads access/refresh tokens', () async {
    final storage = TokenStorage();
    await storage.writeTokens(
        accessToken: 'access-123', refreshToken: 'refresh-456');

    expect(await storage.readToken(), 'access-123');
    expect(await storage.readRefreshToken(), 'refresh-456');
  });

  test('clearAuthToken removes access and refresh but keeps guest mode data',
      () async {
    final storage = TokenStorage();
    await storage.writeTokens(
        accessToken: 'access-123', refreshToken: 'refresh-456');
    await storage.writeGuestDeviceId('guest-uuid-1');
    await storage.writeGuestModeEnabled(true);

    await storage.clearAuthToken();

    expect(await storage.readToken(), isNull);
    expect(await storage.readRefreshToken(), isNull);
    expect(await storage.readGuestDeviceId(), 'guest-uuid-1');
    expect(await storage.readGuestModeEnabled(), isTrue);
  });

  test('persists guest_device_id', () async {
    final storage = TokenStorage();
    await storage.writeGuestDeviceId('guest-uuid-1');

    expect(await storage.readGuestDeviceId(), 'guest-uuid-1');
  });

  test('tokens are never persisted in SharedPreferences', () async {
    final storage = TokenStorage();
    await storage.writeTokens(
        accessToken: 'secure-access', refreshToken: 'secure-refresh');

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('auth_token'), isNull);
    expect(prefs.getString('auth_refresh_token'), isNull);
    expect(await storage.readToken(), 'secure-access');
    expect(await storage.readRefreshToken(), 'secure-refresh');
  });

  test('legacy SharedPreferences token is migrated and removed', () async {
    SharedPreferences.setMockInitialValues({'auth_token': 'legacy-access'});
    FlutterSecureStorage.setMockInitialValues({});
    final storage = TokenStorage();

    expect(await storage.readToken(), 'legacy-access');
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('auth_token'), isNull);
    expect(await storage.readToken(), 'legacy-access');
  });
}
