typedef ScanClock = DateTime Function();

class ScanSuppression {
  ScanSuppression({
    this.cooldown = const Duration(milliseconds: 1200),
    ScanClock? clock,
  }) : _clock = clock ?? DateTime.now;

  final Duration cooldown;
  final ScanClock _clock;
  String? _lastHash;
  DateTime? _lastAt;

  bool shouldAllow({required String hash, DateTime? now}) => !shouldSuppress(hash: hash, now: now);

  bool shouldSuppress({required String hash, DateTime? now}) {
    final current = now ?? _clock();
    final isSame = _lastHash == hash;
    final isCooldown = _lastAt != null && current.difference(_lastAt!) < cooldown;
    final suppressed = isSame && isCooldown;

    if (!suppressed) {
      _lastHash = hash;
      _lastAt = current;
    }

    return suppressed;
  }
}
