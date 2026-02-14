import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../menu_market/presentation/menu_screen.dart';
import '../navigation/presentation/polymarket_tab_screen.dart';
import '../navigation/presentation/ticker_screen.dart';
import '../qr/presentation/join_event_confirm_screen.dart';
import '../qr/presentation/module_unavailable_screen.dart';
import '../qr/presentation/qr_forbidden_screen.dart';
import '../qr/presentation/qr_unknown_screen.dart';
import '../qr/qr_resolve_service.dart';

class QrRouterService {
  QrRouterService(this._ref);

  final Ref _ref;

  Future<void> route({
    required BuildContext context,
    required String raw,
    void Function(QrRouteOutcome outcome)? onOutcome,
  }) async {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) {
      onOutcome?.call(const QrRouteOutcome.unknown('QR vide'));
      await _openUnknown(
        context: context,
        raw: trimmed,
        reason: 'QR invalide ou non supporté.',
        reasonCode: 'invalid',
      );
      return;
    }

    final resolver = _ref.read(qrResolveServiceProvider);
    QrResolveResult result;
    try {
      result = await resolver.resolve(trimmed);
    } catch (_) {
      onOutcome?.call(const QrRouteOutcome.unknown('Service indisponible'));
      await _openUnknown(
        context: context,
        raw: trimmed,
        reason: 'Service indisponible. Réessaie.',
        reasonCode: 'service_unavailable',
      );
      return;
    }

    if (!result.valid) {
      if (result.reason == 'forbidden') {
        onOutcome?.call(const QrRouteOutcome.denied('Accès refusé'));
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => QrForbiddenScreen(roleRequired: result.requiredRole ?? 'staff'),
          ),
        );
        return;
      }
      if (result.reason == 'module_off' || result.reason == 'event_paused' || result.reason == 'event_closed') {
        onOutcome?.call(QrRouteOutcome.denied(_reasonCode(result.reason)));
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: _reasonMessage(result.reason),
              reasonCode: _reasonCode(result.reason),
            ),
          ),
        );
        return;
      }
      onOutcome?.call(QrRouteOutcome.unknown(_reasonCode(result.reason)));
      await _openUnknown(
        context: context,
        raw: trimmed,
        reason: _reasonMessage(result.reason),
        reasonCode: _reasonCode(result.reason),
      );
      return;
    }

    final target = _routeTarget(result);

    switch (target) {
      case _QrTarget.joinEvent:
        if (result.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('JOIN invalide'));
          await _openUnknown(context: context, raw: trimmed, reason: 'QR event invalide.', reasonCode: 'invalid');
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('Join event'));
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => JoinEventConfirmScreen(eventId: result.eventId!)),
        );
        return;
      case _QrTarget.menu:
        if (result.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('MENU invalide'));
          await _openUnknown(context: context, raw: trimmed, reason: 'QR menu incomplet.', reasonCode: 'invalid');
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('Menu'));
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => MenuScreen(eventId: result.eventId!)),
        );
        return;
      case _QrTarget.polymarket:
        onOutcome?.call(const QrRouteOutcome.success('Polymarket'));
        if (result.eventId != null) _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const PolymarketTabScreen()),
        );
        return;
      case _QrTarget.ticker:
        if (result.eventId == null) {
          onOutcome?.call(const QrRouteOutcome.unknown('TICKER invalide'));
          await _openUnknown(context: context, raw: trimmed, reason: 'QR ticker invalide.', reasonCode: 'invalid');
          return;
        }
        onOutcome?.call(const QrRouteOutcome.success('Ticker'));
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const TickerScreen()),
        );
        return;
      case _QrTarget.orderRestricted:
        onOutcome?.call(const QrRouteOutcome.denied('Réservé staff'));
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: 'Module indisponible.',
              reasonCode: 'forbidden',
            ),
          ),
        );
        return;
      case _QrTarget.userRestricted:
        onOutcome?.call(const QrRouteOutcome.denied('Hors scope user'));
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: 'Module indisponible.',
              reasonCode: 'forbidden',
            ),
          ),
        );
        return;
      case _QrTarget.unknown:
        onOutcome?.call(const QrRouteOutcome.unknown('QR inconnu'));
        await _openUnknown(
          context: context,
          raw: trimmed,
          reason: 'QR invalide ou non supporté.',
          reasonCode: 'unknown',
        );
        return;
    }
  }

  void _enterEvent(int eventId) {
    _ref.read(appContextProvider.notifier).enterEvent(
          eventId: eventId,
          eventName: 'Event #$eventId',
        );
  }

  Future<void> _openUnknown({
    required BuildContext context,
    required String raw,
    required String reason,
    required String reasonCode,
  }) async {
    final manualRaw = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => QrUnknownScreen(
          raw: raw,
          reason: reason,
          reasonCode: reasonCode,
        ),
      ),
    );
    if (manualRaw != null && manualRaw.isNotEmpty && manualRaw.trim() != raw.trim()) {
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

enum _QrTarget { joinEvent, menu, polymarket, ticker, orderRestricted, userRestricted, unknown }

_QrTarget _routeTarget(QrResolveResult result) {
  final routeFront = (result.routeFront ?? '').toLowerCase();
  final type = result.type.toLowerCase();

  if (type == 'join' || type == 'join_event') return _QrTarget.joinEvent;
  if (type == 'menu' || routeFront.startsWith('/menu/')) return _QrTarget.menu;
  if (type == 'ticker' || routeFront.startsWith('/events/')) return _QrTarget.ticker;
  if (type == 'polymarket' || type == 'polymarket_bet' || type == 'pm' || routeFront.startsWith('/polymarket/')) {
    return _QrTarget.polymarket;
  }
  if (type == 'order_client' || type == 'order') {
    return _QrTarget.orderRestricted;
  }
  if (type == 'user' || type == 'wallet_user' || routeFront == 'topup_target') {
    return _QrTarget.userRestricted;
  }
  return _QrTarget.unknown;
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

String _reasonMessage(String? reason) {
  switch (reason) {
    case 'module_off':
      return 'Module indisponible.';
    case 'event_paused':
      return 'Service en pause.';
    case 'rate_limited':
      return 'Trop de requêtes. Réessaie.';
    case 'insufficient_balance':
      return 'Solde insuffisant.';
    case 'event_closed':
      return 'Service en pause.';
    default:
      return 'QR invalide ou non supporté.';
  }
}

String _reasonCode(String? reason) {
  switch (reason) {
    case 'module_off':
    case 'event_paused':
    case 'event_closed':
    case 'forbidden':
    case 'invalid':
    case 'expired':
      return reason!;
    default:
      return 'unknown';
  }
}
