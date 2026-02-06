class OfflineNoCacheException implements Exception {
  final String resource;

  const OfflineNoCacheException(this.resource);

  @override
  String toString() => 'offline_no_cache:$resource';
}
