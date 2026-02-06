import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'cache_store.dart';

final cacheStoreProvider = Provider<CacheStore>((ref) {
  return CacheStore();
});
