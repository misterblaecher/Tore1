import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/community/community_models.dart';
import 'package:tore/features/community/data/community_explorer_cache.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('cache key hash is stable regardless of param order', () {
    final a = communityExplorerHashParams({'q': 'abc', 'sort': 'recent', 'type': 'bar'});
    final b = communityExplorerHashParams({'type': 'bar', 'q': 'abc', 'sort': 'recent'});
    expect(a, b);
  });

  test('orga summary parses followersCount and lastActiveAt', () {
    final item = OrgaSummary.fromJson({'id': 1, 'name': 'Club', 'followersCount': 123, 'lastActiveAt': '2025-01-01T12:00:00Z'});
    expect(item.followersCount, 123);
    expect(item.lastActiveAt, isNotNull);
  });

  test('cache read/write and debounce config', () async {
    SharedPreferences.setMockInitialValues({});
    final cache = CommunityExplorerCache(ttl: const Duration(days: 1));
    await cache.save({'q': 'liege'}, {
      'items': [
        {'id': 9, 'name': 'Alpha', 'followersCount': 2}
      ],
      'nextCursor': 'abc',
    });
    final read = await cache.read({'q': 'liege'});
    expect(read.payload?['items'], isNotEmpty);
    expect(read.isStale, isFalse);
    expect(communityExplorerDebounceMs, 350);
  });
}
