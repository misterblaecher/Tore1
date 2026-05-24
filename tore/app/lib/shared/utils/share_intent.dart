import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

const kShareFallbackHintPrivate =
    'Connexion requise. Ouvre TORÈ → Entrer un code.';
const kShareFallbackHintOffline =
    'Hors-ligne : partage le lien, le code sera saisi dans TORÈ.';

class DevShareTraceItem {
  DevShareTraceItem(
      {required this.kind,
      required this.usedShortlink,
      required this.timestamp});
  final String kind;
  final bool usedShortlink;
  final DateTime timestamp;
}

class DevShareTrace {
  static final List<DevShareTraceItem> _items = <DevShareTraceItem>[];
  static List<DevShareTraceItem> get items =>
      List<DevShareTraceItem>.unmodifiable(_items);

  static void record({required String kind, required bool usedShortlink}) {
    if (!kDebugMode) return;
    _items.insert(
        0,
        DevShareTraceItem(
            kind: kind,
            usedShortlink: usedShortlink,
            timestamp: DateTime.now()));
    if (_items.length > 10) {
      _items.removeRange(10, _items.length);
    }
  }
}

class ShareIntentInput {
  const ShareIntentInput({
    this.shortUrl,
    this.openUrl,
    this.displaySuffix,
    this.copyValue,
    this.copyHint,
    this.title,
    this.subtitle,
    this.kind = 'generic',
  });

  final String? shortUrl;
  final String? openUrl;
  final String? displaySuffix;
  final String? copyValue;
  final String? copyHint;
  final String? title;
  final String? subtitle;
  final String kind;
}

class ShareIntentBuilder {
  ShareIntentBuilder(this.input);

  final ShareIntentInput input;

  String get primaryShareUrl {
    final short = (input.shortUrl ?? '').trim();
    if (short.isNotEmpty) return short;
    return (input.openUrl ?? '').trim();
  }

  String get shareText {
    final url = primaryShareUrl;
    final suffix = (input.displaySuffix ?? '').trim();
    if (suffix.isEmpty) return 'Ouvre TORÈ : $url';
    return 'Ouvre TORÈ : $url\nCode: $suffix';
  }

  Future<String> copyPrimary() async {
    final url = primaryShareUrl;
    if (url.isNotEmpty) {
      await Clipboard.setData(ClipboardData(text: url));
    }
    DevShareTrace.record(
        kind: input.kind,
        usedShortlink: (input.shortUrl ?? '').trim().isNotEmpty);
    return 'Lien copié';
  }

  Future<String> copyCodeOrHint() async {
    final value = (input.copyValue ?? '').trim();
    if (value.isNotEmpty) {
      await Clipboard.setData(ClipboardData(text: value));
      DevShareTrace.record(
          kind: input.kind,
          usedShortlink: (input.shortUrl ?? '').trim().isNotEmpty);
      return 'Code copié';
    }
    return (input.copyHint ?? '').trim().isNotEmpty
        ? input.copyHint!.trim()
        : kShareFallbackHintPrivate;
  }
}
