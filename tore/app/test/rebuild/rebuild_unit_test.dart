import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/backend_models.dart';
import 'package:tore/rebuild/models/event_context.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/models/snapshot.dart';
import 'package:tore/rebuild/routing/route_guards.dart';
import 'package:tore/rebuild/services/idempotency_store.dart';

class _MemoryPersistence implements IdempotencyPersistence {
  final Map<String, String> _data = {};

  @override
  Future<Map<String, String>> loadAll() async =>
      Map<String, String>.from(_data);

  @override
  Future<void> saveAll(Map<String, String> data) async {
    _data
      ..clear()
      ..addAll(data);
  }

  @override
  Future<void> clear() async {
    _data.clear();
  }
}

void main() {
  test('state alias normalization maps backend aliases consistently', () {
    expect(mapBackendStateAlias('RUNNING'), EventState.live);
    expect(mapBackendStateAlias('LIVE'), EventState.live);
    expect(mapBackendStateAlias('PAUSE'), EventState.paused);
    expect(mapBackendStateAlias('PAUSED'), EventState.paused);
    expect(mapBackendStateAlias('CLOSED'), EventState.ended);
    expect(mapBackendStateAlias('FROZEN'), EventState.readOnly);
  });

  test('module gating and deep-link guards enforce mode + OFF module blocking',
      () {
    final guards = RouteGuards();
    final snapshot = UserSnapshot(
      roles: {'USER'},
      capabilities: {'can_scan_qr'},
      globalModules: {'user_home': ModuleState.on},
      syncedAt: DateTime.fromMillisecondsSinceEpoch(0),
    );

    expect(guards.modeAllowed(ToreMode.user, snapshot), isTrue);
    expect(guards.modeAllowed(ToreMode.orga, snapshot), isFalse);
    expect(guards.deepLinkAllowed(ModuleState.off), isFalse);
    expect(guards.deepLinkAllowed(ModuleState.on), isTrue);
  });

  test('idempotency key is reused across retries for same intent', () async {
    final persistence = _MemoryPersistence();
    final store = IdempotencyStore(persistence: persistence);

    final first = await store.keyForIntent('POST:/events/42/join');
    final second = await store.keyForIntent('POST:/events/42/join');

    expect(second.key, first.key);
    expect(first.replayed, isFalse);
    expect(second.replayed, isTrue);
  });

  test('QR error code mapping provides stable code + copy prefix', () {
    final invalid = mapQrReasonToError('invalid_qr');
    final moduleOff = mapQrReasonToError('module_off');

    expect(invalid.code, 'qr_unknown');
    expect(invalid.message, startsWith('Code non reconnu'));

    expect(moduleOff.code, 'module_off');
    expect(moduleOff.message, startsWith('Le module'));
  });

  test('API error code mapping distinguishes auth and missing resources', () {
    expect(normalizeUiCode('missing_token'), 'unauthenticated');
    expect(normalizeUiCode('event_not_found'), 'not_found');
    expect(normalizeUiCode('not_found'), 'not_found');
    expect(normalizeUiCode('validation_error'), 'invalid_request');
    expect(resolveUiCopy('unauthenticated').title, 'Connexion requise');
  });

  test('mobile bootstrap and event context parse backend aliases', () {
    final bootstrap = MobileBootstrapDto.fromJson({
      'bar_id': 7,
      'event_id': 12,
      'eventName': 'Soiree',
      'source': 'active',
    });
    expect(bootstrap.barId, '7');
    expect(bootstrap.eventKey, 'event_12');
    expect(bootstrap.eventApiId, '12');

    final context = EventContext.fromJson({
      'eventId': 'event_12',
      'eventState': 'LIVE',
      'moduleStates': {
        'user_menu': 'ON',
        'user_hunts': 'FROZEN',
        'user_wifi': 'READ_ONLY',
      },
    });
    expect(context.eventState, EventState.live);
    expect(context.moduleStates['user_menu'], ModuleState.on);
    expect(context.moduleStates['user_hunts'], ModuleState.frozen);
    expect(context.moduleStates['user_wifi'], ModuleState.readOnly);
  });
}
