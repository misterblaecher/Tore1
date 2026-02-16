import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/features/community/data/orga_posts_cache.dart';
import 'package:tore/features/navigation/models/profile_v2_model.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('profile model parsing', () {
    final model = ProfileV2Model.fromJson({
      'id': 'u1',
      'display_name': 'Pseudo',
      'photo_url': 'https://img',
      'bio': 'bio',
      'instagram_handle': 'insta',
      'visibility': 'PRIVATE',
    });
    expect(model.id, 'u1');
    expect(model.displayName, 'Pseudo');
    expect(model.visibility, 'PRIVATE');
  });

  test('posts cache ttl', () async {
    SharedPreferences.setMockInitialValues({});
    final cache = OrgaPostsCache(ttl: const Duration(seconds: 0));
    await cache.save(9, [
      {'id': 1, 'text': 'hello'}
    ]);
    final (items, stale) = await cache.read(9);
    expect(items.length, 1);
    expect(stale, isTrue);
  });

  test('posts cache read/write payload', () async {
    SharedPreferences.setMockInitialValues({});
    final cache = OrgaPostsCache(ttl: const Duration(days: 1));
    await cache.save(2, [
      {'id': 4, 'text': 'post text', 'pinned': true}
    ]);
    final (items, stale) = await cache.read(2);
    expect(stale, isFalse);
    expect(items.first['text'], 'post text');
    expect(items.first['pinned'], true);
  });
}
