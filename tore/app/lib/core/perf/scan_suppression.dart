class ScanSuppression {
  ScanSuppression({this.cooldown = const Duration(milliseconds: 1200)});

  final Duration cooldown;
  String? _lastHash;
  DateTime? _lastAt;

  bool shouldSuppress({required String hash, required DateTime now}) {
    final isSame = _lastHash == hash;
    final isCooldown = _lastAt != null && now.difference(_lastAt!) < cooldown;
    _lastHash = hash;
    _lastAt = now;
    return isSame && isCooldown;
  }
}
