import '../config/app_environment.dart';
import 'api_client.dart';
import 'cache_store.dart';
import 'client_log.dart';

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

  factory RemoteConfigPayload.defaults(AppEnvironment environment) {
    return RemoteConfigPayload(
      modulesDefaultStates: const {},
      disableWritesGlobal: false,
      disableWritesMessage: 'Writes are temporarily frozen.',
      minSupportedBuild: null,
      minSupportedVersion: null,
      diagnosticsEnabled: environment != AppEnvironment.prod,
      fetchedAt: DateTime.now(),
      source: 'defaults',
    );
  }

  factory RemoteConfigPayload.fromJson(Map<String, dynamic> json,
      {required AppEnvironment environment, required String source}) {
    final modules =
        (json['modules_defaults'] as Map?)?.cast<String, dynamic>() ??
            const <String, dynamic>{};
    final minBuild =
        int.tryParse(json['min_supported_build']?.toString() ?? '');
    final minVersion = json['min_supported_version']?.toString();
    final diagnostics = json['diagnostics_enabled'];

    return RemoteConfigPayload(
      modulesDefaultStates: {
        for (final row in modules.entries) row.key: row.value == true,
      },
      disableWritesGlobal: json['disable_writes_global'] == true,
      disableWritesMessage:
          json['disable_writes_message']?.toString().trim().isNotEmpty == true
              ? json['disable_writes_message'].toString()
              : 'Writes are temporarily frozen.',
      minSupportedBuild: minBuild,
      minSupportedVersion:
          minVersion == null || minVersion.isEmpty ? null : minVersion,
      diagnosticsEnabled: diagnostics is bool
          ? diagnostics
          : environment != AppEnvironment.prod,
      fetchedAt: DateTime.now(),
      source: source,
    );
  }

  Map<String, dynamic> toJson() => {
        'modules_defaults': modulesDefaultStates,
        'disable_writes_global': disableWritesGlobal,
        'disable_writes_message': disableWritesMessage,
        'min_supported_build': minSupportedBuild,
        'min_supported_version': minSupportedVersion,
        'diagnostics_enabled': diagnosticsEnabled,
        'fetched_at': fetchedAt.toIso8601String(),
        'source': source,
      };
}

class RemoteConfigService {
  RemoteConfigService(
      {required ApiClient apiClient,
      required CacheStore cacheStore,
      required AppEnvironment environment})
      : _apiClient = apiClient,
        _cacheStore = cacheStore,
        _environment = environment;

  static const String cacheKey = 'remote_config:v1';
  static const Duration cacheTtl = Duration(minutes: 5);

  final ApiClient _apiClient;
  final CacheStore _cacheStore;
  final AppEnvironment _environment;

  Future<RemoteConfigPayload> load() async {
    final cached = await _cacheStore.loadJson(cacheKey, ttl: cacheTtl);
    try {
      final remote = await _apiClient.fetchRemoteConfig();
      final payload = RemoteConfigPayload.fromJson(remote,
          environment: _environment, source: 'remote');
      await _cacheStore.saveJson(cacheKey, payload.toJson());
      await ClientLog.instance.log('remote_config.load', {
        'source': 'remote',
        'disable_writes_global': payload.disableWritesGlobal
      });
      return payload;
    } catch (_) {
      if (cached != null) {
        final payload = RemoteConfigPayload.fromJson(cached.payload,
            environment: _environment, source: 'cache');
        await ClientLog.instance.log(
            'remote_config.load', {'source': 'cache', 'stale': cached.isStale});
        return payload;
      }
      final defaults = RemoteConfigPayload.defaults(_environment);
      await ClientLog.instance
          .log('remote_config.load', {'source': 'defaults'});
      return defaults;
    }
  }
}

class BuildInfo {
  const BuildInfo(
      {required this.semver,
      required this.buildNumber,
      required this.gitSha,
      required this.buildTime});

  final String semver;
  final int buildNumber;
  final String gitSha;
  final String buildTime;

  static BuildInfo fromEnvironment() {
    const semver = String.fromEnvironment('APP_VERSION', defaultValue: '1.0.0');
    const buildRaw = String.fromEnvironment('APP_BUILD', defaultValue: '1');
    const gitSha = String.fromEnvironment('GIT_SHA', defaultValue: 'unknown');
    const buildTime =
        String.fromEnvironment('BUILD_TIME', defaultValue: 'unknown');
    return BuildInfo(
      semver: semver,
      buildNumber: int.tryParse(buildRaw) ?? 1,
      gitSha: gitSha,
      buildTime: buildTime,
    );
  }
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
