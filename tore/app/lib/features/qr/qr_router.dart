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

  Future<void> route({required BuildContext context, required String raw}) async {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) {
      await _openUnknown(context: context, raw: trimmed, reason: 'QR invalide ou non supporté.');
      return;
    }

    final resolver = _ref.read(qrResolveServiceProvider);
    QrResolveResult result;
    try {
      result = await resolver.resolve(trimmed);
    } catch (_) {
      await _openUnknown(context: context, raw: trimmed, reason: 'Service indisponible. Réessaie.');
      return;
    }

    if (!result.valid) {
      if (result.reason == 'forbidden') {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => QrForbiddenScreen(roleRequired: result.requiredRole ?? 'staff'),
          ),
        );
        return;
      }
      if (result.reason == 'module_off' || result.reason == 'event_paused' || result.reason == 'event_closed') {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: _reasonMessage(result.reason),
            ),
          ),
        );
        return;
      }
      await _openUnknown(context: context, raw: trimmed, reason: _reasonMessage(result.reason));
      return;
    }

    final target = _routeTarget(result);

    switch (target) {
      case _QrTarget.joinEvent:
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR event invalide.');
          return;
        }
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => JoinEventConfirmScreen(eventId: result.eventId!)),
        );
        return;
      case _QrTarget.menu:
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR menu incomplet.');
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => MenuScreen(eventId: result.eventId!)),
        );
        return;
      case _QrTarget.polymarket:
        if (result.eventId != null) _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const PolymarketTabScreen()),
        );
        return;
      case _QrTarget.ticker:
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR ticker invalide.');
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const TickerScreen()),
        );
        return;
      case _QrTarget.orderRestricted:
        await Navigator.of(context).push(
          const MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: 'Module indisponible.',
            ),
          ),
        );
        return;
      case _QrTarget.userRestricted:
        await Navigator.of(context).push(
          const MaterialPageRoute(
            builder: (_) => ModuleUnavailableScreen(
              title: 'Module indisponible',
              message: 'Module indisponible.',
            ),
          ),
        );
        return;
      case _QrTarget.unknown:
        await _openUnknown(context: context, raw: trimmed, reason: 'QR invalide ou non supporté.');
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
  }) async {
    final manualRaw = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) => QrUnknownScreen(
          raw: raw,
          reason: reason,
        ),
      ),
    );
    if (manualRaw != null && manualRaw.isNotEmpty && manualRaw.trim() != raw.trim()) {
      await route(context: context, raw: manualRaw);
    }
  }
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
