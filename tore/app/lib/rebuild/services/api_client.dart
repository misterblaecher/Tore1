import 'dart:convert';

import '../models/event_context.dart';
import '../models/qr_resolve.dart';
import '../models/rebuild_types.dart';
import '../models/snapshot.dart';

class ApiClient {
  Future<UserSnapshot> fetchMeSnapshot() async {
    await Future<void>.delayed(const Duration(milliseconds: 200));
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
    await Future<void>.delayed(const Duration(milliseconds: 220));
    final rawJson = {
      'event': {'id': int.tryParse(eventId.replaceAll('event_', '')) ?? 42},
      'eventState': 'RUNNING',
      'modulesOn': ['user_join', 'user_menu', 'bar_orders_live'],
      'lastUpdatedAt': DateTime.now().toIso8601String(),
    };
    _logWire('/events/{id}/context', rawJson);

    final states = <String, ModuleState>{
      for (final d in defs) d.id: d.scope == ScopeBadge.event || d.scope == ScopeBadge.bar ? ModuleState.on : ModuleState.readOnly,
      'user_hunts': ModuleState.frozen,
      'orga_finance_admin': ModuleState.off,
      'bar_orders_live': ModuleState.on,
    };
    final context = EventContext(
      eventId: eventId,
      eventState: mapBackendStateAlias(rawJson['eventState']! as String),
      moduleStates: states,
      syncedAt: DateTime.parse(rawJson['lastUpdatedAt']! as String),
    );
    _logNormalized('/events/{id}/context', {'eventState': context.eventState.name});
    return context;
  }

  Future<QrResolve> resolveQr(String payload) async {
    await Future<void>.delayed(const Duration(milliseconds: 160));
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
    _logWire('/qr/resolve', rawResponse);
    _logNormalized('/qr/resolve', {'reason': rawResponse['reason'], 'type': rawResponse['type']});
    return QrResolve.fromJson(rawResponse);
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
