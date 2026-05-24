import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';
import '../../config/app_config.dart';

class TokenStorage {
  static const _accessKey = 'auth_token';
  static const _refreshKey = 'auth_refresh_token';
  static const _guestDeviceIdKey = 'guest_device_id';
  static const _guestModeKey = 'guest_mode_enabled';

  Future<void> writeToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, token);
    if (AppConfig.enableAuthLogs) {
      debugPrint('💾 ACCESS TOKEN SAVED: ${token.substring(0, 8)}...');
    }
  }

  Future<void> writeTokens(
      {required String accessToken, required String refreshToken}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, accessToken);
    await prefs.setString(_refreshKey, refreshToken);
    if (AppConfig.enableAuthLogs) {
      debugPrint('💾 TOKENS SAVED');
    }
  }

  Future<String?> readToken() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_accessKey);
    if (AppConfig.enableAuthLogs) {
      debugPrint(token == null
          ? '📭 ACCESS TOKEN READ: null'
          : '📬 ACCESS TOKEN READ: ${token.substring(0, 8)}...');
    }
    return token;
  }

  Future<String?> readRefreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshKey);
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
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
    await prefs.remove(_guestModeKey);
    if (AppConfig.enableAuthLogs) {
      debugPrint('🗑️ TOKENS CLEARED');
    }
  }

  Future<void> clearAuthToken() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }

  Future<void> clearToken() => clear();
}
