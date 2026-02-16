import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../../core/network/network_state_provider.dart';
import '../../core/qr/qr_parser.dart';
import '../../core/qr/qr_validator.dart';
import '../../state.dart';
import '../entry/presentation/entry_staff_screen.dart';
import '../hunt/presentation/hunt_screen.dart';
import '../menu_market/presentation/menu_screen.dart';
import '../navigation/presentation/polymarket_tab_screen.dart';
import '../qr/presentation/join_event_screen.dart';
import '../qr/presentation/module_unavailable_screen.dart';
import '../qr/presentation/qr_expired_screen.dart';
import '../qr/presentation/qr_invalid_screen.dart';
import '../qr/presentation/qr_revoked_screen.dart';
import '../qr/presentation/qr_unknown_screen.dart';
import '../qr/presentation/wifi_screen.dart';
import '../staff/presentation/staff_providers.dart';

class QrRouterService {
  QrRouterService(this._ref);

  final Ref _ref;

  Future<void> route({
    required BuildContext context,
    required String raw,
    void Function(QrRouteOutcome outcome)? onOutcome,
  }) async {
    final payload = _ref.read(qrParserProvider).parse(raw);
    final validation = await _ref.read(qrValidatorProvider).validate(payload);

    if (!validation.isOk) {
      await _routeValidationError(context, payload, validation, onOutcome);
      return;
    }

    if (payload.isUnknown) {
      onOutcome?.call(const QrRouteOutcome.unknown('QR inconnu'));
      await _openUnknown(context: context, payload: payload, reason: payload.reason ?? 'QR inconnu');
      return;
    }

    if (_isWriteBlockedForPayload(payload)) {
      onOutcome?.call(const QrRouteOutcome.denied('Mode lecture'));
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => const ModuleUnavailableScreen(
            title: 'Action bloquée',
            message: 'Mode lecture: réseau indisponible.',
            reasonCode: 'read_only',
          ),
        ),
      );
      return;
    }

    switch (payload.type) {
      case QrType.joinEvent:
        if (payload.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('JOIN invalide'));
          await _openUnknown(context: context, payload: payload, reason: 'event_id manquant');
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('Join event'));
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => JoinEventScreen(prefillEventId: payload.eventId)),
        );
        return;
      case QrType.menu:
        final eventId = payload.eventId ?? _ref.read(appContextProvider).activeEventId;
        if (eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('Menu invalide'));
          await _openUnknown(context: context, payload: payload, reason: 'event_id manquant');
          return;
        }
        _enterEvent(eventId);
        onOutcome?.call(const QrRouteOutcome.success('Menu'));
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => MenuScreen(eventId: eventId)),
        );
        return;
      case QrType.staffEntry:
        if (payload.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('Staff entry invalide'));
          await _openUnknown(context: context, payload: payload, reason: 'event_id manquant');
          return;
        }
        _ref.read(staffSessionProvider.notifier).establish(
          eventId: payload.eventId!,
          role: StaffSessionRole.entry,
          tokenId: payload.tokenId,
          expiresAt: payload.expiresAt,
        );
        _enterEvent(payload.eventId!);
        onOutcome?.call(const QrRouteOutcome.success('Staff entry'));
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => EntryStaffScreen(eventId: payload.eventId)),
        );
        return;
      case QrType.staffBar:
        if (payload.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('Staff bar invalide'));
          await _openUnknown(context: context, payload: payload, reason: 'event_id manquant');
          return;
        }
        final roleRaw = (payload.fields['role'] ?? '').toLowerCase();
        final role = roleRaw == 'manager' ? StaffSessionRole.manager : StaffSessionRole.bar;
        _ref.read(staffSessionProvider.notifier).establish(
          eventId: payload.eventId!,
          role: role,
          tokenId: payload.tokenId,
          expiresAt: payload.expiresAt,
        );
        _enterEvent(payload.eventId!);
        if (role == StaffSessionRole.bar) {
          onOutcome?.call(const QrRouteOutcome.success('Staff bar'));
          await Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => const ModuleUnavailableScreen(
                title: 'Module BAR indisponible',
                message: 'Session BAR créée. Le module live arrive en P3.',
                reasonCode: 'bar_pending_p3',
              ),
            ),
          );
          return;
        }
        onOutcome?.call(const QrRouteOutcome.denied('Module manager indisponible'));
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => const ModuleUnavailableScreen(
              title: 'Module manager indisponible',
              message: 'Session manager créée. L'écran dédié n'est pas encore disponible.',
              reasonCode: 'manager_module_unavailable',
            ),
          ),
        );
        return;
      case QrType.polymarket:
        onOutcome?.call(const QrRouteOutcome.success('Polymarket'));
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const PolymarketTabScreen()),
        );
        return;
      case QrType.wifi:
        if (payload.eventId == null || payload.tokenId == null || payload.tokenId!.isEmpty) {
          onOutcome?.call(const QrRouteOutcome.denied('WiFi QR invalide'));
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const ModuleUnavailableScreen(
                title: 'WiFi indisponible',
                message: 'QR WiFi invalide.',
                reasonCode: 'invalid_qr',
              ),
            ),
          );
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('WiFi'));
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => WifiScreen(eventId: payload.eventId!, token: payload.tokenId!)),
        );
        return;
      case QrType.hunt:
        final activeEventId = _ref.read(appContextProvider).activeEventId;
        final qrEventId = payload.eventId ?? int.tryParse((payload.fields['event_id'] ?? '').toString());
        if (activeEventId == null || qrEventId == null || activeEventId != qrEventId) {
          onOutcome?.call(const QrRouteOutcome.denied('Checkpoint hors contexte event'));
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const QrInvalidScreen(details: 'Checkpoint Hunt invalide: event actif absent ou différent.'),
            ),
          );
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('Hunt checkpoint'));
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => HuntScreen(eventId: activeEventId, initialClaimPayload: payload)),
        );
        return;
      case QrType.battle:
      case QrType.order:
        onOutcome?.call(const QrRouteOutcome.denied('Module indisponible'));
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => const ModuleUnavailableScreen(
              title: 'Module pas encore dispo',
              message: 'Module pas encore dispo',
              reasonCode: 'module_unavailable',
            ),
          ),
        );
        return;
      case QrType.unknown:
        onOutcome?.call(const QrRouteOutcome.unknown('QR inconnu'));
        await _openUnknown(context: context, payload: payload, reason: payload.reason ?? 'QR inconnu');
        return;
    }
  }

  Future<void> _routeValidationError(
    BuildContext context,
    QrPayload payload,
    QrValidationResult validation,
    void Function(QrRouteOutcome outcome)? onOutcome,
  ) async {
    switch (validation.status) {
      case QrValidationStatus.expired:
        onOutcome?.call(const QrRouteOutcome.denied('QR expiré'));
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => QrExpiredScreen(details: validation.reason)));
        return;
      case QrValidationStatus.revoked:
        onOutcome?.call(const QrRouteOutcome.denied('QR révoqué'));
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => QrRevokedScreen(details: validation.reason)));
        return;
      case QrValidationStatus.invalid:
        onOutcome?.call(const QrRouteOutcome.unknown('QR invalide'));
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => QrInvalidScreen(details: validation.reason)));
        return;
      case QrValidationStatus.unknownType:
        onOutcome?.call(const QrRouteOutcome.unknown('Type inconnu'));
        await _openUnknown(context: context, payload: payload, reason: validation.reason ?? 'Type inconnu');
        return;
      case QrValidationStatus.ok:
        return;
    }
  }

  bool _isWriteBlockedForPayload(QrPayload payload) {
    final readOnly = _ref.read(isReadOnlyProvider) || _ref.read(networkStatusProvider) == NetworkState.offline;
    if (!readOnly) return false;
    if (payload.type == QrType.staffEntry) {
      return false; // controlled exception: entry staff can capture offline then sync.
    }
    return payload.type == QrType.staffBar || payload.type == QrType.order;
  }

  void _enterEvent(int eventId) {
    _ref.read(appContextProvider.notifier).enterEvent(eventId: eventId, eventName: 'Event #$eventId');
  }

  Future<void> _openUnknown({required BuildContext context, required QrPayload payload, required String reason}) async {
    final manualRaw = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => QrUnknownScreen(raw: payload.raw, reason: reason, reasonCode: payload.reason ?? 'unknown'),
      ),
    );
    if (manualRaw != null && manualRaw.isNotEmpty && manualRaw.trim() != payload.raw.trim()) {
      await route(context: context, raw: manualRaw);
    }
  }
}

enum QrRouteStatus { success, denied, unknown }

class QrRouteOutcome {
  const QrRouteOutcome(this.status, this.label);

  const QrRouteOutcome.success(String label) : this(QrRouteStatus.success, label);
  const QrRouteOutcome.denied(String label) : this(QrRouteStatus.denied, label);
  const QrRouteOutcome.unknown(String label) : this(QrRouteStatus.unknown, label);

  final QrRouteStatus status;
  final String label;
}

final qrRouterServiceProvider = Provider<QrRouterService>((ref) {
  return QrRouterService(ref);
});

Future<void> handleQr({
  required BuildContext context,
  required WidgetRef ref,
  required String raw,
}) async {
  await ref.read(qrRouterServiceProvider).route(context: context, raw: raw);
}
