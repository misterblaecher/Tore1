import 'dart:convert';

import 'package:dio/dio.dart';

import '../../config/app_config.dart';
import '../models/backend_models.dart';
import '../models/error_model.dart';
import '../models/event_context.dart';
import '../models/qr_resolve.dart';
import '../models/rebuild_types.dart';
import '../models/snapshot.dart';
import 'cache_store.dart';
import 'client_log.dart';
import 'network_state_resolver.dart';

class ApiRequestStat {
  const ApiRequestStat({required this.method, required this.path, required this.status, required this.latencyMs, required this.at});

  final String method;
  final String path;
  final int status;
  final int latencyMs;
  final DateTime at;
}

class ApiClient {
  ApiClient({CacheStore? cacheStore, NetworkStateResolver? networkStateResolver})
      : _cache = cacheStore ?? CacheStore(),
        _networkStateResolver = networkStateResolver ?? NetworkStateResolver(),
        _dio = Dio(BaseOptions(baseUrl: AppConfig.apiBaseUrlResolved, connectTimeout: const Duration(seconds: 10), receiveTimeout: const Duration(seconds: 15)));

  final Dio _dio;
  final CacheStore _cache;
  final NetworkStateResolver _networkStateResolver;
  final List<ApiRequestStat> _recentRequests = <ApiRequestStat>[];
  final List<String> _recentErrors = <String>[];

  List<ApiRequestStat> recentRequests() => _recentRequests.reversed.take(10).toList(growable: false);

  List<String> recentErrorCodes() => _recentErrors.reversed.take(10).toList(growable: false);

  Future<UserSnapshot> fetchMeSnapshot() async {
    await Future<void>.delayed(const Duration(milliseconds: 50));
    final rawJson = {
      'id': 'user_123',
      'account_mode': 'orga',
    };
    _logWire('/auth/me', rawJson);

    final snapshot = UserSnapshot(
      roles: const {'USER', 'ORGA'},
      capabilities: const {'can_access_orga', 'can_scan_qr'},
      globalModules: const {
        'user_qr_scanner': ModuleState.on,
        'user_polymarket_global': ModuleState.on,
        'bar_dashboard': ModuleState.off,
      },
      syncedAt: DateTime.now(),
    );
    _logNormalized('/auth/me', {'roles': snapshot.roles.toList(), 'caps': snapshot.capabilities.toList()});
    return snapshot;
  }

  Future<EventContext> fetchEventContext(String eventId, List<ModuleDefinition> defs) async {
    final rawJson = await _getJson('/events/$eventId/context', network: ConnectivityState.online);
    final states = <String, ModuleState>{
      for (final d in defs) d.id: d.scope == ScopeBadge.event || d.scope == ScopeBadge.bar ? ModuleState.on : ModuleState.readOnly,
      'user_hunts': ModuleState.frozen,
      'orga_finance_admin': ModuleState.off,
      'bar_orders_live': ModuleState.on,
    };
    final context = EventContext(
      eventId: eventId,
      eventState: mapBackendStateAlias((rawJson['eventState'] ?? rawJson['event_state'] ?? 'RUNNING').toString()),
      moduleStates: states,
      syncedAt: DateTime.tryParse((rawJson['lastUpdatedAt'] ?? DateTime.now().toIso8601String()).toString()) ?? DateTime.now(),
    );
    _logNormalized('/events/{id}/context', {'eventState': context.eventState.name});
    return context;
  }

  Future<QrResolve> resolveQr(String payload) async {
    await ClientLog.instance.log('qr.scan', {'type': 'unknown', 'signed': payload.contains('sig='), 'expires_in': payload.contains('exp=') ? 'embedded' : 'n/a'});
    try {
      final json = await _postJson('/qr/resolve', {'payload': payload}, network: ConnectivityState.online);
      await ClientLog.instance.log('qr.route', {'target': json['type']?.toString() ?? 'unknown', 'success': true});
      return QrResolve.fromJson(json);
    } catch (_) {
      final normalized = payload.trim().toLowerCase();
      Map<String, dynamic> rawResponse;
      if (normalized.isEmpty || normalized == 'unknown') {
        rawResponse = {'valid': false, 'type': 'unknown', 'reason': 'invalid_qr'};
      } else if (normalized.contains('expired')) {
        rawResponse = {'valid': false, 'type': 'unknown', 'reason': 'expired_qr'};
      } else if (normalized.contains('replay')) {
        rawResponse = {'valid': false, 'type': 'unknown', 'reason': 'replay_qr'};
      } else if (normalized.contains('module_off')) {
        rawResponse = {'valid': false, 'type': 'menu', 'reason': 'module_off'};
      } else if (normalized.contains('paused')) {
        rawResponse = {'valid': false, 'type': 'event_hub', 'reason': 'event_paused'};
      } else if (normalized.contains('down')) {
        rawResponse = {'valid': false, 'type': 'unknown', 'reason': 'backend_down'};
      } else if (normalized.contains('join')) {
        rawResponse = {'valid': true, 'type': 'join_event', 'event_id': 42, 'route_front': '/event/42/join'};
      } else if (normalized.contains('menu')) {
        rawResponse = {'valid': true, 'type': 'menu', 'event_id': 42, 'route_front': '/event/42/menu'};
      } else {
        rawResponse = {'valid': true, 'type': 'event_hub', 'event_id': 42, 'route_front': '/event/42'};
      }
      await ClientLog.instance.log('qr.route', {'target': rawResponse['type']?.toString() ?? 'unknown', 'success': false});
      return QrResolve.fromJson(rawResponse);
    }
  }

  Future<List<BarDto>> fetchBars({required ConnectivityState network, String? cursor, int limit = 20}) async {
    final key = _cache.barsKey();
    final json = await _cacheFirstGet(key: key, path: '/bars', query: {'cursor': cursor, 'limit': limit}, network: network);
    return _items(json).map(BarDto.fromJson).toList();
  }

  Future<List<EventDto>> fetchBarEvents(String barId, {String filter = 'all', required ConnectivityState network, String? cursor, int limit = 20}) async {
    final key = _cache.barEventsKey(barId, filter);
    final json = await _cacheFirstGet(key: key, path: '/bars/$barId/events', query: {'filter': filter, 'cursor': cursor, 'limit': limit}, network: network);
    return _items(json).map(EventDto.fromJson).toList();
  }

  Future<void> joinEvent(String eventId, {String? optionalCode, required String idempotencyKey, required ConnectivityState network}) async {
    await _postJson('/events/$eventId/join', {'code': optionalCode}, headers: {'X-Idempotency-Key': idempotencyKey}, network: network);
  }

  Future<List<MenuItemDto>> fetchMenu({String? barId, String? eventId, required ConnectivityState network}) async {
    final scope = eventId != null ? 'event' : 'bar';
    final id = eventId ?? barId ?? 'unknown';
    final path = eventId != null ? '/events/$eventId/menu' : '/menu/public/$barId';
    final json = await _cacheFirstGet(key: _cache.menuKey(scope, id), path: path, network: network);
    final payload = (json['menu'] ?? json['items'] ?? json) as Object;
    if (payload is List) return payload.whereType<Map<String, dynamic>>().map(MenuItemDto.fromJson).toList();
    return _items(json).map(MenuItemDto.fromJson).toList();
  }

  Future<WalletDto> fetchWallet({String? eventId, required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: _cache.walletKey(eventId == null ? 'me' : 'event', eventId ?? 'me'), path: '/wallet/me', query: eventId == null ? null : {'event_id': eventId}, network: network);
    return WalletDto.fromJson(json);
  }

  Future<PagedResult<TickerItemDto>> fetchTicker(String eventId, {String? cursor, int limit = 30, required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: _cache.tickerKey(eventId), path: '/events/$eventId/ticker', query: {'cursor': cursor, 'limit': limit}, network: network);
    return PagedResult(items: _items(json).map(TickerItemDto.fromJson).toList(), nextCursor: json['next_cursor']?.toString());
  }

  Future<List<PolymarketDto>> fetchPolymarketGlobal({required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: 'polymarket:global:v1', path: '/polymarket/global', network: network);
    return _items(json).map(PolymarketDto.fromJson).toList();
  }

  Future<List<PolymarketDto>> fetchPolymarketEvent(String eventId, {required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: 'polymarket:event:$eventId:v1', path: '/events/$eventId/polymarket', network: network);
    return _items(json).map(PolymarketDto.fromJson).toList();
  }

  Future<EntryStatsDto> fetchEntryStats(String eventId, {required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: 'entry_stats:$eventId:v1', path: '/partner/portal/orga/events/$eventId/entry/stats', network: network);
    return EntryStatsDto.fromJson(json);
  }

  Future<Map<String, dynamic>?> fetchOrgaQrPack(String eventId, {required ConnectivityState network}) async {
    try {
      return await _getJson('/partner/portal/orga/events/$eventId/qr/pack', network: network);
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>> writeEntryScan(String eventId, Map<String, dynamic> payload, {required String idempotencyKey, required ConnectivityState network}) {
    return _postJson('/partner/portal/orga/events/$eventId/entry/scan', payload, headers: {'X-Idempotency-Key': idempotencyKey}, network: network);
  }

  Future<PagedResult<OrderDto>> fetchOrdersLive(String eventId, {String? cursor, int limit = 25, required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: _cache.ordersKey('event', eventId), path: '/orders/live', query: {'event_id': eventId, 'cursor': cursor, 'limit': limit}, network: network);
    return PagedResult(items: _items(json).map(OrderDto.fromJson).toList(), nextCursor: json['next_cursor']?.toString());
  }

  Future<void> updateOrderStatus(String orderId, String status, {String? reason, required String idempotencyKey, required ConnectivityState network}) async {
    await _patchJson('/orders/$orderId/status', {'status': status, if (reason != null) 'reason_text': reason}, headers: {'X-Idempotency-Key': idempotencyKey}, network: network);
  }

  Future<List<ZoneDto>> fetchZones(String barId, {required ConnectivityState network}) async {
    final json = await _cacheFirstGet(key: _cache.zonesKey(barId), path: '/partner/portal/bar/$barId/zones', network: network);
    return _items(json).map(ZoneDto.fromJson).toList();
  }

  Future<void> toggleZone(String zoneId, bool enabled, {String? reason, required String idempotencyKey, required ConnectivityState network}) async {
    await _patchJson('/partner/portal/zones/$zoneId', {'enabled': enabled, if (reason != null) 'reason_text': reason}, headers: {'X-Idempotency-Key': idempotencyKey}, network: network);
  }

  Future<Map<String, dynamic>> _cacheFirstGet({required String key, required String path, Map<String, dynamic>? query, required ConnectivityState network}) async {
    final cached = await _cache.loadJson(key, ttl: const Duration(minutes: 5));
    if (network == ConnectivityState.offline) {
      if (cached != null) {
        await ClientLog.instance.log('offline.read_cache', {'key': key});
        return cached.payload;
      }
      throw const ApiError(ErrorModel(code: 'offline_read_unavailable', message: 'offline_read_unavailable'));
    }
    if (cached != null && !cached.isStale) return cached.payload;
    try {
      final json = await _getJson(path, query: query, network: network);
      await _cache.saveJson(key, json);
      return json;
    } catch (_) {
      if (cached != null) return cached.payload;
      rethrow;
    }
  }

  Future<Map<String, dynamic>> _getJson(String path, {Map<String, dynamic>? query, required ConnectivityState network}) async {
    return _withRetry(() async {
      final watch = Stopwatch()..start();
      final res = await _dio.get(path, queryParameters: query);
      _recordRequest('GET', path, res.statusCode ?? 200, watch.elapsedMilliseconds);
      return _asMap(res.data);
    }, retries: _networkStateResolver.getMaxGetRetries(network));
  }

  Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> body, {Map<String, dynamic>? headers, required ConnectivityState network}) async {
    if (!_networkStateResolver.canWrite(network)) {
      await ClientLog.instance.log('write.blocked', {'reason_code': 'offline_write_blocked', 'network_state': network.name, 'event_state': 'unknown', 'module_state': 'unknown'});
      throw const ApiError(ErrorModel(code: 'offline_write_blocked', message: 'offline_write_blocked'));
    }
    final watch = Stopwatch()..start();
    final res = await _dio.post(path, data: body, options: Options(headers: headers));
    _recordRequest('POST', path, res.statusCode ?? 200, watch.elapsedMilliseconds);
    return _asMap(res.data);
  }

  Future<Map<String, dynamic>> _patchJson(String path, Map<String, dynamic> body, {Map<String, dynamic>? headers, required ConnectivityState network}) async {
    if (!_networkStateResolver.canWrite(network)) {
      await ClientLog.instance.log('write.blocked', {'reason_code': 'offline_write_blocked', 'network_state': network.name, 'event_state': 'unknown', 'module_state': 'unknown'});
      throw const ApiError(ErrorModel(code: 'offline_write_blocked', message: 'offline_write_blocked'));
    }
    final watch = Stopwatch()..start();
    final res = await _dio.patch(path, data: body, options: Options(headers: headers));
    _recordRequest('PATCH', path, res.statusCode ?? 200, watch.elapsedMilliseconds);
    return _asMap(res.data);
  }

  Future<T> _withRetry<T>(Future<T> Function() run, {required int retries}) async {
    Object? last;
    for (var attempt = 0; attempt <= retries; attempt++) {
      try {
        return await run();
      } catch (e) {
        last = e;
        if (attempt < retries) {
          await Future<void>.delayed(Duration(milliseconds: 200 * (attempt + 1)));
        }
      }
    }
    throw _normalizeError(last);
  }

  ApiError _normalizeError(Object? error) {
    if (error is ApiError) return error;
    if (error is DioException) {
      final reason = (error.response?.data as Map?)?['reason']?.toString() ?? 'backend_down';
      final normalized = normalizeUiCode(reason);
      _recentErrors.add(normalized);
      if (_recentErrors.length > 20) {
        _recentErrors.removeAt(0);
      }
      ClientLog.instance.log('api.error', {'normalized_code': normalized});
      return ApiError(ErrorModel(code: normalized, message: resolveUiCopy(reason).message));
    }
    _recentErrors.add('backend_down');
    ClientLog.instance.log('api.error', {'normalized_code': 'backend_down'});
    return const ApiError(ErrorModel(code: 'backend_down', message: 'Service indisponible'));
  }

  List<Map<String, dynamic>> _items(Map<String, dynamic> map) {
    final rows = (map['items'] ?? map['rows'] ?? map['events'] ?? map['orders'] ?? map['markets'] ?? <dynamic>[]) as List<dynamic>;
    return rows.whereType<Map<String, dynamic>>().toList();
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return value.cast<String, dynamic>();
    if (value is List) return {'items': value};
    return {'value': value};
  }

  void _recordRequest(String method, String path, int status, int latencyMs) {
    _recentRequests.add(ApiRequestStat(method: method, path: path, status: status, latencyMs: latencyMs, at: DateTime.now()));
    if (_recentRequests.length > 50) {
      _recentRequests.removeAt(0);
    }
    ClientLog.instance.log('api.request', {'path': path, 'method': method, 'latency_ms': latencyMs, 'status': status});
  }

  void _logWire(String endpoint, Map<String, dynamic> payload) {
    assert(() {
      // ignore: avoid_print
      print('[rebuild-wire] $endpoint ${jsonEncode(payload)}');
      return true;
    }());
  }

  void _logNormalized(String endpoint, Map<String, dynamic> payload) {
    assert(() {
      // ignore: avoid_print
      print('[rebuild-norm] $endpoint ${jsonEncode(payload)}');
      return true;
    }());
  }
}

class ApiError implements Exception {
  const ApiError(this.error);
  final ErrorModel error;
}
