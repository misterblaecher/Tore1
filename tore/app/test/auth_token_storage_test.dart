import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tore/core/network/token_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('stores and reads access/refresh tokens', () async {
    final storage = TokenStorage();
    await storage.writeTokens(accessToken: 'access-123', refreshToken: 'refresh-456');

    expect(await storage.readToken(), 'access-123');
    expect(await storage.readRefreshToken(), 'refresh-456');
  });

  test('persists guest_device_id', () async {
    final storage = TokenStorage();
    await storage.writeGuestDeviceId('guest-uuid-1');

    expect(await storage.readGuestDeviceId(), 'guest-uuid-1');
  });
}
