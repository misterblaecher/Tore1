import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../menu_market/presentation/menu_screen.dart';
import '../navigation/presentation/checkin_screen.dart';
import '../qr/presentation/qr_unknown_screen.dart';
import '../qr/presentation/qr_placeholders.dart';
import '../qr/presentation/qr_forbidden_screen.dart';
import '../qr/qr_resolve_service.dart';

Future<void> handleQr({
  required BuildContext context,
  required WidgetRef ref,
  required String raw,
}) async {
  final trimmed = raw.trim();
  final resolver = ref.read(qrResolveServiceProvider);
  QrResolveResult result;

  try {
    result = await resolver.resolve(trimmed);
  } catch (_) {
    result = _localResolve(trimmed);
  }

  if (!result.valid || result.eventId == null) {
    if (result.reason == 'forbidden') {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => QrForbiddenScreen(
            roleRequired: result.requiredRole ?? 'entry',
          ),
        ),
      );
      return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => QrUnknownScreen(
          raw: trimmed,
          reason: _reasonMessage(result.reason),
        ),
      ),
    );
    return;
  }

  if (result.type == 'entry' &&
      !_isRoleAllowed(result.grantedRole, 'entry')) {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => QrForbiddenScreen(
          roleRequired: 'entry',
        ),
      ),
    );
    return;
  }

  switch (result.type) {
    case 'join':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => JoinEventPlaceholder(eventId: result.eventId!)),
      );
      return;
    case 'menu':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => MenuScreen(eventId: result.eventId!)),
      );
      return;
    case 'entry':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const CheckinScreen()),
      );
      return;
    default:
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => QrUnknownScreen(
            raw: trimmed,
            reason: 'Format tore:// non supporté.',
          ),
        ),
      );
  }
}

QrResolveResult _localResolve(String raw) {
  final trimmed = raw.trim();
  if (trimmed.isEmpty) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  if (!trimmed.toLowerCase().startsWith('tore://')) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  final uri = Uri.tryParse(trimmed);
  if (uri == null) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  final eventId = int.tryParse(uri.queryParameters['event_id'] ?? '');
  final type = uri.host;
  if (eventId == null || type.isEmpty) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  if (type != 'menu' && type != 'join' && type != 'entry') {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  return QrResolveResult(
    valid: true,
    type: type,
    eventId: eventId,
    reason: null,
    requiredRole: type == 'entry' ? 'entry' : 'guest',
    grantedRole: 'guest',
  );
}

String _reasonMessage(String? reason) {
  switch (reason) {
    case 'expired':
      return 'QR expiré.';
    case 'forbidden':
      return 'QR non autorisé.';
    case 'invalid':
    default:
      return 'QR invalide ou non supporté.';
  }
}

bool _isRoleAllowed(String? grantedRole, String requiredRole) {
  final rank = _roleRank(grantedRole);
  final required = _roleRank(requiredRole);
  return rank >= required;
}

int _roleRank(String? role) {
  switch (role) {
    case 'admin':
      return 3;
    case 'entry':
      return 2;
    default:
      return 1;
  }
}