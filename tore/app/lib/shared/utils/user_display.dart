import '../../core/auth/auth_models.dart';

/// Helpers to keep the UI "clean" (no raw UUID/hash displayed).
class UserDisplay {
  /// Returns a short stable code like "A9F3" from a user id/hash.
  static String shortCode(String id) {
    final clean = id.trim();
    if (clean.isEmpty) return '????';
    if (clean.length <= 4) return clean.toUpperCase();
    // Use the last 4 chars: stable and less "sensitive" than full id.
    return clean.substring(clean.length - 4).toUpperCase();
  }

  /// Returns a user-facing label.
  /// If display name is empty, we show "Invité".
  static String label(AppUser me) {
    final dn = me.displayName.trim();
    return dn.isEmpty ? 'Invité' : dn;
  }

  /// "Invité #A9F3" or "Alice #A9F3".
  static String labelWithCode(AppUser me) {
    return '${label(me)} #${shortCode(me.id)}';
  }
}
