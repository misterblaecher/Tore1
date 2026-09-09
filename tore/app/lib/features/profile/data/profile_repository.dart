import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../shared/cache/cache_store.dart';
import '../domain/profile_models.dart';

class ProfileLoadResult {
  final ToreProfile profile;
  final bool isFromCache;
  final DateTime? cachedAt;

  const ProfileLoadResult(this.profile,
      {this.isFromCache = false, this.cachedAt});
}

class ProfileRepository {
  final ApiClient api;
  final CacheStore cache;

  ProfileRepository(this.api, this.cache);

  Future<ProfileLoadResult> getOwnerProfile(String userId) async {
    final key = cache.ownerKey(userId);
    try {
      final response = await api.dio.get(ApiEndpoints.meProfile);
      final data = (response.data as Map).cast<String, dynamic>();
      final fetchedAt = DateTime.now();
      await cache.setJson(
          key,
          {
            'profile': data,
            'cached_at': fetchedAt.toIso8601String(),
          },
          ttl: const Duration(days: 7));
      return ProfileLoadResult(ToreProfile.fromJson(data));
    } on DioException catch (error) {
      if (error.response?.statusCode == 401 ||
          error.response?.statusCode == 403) {
        rethrow;
      }
      final cached = await cache.getJson(key);
      final raw = cached?['profile'];
      if (raw is Map) {
        return ProfileLoadResult(
          ToreProfile.fromJson(raw.cast<String, dynamic>()),
          isFromCache: true,
          cachedAt: DateTime.tryParse(cached?['cached_at']?.toString() ?? ''),
        );
      }
      rethrow;
    }
  }

  Future<ToreProfile> patchProfile({
    String? username,
    String? displayName,
    String? avatarUrl,
    String? oripeaux,
    String? bio,
    String? city,
  }) async {
    final response = await api.dio.patch(ApiEndpoints.meProfile, data: {
      if (username != null) 'username': username,
      if (displayName != null) 'display_name': displayName,
      if (avatarUrl != null) 'avatar_url': avatarUrl,
      if (oripeaux != null) 'oripeaux': oripeaux,
      if (bio != null) 'bio': bio,
      if (city != null) 'city': city,
    });
    final data = (response.data as Map).cast<String, dynamic>();
    final profile = ToreProfile.fromJson(data);
    await _cacheOwner(profile);
    return profile;
  }

  Future<ToreProfile> patchPrivacy(Map<String, dynamic> fields) async {
    final response = await api.dio.patch(ApiEndpoints.mePrivacy, data: fields);
    final data = (response.data as Map).cast<String, dynamic>();
    final profile = ToreProfile.fromJson(data);
    await _cacheOwner(profile);
    return profile;
  }

  Future<List<Affiliation>> getAffiliations(String userId) async {
    final key = cache.affiliationsKey(userId);
    try {
      final response = await api.dio.get(ApiEndpoints.meAffiliations);
      final data = (response.data as Map).cast<String, dynamic>();
      final items = (data['items'] as List? ?? const [])
          .whereType<Map>()
          .map((item) => Affiliation.fromJson(item.cast<String, dynamic>()))
          .toList();
      await cache.setJson(
          key,
          {
            'items': items.map((item) => item.toJson()).toList(),
            'cached_at': DateTime.now().toIso8601String(),
          },
          ttl: const Duration(days: 7));
      return items;
    } on DioException catch (error) {
      if (error.response?.statusCode == 401 ||
          error.response?.statusCode == 403) {
        rethrow;
      }
      final cached = await cache.getJson(key);
      final items = cached?['items'];
      if (items is List) {
        return items
            .whereType<Map>()
            .map((item) => Affiliation.fromJson(item.cast<String, dynamic>()))
            .toList();
      }
      rethrow;
    }
  }

  Future<EffectiveCapabilities> getCapabilities(String userId) async {
    final key = cache.capabilitiesKey(userId);
    try {
      final response = await api.dio.get(ApiEndpoints.meCapabilities);
      final data = (response.data as Map).cast<String, dynamic>();
      final capabilities = EffectiveCapabilities.fromJson(data);
      await cache.setJson(key, capabilities.toJson(),
          ttl: const Duration(minutes: 5));
      return capabilities;
    } on DioException catch (error) {
      if (error.response?.statusCode == 401 ||
          error.response?.statusCode == 403) {
        rethrow;
      }
      final cached = await cache.getJson(key);
      if (cached != null) {
        return EffectiveCapabilities.fromJson(cached,
            allowOperationalModes: false);
      }
      rethrow;
    }
  }

  Future<ToreProfile?> preview(String context) async {
    final response = await api.dio
        .get(ApiEndpoints.meProfilePreview, queryParameters: {'as': context});
    final data = (response.data as Map).cast<String, dynamic>();
    if (data['visible'] != true || data['profile'] is! Map) return null;
    return ToreProfile.fromJson(
        (data['profile'] as Map).cast<String, dynamic>());
  }

  Future<void> _cacheOwner(ToreProfile profile) async {
    await cache.setJson(
        cache.ownerKey(profile.id),
        {
          'profile': profile.toJson(),
          'cached_at': DateTime.now().toIso8601String(),
        },
        ttl: const Duration(days: 7));
  }
}
