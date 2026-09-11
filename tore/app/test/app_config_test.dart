import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/foundation.dart';
import 'package:tore/config/app_config.dart';

void main() {
  test('production requires an explicit HTTPS API URL', () {
    expect(() => AppConfig.resolve(flavor: 'prod'), throwsFormatException);
    expect(() => AppConfig.resolve(environment: 'production'), throwsFormatException);
    for (final url in ['http://api.tore.test', 'https://localhost', 'https://127.0.0.1', 'https://user:password@api.tore.test', 'https://api.tore.test?token=secret']) {
      expect(() => AppConfig.resolve(flavor: 'prod', primaryBaseUrl: url), throwsFormatException);
    }
  });

  test('flavor determines environment unless explicitly overridden', () {
    final config = AppConfig.resolve(flavor: 'prod', primaryBaseUrl: ' https://api.tore.test/ ');
    expect(config.environmentName, 'prod');
    expect(config.apiBaseUrl, 'https://api.tore.test');
  });

  test('local development and API_BASE_URL compatibility remain supported', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    expect(AppConfig.resolve(flavor: 'dev').apiBaseUrl, 'http://10.0.2.2:8000');
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    expect(AppConfig.resolve(flavor: 'dev').apiBaseUrl, 'http://localhost:8000');
    debugDefaultTargetPlatformOverride = null;
    expect(AppConfig.resolve(flavor: 'dev', compatBaseUrl: 'http://localhost:9000/').apiBaseUrl, 'http://localhost:9000');
  });
}
