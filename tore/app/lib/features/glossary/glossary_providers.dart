import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/network_state_provider.dart';
import 'package:tore/features/glossary/glossary_cache.dart';
import 'package:tore/features/glossary/glossary_models.dart';
import 'package:tore/state.dart';

class GlossaryFilters {
  const GlossaryFilters(
      {this.query,
      this.tags = const <String>[],
      this.year,
      this.cursor,
      this.limit = 30});

  final String? query;
  final List<String> tags;
  final int? year;
  final String? cursor;
  final int limit;

  Map<String, dynamic> toMap() => {
        'query': query,
        'tags': tags,
        'year': year,
        'cursor': cursor,
        'limit': limit,
      };
}

class GlossaryCached<T> {
  const GlossaryCached({required this.data, required this.cacheStatus});

  final T data;
  final CacheStatus cacheStatus;
}

final glossaryCacheProvider =
    Provider<GlossaryCacheStore>((ref) => const GlossaryCacheStore());

final glossaryPublicCommitteesProvider =
    FutureProvider<GlossaryCached<List<GlossaryCommittee>>>((ref) async {
  final api = ref.read(apiProvider);
  final cache = ref.read(glossaryCacheProvider);
  final network = ref.watch(networkStatusProvider);
  if (network == NetworkState.offline) {
    final hit = await cache.read(GlossaryCacheStore.publicCommitteesKey);
    if (hit != null) {
      return GlossaryCached(
        data: ((hit.payload['items'] as List?) ?? const <dynamic>[])
            .whereType<Map>()
            .map(
                (e) => GlossaryCommittee.fromJson(Map<String, dynamic>.from(e)))
            .toList(growable: false),
        cacheStatus: hit.status,
      );
    }
  }
  try {
    final items = await api.glossaryPublicCommittees();
    await cache.write(GlossaryCacheStore.publicCommitteesKey, {
      'items': items
          .map((e) => {'id': e.id, 'name': e.name, 'shortName': e.shortName})
          .toList(growable: false)
    });
    return GlossaryCached(
        data: items,
        cacheStatus: const CacheStatus(isCached: false, isStale: false));
  } catch (_) {
    final hit = await cache.read(GlossaryCacheStore.publicCommitteesKey);
    if (hit == null) rethrow;
    return GlossaryCached(
      data: ((hit.payload['items'] as List?) ?? const <dynamic>[])
          .whereType<Map>()
          .map((e) => GlossaryCommittee.fromJson(Map<String, dynamic>.from(e)))
          .toList(growable: false),
      cacheStatus: hit.status,
    );
  }
});

final glossaryPublicSettingsProvider =
    FutureProvider.family<GlossaryCached<GlossarySettings>, int>(
        (ref, committeeId) async {
  final api = ref.read(apiProvider);
  final cache = ref.read(glossaryCacheProvider);
  final key = GlossaryCacheStore.publicSettingsKey(committeeId);
  try {
    final data = await api.glossaryPublicSettings(committeeId);
    await cache.write(key, data.toJson());
    return GlossaryCached(
        data: data,
        cacheStatus: const CacheStatus(isCached: false, isStale: false));
  } catch (_) {
    final hit = await cache.read(key);
    if (hit == null) rethrow;
    return GlossaryCached(
        data: GlossarySettings.fromJson(hit.payload), cacheStatus: hit.status);
  }
});

final glossaryPublicTermsProvider = FutureProvider.family<
    GlossaryCached<GlossaryTermsPage>,
    ({int committeeId, GlossaryFilters filters})>((ref, input) async {
  final api = ref.read(apiProvider);
  final cache = ref.read(glossaryCacheProvider);
  final key = cache.publicTermsKey(input.committeeId, input.filters.toMap());
  try {
    final data = await api.glossaryPublicTerms(
      input.committeeId,
      query: input.filters.query,
      tags: input.filters.tags,
      year: input.filters.year,
      cursor: input.filters.cursor,
      limit: input.filters.limit,
    );
    await cache.write(key, data.toJson());
    return GlossaryCached(
        data: data,
        cacheStatus: const CacheStatus(isCached: false, isStale: false));
  } catch (_) {
    final hit = await cache.read(key);
    if (hit == null) rethrow;
    return GlossaryCached(
        data: GlossaryTermsPage.fromJson(hit.payload), cacheStatus: hit.status);
  }
});

final committeeGlossarySettingsProvider =
    FutureProvider.family<GlossaryCached<GlossarySettings>, int>(
        (ref, committeeId) async {
  final api = ref.read(apiProvider);
  final cache = ref.read(glossaryCacheProvider);
  final key = GlossaryCacheStore.privateSettingsKey(committeeId);
  try {
    final data = await api.committeeGlossarySettings(committeeId);
    await cache.write(key, data.toJson());
    return GlossaryCached(
        data: data,
        cacheStatus: const CacheStatus(isCached: false, isStale: false));
  } catch (_) {
    final hit = await cache.read(key);
    if (hit == null) rethrow;
    return GlossaryCached(
        data: GlossarySettings.fromJson(hit.payload), cacheStatus: hit.status);
  }
});

final committeeGlossaryTermsProvider = FutureProvider.family<
    GlossaryCached<GlossaryTermsPage>,
    ({int committeeId, GlossaryFilters filters})>((ref, input) async {
  final api = ref.read(apiProvider);
  final cache = ref.read(glossaryCacheProvider);
  final key = cache.privateTermsKey(input.committeeId, input.filters.toMap());
  try {
    final data = await api.committeeGlossaryTerms(
      input.committeeId,
      query: input.filters.query,
      tags: input.filters.tags,
      year: input.filters.year,
      cursor: input.filters.cursor,
      limit: input.filters.limit,
    );
    await cache.write(key, data.toJson());
    return GlossaryCached(
        data: data,
        cacheStatus: const CacheStatus(isCached: false, isStale: false));
  } catch (_) {
    final hit = await cache.read(key);
    if (hit == null) rethrow;
    return GlossaryCached(
        data: GlossaryTermsPage.fromJson(hit.payload), cacheStatus: hit.status);
  }
});

void invalidateGlossaryAfterWrite(WidgetRef ref, int committeeId) {
  ref.invalidate(committeeGlossarySettingsProvider(committeeId));
  ref.invalidate(glossaryPublicSettingsProvider(committeeId));
  ref.invalidate(glossaryPublicTermsProvider);
  ref.invalidate(committeeGlossaryTermsProvider);
  ref.invalidate(glossaryPublicCommitteesProvider);
}
