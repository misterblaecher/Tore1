import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/core/config/remote_config.dart';
import 'package:tore/shared/cache/cache_store.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('parses remote safety flags and minimum version requirements', () {
    final payload = RemoteConfigPayload.fromJson(
      {
        'modules_defaults': {'menu': true, 'wallet': false},
        'disable_writes_global': true,
        'disable_writes_message': 'Maintenance en cours',
        'min_supported_build': 12,
        'min_supported_version': '1.4.0',
        'diagnostics_enabled': false,
      },
      environmentName: 'prod',
      source: 'remote',
    );

    expect(payload.modulesDefaultStates, {'menu': true, 'wallet': false});
    expect(payload.disableWritesGlobal, isTrue);
    expect(payload.disableWritesMessage, 'Maintenance en cours');
    expect(payload.minSupportedBuild, 12);
    expect(payload.minSupportedVersion, '1.4.0');
    expect(payload.diagnosticsEnabled, isFalse);
  });

  test('version comparison handles semver core and build minimum', () {
    final config = RemoteConfigPayload.fromJson(
      {
        'min_supported_build': 10,
        'min_supported_version': '1.2.3',
      },
      environmentName: 'dev',
      source: 'test',
    );

    expect(
      requiresRemoteUpdate(
          config, const BuildInfo(semver: '1.2.2', buildNumber: 20)),
      isTrue,
    );
    expect(
      requiresRemoteUpdate(
          config, const BuildInfo(semver: '1.2.3', buildNumber: 9)),
      isTrue,
    );
    expect(
      requiresRemoteUpdate(
          config, const BuildInfo(semver: '1.3.0', buildNumber: 10)),
      isFalse,
    );
  });

  test('falls back safely to cached config when refresh fails', () async {
    final cache = CacheStore();
    final firstNow = DateTime(2026, 9, 11, 10);
    final initial = RemoteConfigService(
      cacheStore: cache,
      environmentName: 'dev',
      now: () => firstNow,
      fetchRemoteConfig: () async => {
        'disable_writes_global': true,
        'disable_writes_message': 'Freeze test',
        'diagnostics_enabled': true,
      },
    );

    final remote = await initial.load(forceRefresh: true);
    expect(remote.source, 'remote');
    expect(remote.disableWritesGlobal, isTrue);

    final fallback = RemoteConfigService(
      cacheStore: cache,
      environmentName: 'dev',
      now: () => firstNow.add(const Duration(minutes: 10)),
      fetchRemoteConfig: () async => throw StateError('network down'),
    );

    final cached = await fallback.load(forceRefresh: true);
    expect(cached.source, 'cache_stale');
    expect(cached.disableWritesGlobal, isTrue);
    expect(cached.disableWritesMessage, 'Freeze test');
  });

  test('defaults fail open for reads but keep diagnostics off in prod', () async {
    final service = RemoteConfigService(
      cacheStore: CacheStore(),
      environmentName: 'prod',
      fetchRemoteConfig: () async => throw StateError('network down'),
    );

    final payload = await service.load(forceRefresh: true);
    expect(payload.source, 'defaults');
    expect(payload.disableWritesGlobal, isFalse);
    expect(payload.diagnosticsEnabled, isFalse);
  });
}
