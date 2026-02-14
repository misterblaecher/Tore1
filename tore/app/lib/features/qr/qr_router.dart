import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../entry/presentation/entry_mode_screen.dart';
import '../menu_market/presentation/menu_screen.dart';
import '../navigation/presentation/home_hub_screen.dart';
import '../navigation/presentation/polymarket_tab_screen.dart';
import '../qr/presentation/qr_forbidden_screen.dart';
import '../qr/presentation/qr_unknown_screen.dart';
import '../qr/presentation/module_unavailable_screen.dart';
import '../qr/qr_resolve_service.dart';
import '../staff/presentation/bar_staff_screen.dart';

class QrRouterService {
  QrRouterService(this._ref);

  final Ref _ref;

  Future<void> route({required BuildContext context, required String raw}) async {
    final trimmed = raw.trim();
    if (trimmed.isEmpty) {
      await _openUnknown(context: context, raw: trimmed, reason: 'QR vide.');
      return;
    }

    final resolver = _ref.read(qrResolveServiceProvider);
    QrResolveResult result;

    try {
      result = await resolver.resolve(trimmed);
    } catch (_) {
      result = _localResolve(trimmed);
    }

    if (!result.valid) {
      if (result.reason == 'forbidden') {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => QrForbiddenScreen(roleRequired: result.requiredRole ?? 'entry'),
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

    final normalizedType = _normalizeType(result.type);

    switch (normalizedType) {
      case 'menu':
        if (result.eventId == null) {
          await _openUnknown(
            context: context,
            raw: trimmed,
            reason: 'QR menu incomplet (event_id requis).',
          );
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => MenuScreen(eventId: result.eventId!)),
        );
        return;
      case 'join_event':
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR event invalide.');
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const HomeHubScreen()),
        );
        return;
      case 'entry_staff':
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR staff entrée invalide.');
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => EntryModeScreen(eventId: result.eventId)),
        );
        return;
      case 'polymarket':
        if (result.reason == 'module_off') {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => const ModuleUnavailableScreen(
                title: 'Module indisponible',
                message: 'Ce module est désactivé pour cet event.',
              ),
            ),
          );
          return;
        }
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const PolymarketTabScreen()),
        );
        return;
      case 'bar_staff':
        if (result.eventId == null) {
          await _openUnknown(context: context, raw: trimmed, reason: 'QR staff bar invalide.');
          return;
        }
        _enterEvent(result.eventId!);
        await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => BarStaffScreen(eventId: result.eventId!)),
        );
        return;
      default:
        await _openUnknown(context: context, raw: trimmed, reason: 'QR non supporté.');
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

String _normalizeType(String type) {
  switch (type) {
    case 'join':
    case 'join_event':
      return 'join_event';
    case 'entry':
    case 'staff_entry':
    case 'entry_staff':
      return 'entry_staff';
    case 'bar_staff':
      return 'bar_staff';
    case 'pm':
    case 'polymarket':
      return 'polymarket';
    default:
      return type;
  }
}

QrResolveResult _localResolve(String raw) {
  final uri = Uri.tryParse(raw);
  if (uri == null || uri.scheme.toLowerCase() != 'tore') {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      barId: null,
      token: null,
      routeFront: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  final rawType = (uri.host.isNotEmpty ? uri.host : uri.path).replaceFirst('/', '').toLowerCase();
  final type = _normalizeType(rawType);
  final eventId = int.tryParse(uri.queryParameters['event_id'] ?? '');

  if (type == 'polymarket') {
    return QrResolveResult(
      valid: true,
      type: type,
      eventId: eventId,
      barId: null,
      token: null,
      routeFront: null,
      reason: null,
      requiredRole: null,
      grantedRole: 'guest',
    );
  }

  if (type == 'menu' || type == 'join_event' || type == 'entry_staff' || type == 'bar_staff') {
    return QrResolveResult(
      valid: eventId != null,
      type: type,
      eventId: eventId,
      barId: null,
      token: null,
      routeFront: null,
      reason: eventId == null ? 'invalid' : null,
      requiredRole: null,
      grantedRole: 'guest',
    );
  }

  return const QrResolveResult(
    valid: false,
    type: 'unknown',
    eventId: null,
    barId: null,
    token: null,
    routeFront: null,
    reason: 'invalid',
    requiredRole: null,
    grantedRole: null,
  );
}

String _reasonMessage(String? reason) {
  switch (reason) {
    case 'expired':
      return 'QR expiré.';
    case 'module_off':
      return 'Ce module est désactivé pour cet event.';
    case 'event_paused':
      return 'Event temporairement en pause.';
    case 'event_closed':
      return 'Event terminé.';
    case 'forbidden':
      return 'Accès non autorisé.';
    default:
      return 'QR invalide ou non supporté.';
  }
}
