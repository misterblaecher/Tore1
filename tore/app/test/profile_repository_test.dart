import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tore/core/network/api_client.dart';
import 'package:tore/features/profile/data/profile_repository.dart';
import 'package:tore/shared/cache/cache_store.dart';

class _QueueAdapter implements HttpClientAdapter {
  _QueueAdapter(this.responses);
  final List<Object> responses;

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    final next = responses.removeAt(0);
    if (next is DioException) throw next;
    final response =
        next is _QueuedResponse ? next : _QueuedResponse(next, statusCode: 200);
    return ResponseBody.fromString(
        jsonEncode(response.data), response.statusCode,
        headers: {
          Headers.contentTypeHeader: ['application/json']
        });
  }

  @override
  void close({bool force = false}) {}
}

class _QueuedResponse {
  const _QueuedResponse(this.data, {required this.statusCode});

  final Object data;
  final int statusCode;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('owner profile is loaded from a user-scoped offline cache', () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    client.dio.httpClientAdapter = _QueueAdapter([
      {
        'id': 'user-a',
        'username': 'alice',
        'display_name': 'Alice',
        'privacy': _privacy,
      },
      DioException(
          requestOptions: RequestOptions(path: '/me/profile'),
          type: DioExceptionType.connectionError),
    ]);
    final repository = ProfileRepository(client, CacheStore());

    final online = await repository.getOwnerProfile('user-a');
    final cached = await repository.getOwnerProfile('user-a');

    expect(online.isFromCache, isFalse);
    expect(cached.isFromCache, isTrue);
    expect(cached.profile.username, 'alice');
    expect(cached.cachedAt, isNotNull);
    expect(await CacheStore().getJson(CacheStore().ownerKey('user-b')), isNull);
  });

  test('cached capabilities never reopen operational modes offline', () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    client.dio.httpClientAdapter = _QueueAdapter([
      {
        'global_roles': ['USER'],
        'structures': [
          {'organization_id': 7, 'role': 'OWNER', 'can_manage': true}
        ],
        'events': [],
        'bars': [],
        'modes': {'organizer': true, 'bar': true},
      },
      DioException(
          requestOptions: RequestOptions(path: '/me/capabilities'),
          type: DioExceptionType.connectionError),
    ]);
    final repository = ProfileRepository(client, CacheStore());

    final online = await repository.getCapabilities('user-a');
    final cached = await repository.getCapabilities('user-a');

    expect(online.canUseOrganizerMode, isTrue);
    expect(cached.structures, isNotEmpty);
    expect(cached.canUseOrganizerMode, isFalse);
    expect(cached.canUseBarMode, isFalse);
  });

  test('profile PATCH persists the real server response in the owner cache',
      () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    client.dio.httpClientAdapter = _QueueAdapter([
      {
        'id': 'user-a',
        'username': 'alice-renamed',
        'display_name': 'Alice',
        'privacy': _privacy,
      },
    ]);
    final cache = CacheStore();
    final repository = ProfileRepository(client, cache);

    final saved = await repository.patchProfile(username: 'alice-renamed');

    expect(saved.username, 'alice-renamed');
    final cached = await cache.getJson(cache.ownerKey('user-a'));
    expect((cached?['profile'] as Map)['username'], 'alice-renamed');
  });

  test('username conflict is propagated with its HTTP status', () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    final request = RequestOptions(path: '/me/profile');
    client.dio.httpClientAdapter = _QueueAdapter([
      DioException(
        requestOptions: request,
        response: Response(
          requestOptions: request,
          statusCode: 409,
          data: {'detail': 'username_taken'},
        ),
        type: DioExceptionType.badResponse,
      ),
    ]);
    final repository = ProfileRepository(client, CacheStore());

    await expectLater(
      repository.patchProfile(username: 'already-taken'),
      throwsA(isA<DioException>()
          .having((error) => error.response?.statusCode, 'status', 409)),
    );
  });

  test('generic profile save failure is propagated without a fake success',
      () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    final request = RequestOptions(path: '/me/profile');
    client.dio.httpClientAdapter = _QueueAdapter([
      DioException(
        requestOptions: request,
        response: Response(
          requestOptions: request,
          statusCode: 500,
          data: {'detail': 'temporary_failure'},
        ),
        type: DioExceptionType.badResponse,
      ),
    ]);
    final repository = ProfileRepository(client, CacheStore());

    await expectLater(
      repository.patchProfile(displayName: 'Unsaved'),
      throwsA(isA<DioException>()
          .having((error) => error.response?.statusCode, 'status', 500)),
    );
  });

  test('profile preview uses the contextual response from the server',
      () async {
    final client = ApiClient.create(baseUrl: 'http://profile-cache.test');
    client.dio.httpClientAdapter = _QueueAdapter([
      {
        'visible': true,
        'viewer_context': 'PUBLIC',
        'profile': {
          'id': 'user-a',
          'username': 'alice',
          'display_name': 'Alice',
        },
      },
      {
        'visible': false,
        'viewer_context': 'PUBLIC',
        'profile': null,
      },
    ]);
    final repository = ProfileRepository(client, CacheStore());

    expect((await repository.preview('PUBLIC'))?.username, 'alice');
    expect(await repository.preview('PUBLIC'), isNull);
  });
}

const _privacy = {
  'profile': 'PRIVATE',
  'photo': 'PRIVATE',
  'bio': 'PRIVATE',
  'affiliations': 'PRIVATE',
  'badges': 'PRIVATE',
  'event_history': 'PRIVATE',
  'participations': 'PRIVATE',
  'gamification': 'PRIVATE',
  'event_history_opt_in': false,
  'participations_opt_in': false,
  'gamification_opt_in': false,
};
