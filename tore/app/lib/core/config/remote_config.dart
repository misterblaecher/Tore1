import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../config/app_config.dart';
import '../../shared/cache/cache_providers.dart';
import '../../shared/cache/cache_store.dart';
import '../network/providers.dart';

class RemoteConfigPayload {
  const RemoteConfigPayload({
    required this.modulesDefaultStates,
    required this.disableWritesGlobal,
    required this.disableWritesMessage,
    required this.minSupportedBuild,
    required this.minSupportedVersion,
    required this.diagnosticsEnabled,
    required this.fetchedAt,
    required this.source,
  });

  final Map<String, bool> modulesDefaultStates;
  final bool disableWritesGlobal;
  final String disableWritesMessage;
  final int? minSupportedBuild;
  final String? minSupportedVersion;
  final bool diagnosticsEnabled;
  final DateTime fetchedAt;
  final String source;

  factory RemoteConfigPayload.defaults(String environmentName) {
    return RemoteConfigPayload(
      modulesDefaultStates: const {},
      disableWritesGlobal: false,
      disableWritesMessage: 'Les actions sont temporairement suspendues.',
      minSupportedBuild: null,
      minSupportedVersion: null,
      diagnosticsEnabled: !_isProduction(environmentName),
      fetchedAt: DateTime.now(),
      source: 'defaults',
    );
  }

  factory RemoteConfigPayload.fromJson(
    Map<String, dynamic> json, {
    required String environmentName,
    required String source,
    DateTime? fetchedAt,
  }) {
    final modules = (json['modules_defaults'] as Map?) ?? const {};
    final rawFetchedAt = json['fetched_at']?.toString();
    final parsedFetchedAt = rawFetchedAt == null
        ? null
        : DateTime.tryParse(rawFetchedAt)?.toLocal();
    final diagnostics = json['diagnostics_enabled'];
    final message = json['disable_writes_message']?.toString().trim();

    return RemoteConfigPayload(
      modulesDefaultStates: {
        for (final entry in modules.entries)
          entry.key.toString(): entry.value == true,
      },
      disableWritesGlobal: json['disable_writes_global'] == true,
      disableWritesMessage: message != null && message.isNotEmpty
          ? message
          : 'Les actions sont temporairement suspendues.',
      minSupportedBuild:
          int.tryParse(json['min_supported_build']?.toString() ?? ''),
      minSupportedVersion: _optionalString(json['min_supported_version']),
      diagnosticsEnabled: diagnostics is bool
          ? diagnostics
          : !_isProduction(environmentName),
      fetchedAt: fetchedAt ?? parsedFetchedAt ?? DateTime.now(),
      source: source,
    );
  }

  RemoteConfigPayload withSource(String nextSource) => RemoteConfigPayload(
        modulesDefaultStates: modulesDefaultStates,
        disableWritesGlobal: disableWritesGlobal,
        disableWritesMessage: disableWritesMessage,
        minSupportedBuild: minSupportedBuild,
        minSupportedVersion: minSupportedVersion,
        diagnosticsEnabled: diagnosticsEnabled,
        fetchedAt: fetchedAt,
        source: nextSource,
      );

  Map<String, dynamic> toJson() => {
        'modules_defaults': modulesDefaultStates,
        'disable_writes_global': disableWritesGlobal,
        'disable_writes_message': disableWritesMessage,
        'min_supported_build': minSupportedBuild,
        'min_supported_version': minSupportedVersion,
        'diagnostics_enabled': diagnosticsEnabled,
        'fetched_at': fetchedAt.toUtc().toIso8601String(),
      };
}

typedef RemoteConfigFetcher = Future<Map<String, dynamic>> Function();

class RemoteConfigService {
  RemoteConfigService({
    required RemoteConfigFetcher fetchRemoteConfig,
    required CacheStore cacheStore,
    required String environmentName,
    DateTime Function()? now,
  })  : _fetchRemoteConfig = fetchRemoteConfig,
        _cacheStore = cacheStore,
        _environmentName = environmentName,
        _now = now ?? DateTime.now;

  static const cacheKey = 'tore_cache.public.remote_config.v2';
  static const freshFor = Duration(minutes: 5);
  static const fallbackFor = Duration(hours: 24);

  final RemoteConfigFetcher _fetchRemoteConfig;
  final CacheStore _cacheStore;
  final String _environmentName;
  final DateTime Function() _now;

  Future<RemoteConfigPayload> load({bool forceRefresh = false}) async {
    final cachedJson = await _cacheStore.getJson(cacheKey);
    final cached = cachedJson == null
        ? null
        : RemoteConfigPayload.fromJson(
            cachedJson,
            environmentName: _environmentName,
            source: 'cache',
          );
    final age = cached == null ? null : _now().difference(cached.fetchedAt);

    if (!forceRefresh &&
        cached != null &&
        age != null &&
        !age.isNegative &&
        age <= freshFor) {
      return cached.withSource('cache_fresh');
    }

    try {
      final remoteJson = await _fetchRemoteConfig();
      final remote = RemoteConfigPayload.fromJson(
        remoteJson,
        environmentName: _environmentName,
        source: 'remote',
        fetchedAt: _now(),
      );
      await _cacheStore.setJson(cacheKey, remote.toJson(), ttl: fallbackFor);
      return remote;
    } catch (_) {
      if (cached != null &&
          age != null &&
          !age.isNegative &&
          age <= fallbackFor) {
        return cached.withSource('cache_stale');
      }
      return RemoteConfigPayload.defaults(_environmentName);
    }
  }
}

class BuildInfo {
  const BuildInfo({required this.semver, required this.buildNumber});

  final String semver;
  final int buildNumber;

  factory BuildInfo.fromEnvironment() {
    const semver = String.fromEnvironment('APP_VERSION', defaultValue: '1.0.0');
    const buildRaw = String.fromEnvironment('APP_BUILD', defaultValue: '1');
    return BuildInfo(
      semver: semver,
      buildNumber: int.tryParse(buildRaw) ?? 1,
    );
  }
}

bool requiresRemoteUpdate(RemoteConfigPayload config, BuildInfo build) {
  final minBuild = config.minSupportedBuild;
  if (minBuild != null && build.buildNumber < minBuild) return true;
  final minVersion = config.minSupportedVersion;
  return minVersion != null && isBelowMinVersion(build.semver, minVersion);
}

bool isBelowMinVersion(String currentVersion, String minVersion) {
  List<int> parse(String value) {
    final core = value.split('-').first.split('+').first;
    final parts = core.split('.');
    return [
      int.tryParse(parts.isNotEmpty ? parts[0] : '0') ?? 0,
      int.tryParse(parts.length > 1 ? parts[1] : '0') ?? 0,
      int.tryParse(parts.length > 2 ? parts[2] : '0') ?? 0,
    ];
  }

  final current = parse(currentVersion);
  final minimum = parse(minVersion);
  for (var i = 0; i < 3; i++) {
    if (current[i] < minimum[i]) return true;
    if (current[i] > minimum[i]) return false;
  }
  return false;
}

final remoteConfigServiceProvider = Provider<RemoteConfigService>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  final appConfig = ref.watch(appConfigProvider);
  final cache = ref.watch(cacheStoreProvider);
  return RemoteConfigService(
    cacheStore: cache,
    environmentName: appConfig.environmentName,
    fetchRemoteConfig: () async {
      final response = await apiClient.dio.get(
        '/mobile/remote-config',
        options: Options(extra: const {'skipRetry': true}),
      );
      return Map<String, dynamic>.from(response.data as Map);
    },
  );
});

final remoteConfigProvider = FutureProvider<RemoteConfigPayload>((ref) async {
  return ref.watch(remoteConfigServiceProvider).load();
});

final remoteWritesDisabledProvider = Provider<bool>((ref) {
  return ref.watch(remoteConfigProvider).asData?.value.disableWritesGlobal ??
      false;
});

final remoteWriteMessageProvider = Provider<String?>((ref) {
  final config = ref.watch(remoteConfigProvider).asData?.value;
  if (config == null || !config.disableWritesGlobal) return null;
  return config.disableWritesMessage;
});

String? _optionalString(Object? value) {
  final raw = value?.toString().trim();
  return raw == null || raw.isEmpty || raw.toLowerCase() == 'null' ? null : raw;
}

bool _isProduction(String environmentName) {
  final normalized = environmentName.trim().toLowerCase();
  return normalized == 'prod' || normalized == 'production';
}
