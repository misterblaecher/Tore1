import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class TokenStorage {
  static const _accessKey = 'auth_token';
  static const _refreshKey = 'auth_refresh_token';
  static const _guestDeviceIdKey = 'guest_device_id';
  static const _guestModeKey = 'guest_mode_enabled';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  Future<void> writeToken(String token) async {
    await _secureStorage.write(key: _accessKey, value: token);
    await _removeLegacyTokenKeys();
  }

  Future<void> writeTokens(
      {required String accessToken, required String refreshToken}) async {
    await _secureStorage.write(key: _accessKey, value: accessToken);
    await _secureStorage.write(key: _refreshKey, value: refreshToken);
    await _removeLegacyTokenKeys();
  }

  Future<String?> readToken() async {
    return _readAndMigrate(_accessKey);
  }

  Future<String?> readRefreshToken() async {
    return _readAndMigrate(_refreshKey);
  }

  Future<void> writeGuestDeviceId(String id) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_guestDeviceIdKey, id);
  }

  Future<String?> readGuestDeviceId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_guestDeviceIdKey);
  }

  Future<void> writeGuestModeEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_guestModeKey, enabled);
  }

  Future<bool> readGuestModeEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_guestModeKey) ?? false;
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await _secureStorage.delete(key: _accessKey);
    await _secureStorage.delete(key: _refreshKey);
    await _removeLegacyTokenKeys(prefs);
    await prefs.remove(_guestModeKey);
  }

  Future<void> clearAuthToken() async {
    final prefs = await SharedPreferences.getInstance();
    await _secureStorage.delete(key: _accessKey);
    await _secureStorage.delete(key: _refreshKey);
    await _removeLegacyTokenKeys(prefs);
  }

  Future<void> clearToken() => clear();

  Future<String?> _readAndMigrate(String key) async {
    final secureValue = await _secureStorage.read(key: key);
    if (secureValue != null && secureValue.isNotEmpty) return secureValue;
    final prefs = await SharedPreferences.getInstance();
    final legacyValue = prefs.getString(key);
    if (legacyValue != null && legacyValue.isNotEmpty) {
      await _secureStorage.write(key: key, value: legacyValue);
      await prefs.remove(key);
      return legacyValue;
    }
    return null;
  }

  Future<void> _removeLegacyTokenKeys([SharedPreferences? existing]) async {
    final prefs = existing ?? await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }
}
