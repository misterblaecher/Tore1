String pickShareUrl({String? shortUrl, String? webUrl, String? openUrl}) {
  final candidates = [shortUrl, webUrl, openUrl];
  for (final value in candidates) {
    final text = (value ?? '').trim();
    if (text.isNotEmpty) return text;
  }
  return '';
}

String shareText({required String url, String? fallbackSuffix}) {
  final suffix = (fallbackSuffix ?? '').trim();
  if (suffix.isEmpty) {
    return 'Ouvre TORÈ : $url';
  }
  return 'Ouvre TORÈ : $url\nSinon: ouvre TORÈ → Entrer un code → $suffix';
}
