import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';
import '../../config/app_config.dart';

class TokenStorage {
  static const _key = 'auth_token';

  Future<void> writeToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, token);
    if (AppConfig.enableAuthLogs) {
      debugPrint('💾 TOKEN SAVED: ${token.substring(0, 8)}...');
    }
  }

  Future<String?> readToken() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_key);
    if (AppConfig.enableAuthLogs) {
      debugPrint(token == null
          ? '📭 TOKEN READ: null'
          : '📬 TOKEN READ: ${token.substring(0, 8)}...');
    }
    return token;
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
    if (AppConfig.enableAuthLogs) {
      debugPrint('🗑️ TOKEN CLEARED');
    }
  }

  // ✅ compat avec ton code (tu utilises tokenStorage.clear())
  Future<void> clearToken() => clear();
}
