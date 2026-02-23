import 'package:flutter_test/flutter_test.dart';
import 'package:tore/rebuild/models/event_context.dart';
import 'package:tore/rebuild/models/qr_resolve.dart';
import 'package:tore/rebuild/models/rebuild_types.dart';
import 'package:tore/rebuild/models/snapshot.dart';
import 'package:tore/rebuild/routing/route_guards.dart';
import 'package:tore/rebuild/services/idempotency_store.dart';

class _MemoryPersistence implements IdempotencyPersistence {
  final Map<String, String> _data = {};

  @override
  Future<Map<String, String>> loadAll() async => Map<String, String>.from(_data);

  @override
  Future<void> saveAll(Map<String, String> data) async {
    _data
      ..clear()
      ..addAll(data);
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

  test('module gating and deep-link guards enforce mode + OFF module blocking', () {
    final guards = RouteGuards();
    const snapshot = UserSnapshot(
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

    expect(first, equals(second));
  });

  test('QR error code mapping provides expected UX copy', () {
    final invalid = mapQrReasonToError('invalid_qr');
    final moduleOff = mapQrReasonToError('module_off');

    expect(invalid.message, 'QR non reconnu.');
    expect(moduleOff.message, 'Module indisponible.');
  });
}
