import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/app_context/app_context.dart';
import '../../shared/models/event_config.dart';
import '../events/presentation/event_config_providers.dart';
import '../entry/presentation/entry_mode_screen.dart';
import '../menu_market/presentation/menu_screen.dart';
import '../qr/presentation/qr_feature_disabled_screen.dart';
import '../qr/presentation/qr_forbidden_screen.dart';
import '../qr/presentation/qr_placeholders.dart';
import '../qr/presentation/qr_unknown_screen.dart';
import '../qr/qr_resolve_service.dart';
import '../staff/presentation/staff_invite_accept_screen.dart';
import '../staff/presentation/staff_management_screen.dart';
import '../../shared/widgets/offline_fallback_screen.dart';

Future<void> handleQr({
  required BuildContext context,
  required WidgetRef ref,
  required String raw,
}) async {
  final trimmed = raw.trim();
  final resolver = ref.read(qrResolveServiceProvider);
  QrResolveResult result;
  var resolvedFromFallback = false;

  try {
    result = await resolver.resolve(trimmed);
  } catch (_) {
    resolvedFromFallback = true;
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

  if (resolvedFromFallback &&
      (result.type == 'staff_invite' ||
          result.type == 'admin_config' ||
          result.type == 'staff_entry')) {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: const Text('Hors-ligne')),
          body: OfflineFallbackScreen(
            title: 'Hors-ligne',
            message: 'Action indisponible hors-ligne.',
            onRetry: () {
              Navigator.of(context).pop();
              handleQr(context: context, ref: ref, raw: raw);
            },
          ),
        ),
      ),
    );
    return;
  }

  if (result.type == 'entry' &&
      !_isRoleAllowed(result.grantedRole, 'entry')) {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const QrForbiddenScreen(
          roleRequired: 'entry',
        ),
      ),
    );
    return;
  }

  if (result.type == 'admin_config' &&
      !_isRoleAllowed(result.grantedRole, 'admin')) {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const QrForbiddenScreen(
          roleRequired: 'admin',
        ),
      ),
    );
    return;
  }

  if (result.type == 'staff_entry' &&
      !_isRoleAllowed(result.grantedRole, 'entry')) {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => const QrForbiddenScreen(
          roleRequired: 'entry',
        ),
      ),
    );
    return;
  }

  if (result.type != 'staff_invite') {
    final config = await _fetchConfigSafe(ref, result.eventId!);
    if (!_isFeatureEnabled(config, result.type)) {
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => QrFeatureDisabledScreen(
            featureLabel: _featureLabel(result.type),
          ),
        ),
      );
      return;
    }
  }

  switch (result.type) {
    case 'join':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => JoinEventPlaceholder(eventId: result.eventId!),
        ),
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
        MaterialPageRoute(builder: (_) => EntryModeScreen(eventId: result.eventId)),
      );
      return;
    case 'admin_config':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => AdminConfigPlaceholder(eventId: result.eventId!),
        ),
      );
      return;
    case 'staff_entry':
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      if (_isRoleAllowed(result.grantedRole, 'admin')) {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => StaffManagementScreen(eventId: result.eventId!),
          ),
        );
        return;
      }

      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => EntryModeScreen(eventId: result.eventId)),
      );
      return;
    case 'staff_invite':
      if (result.token == null || result.token!.isEmpty) {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => QrUnknownScreen(
              raw: trimmed,
              reason: 'QR staff invalide.',
            ),
          ),
        );
        return;
      }

      ref.read(appContextProvider.notifier).enterEvent(
            eventId: result.eventId!,
            eventName: 'Event #${result.eventId}',
          );

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => StaffInviteAcceptScreen(
            eventId: result.eventId!,
            token: result.token!,
          ),
        ),
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

Future<EventConfig?> _fetchConfigSafe(WidgetRef ref, int eventId) async {
  try {
    return await ref.read(eventConfigProvider(eventId).future);
  } catch (_) {
    return null;
  }
}

bool _isFeatureEnabled(EventConfig? config, String type) {
  if (config == null) return true;
  switch (type) {
    case 'menu':
      return config.menuEnabled;
    case 'entry':
      return config.entryEnabled;
    case 'admin_config':
    case 'staff_entry':
    case 'staff_invite':
      return true;
    case 'join':
    default:
      return true;
  }
}

String _featureLabel(String type) {
  switch (type) {
    case 'menu':
      return 'Menu';
    case 'entry':
      return 'Entrée';
    case 'join':
    default:
      return 'Fonction';
  }
}

QrResolveResult _localResolve(String raw) {
  final trimmed = raw.trim();
  if (trimmed.isEmpty) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      token: null,
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
      token: null,
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
      token: null,
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
      token: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  if (type != 'menu' &&
      type != 'join' &&
      type != 'entry' &&
      type != 'admin_config' &&
      type != 'staff_entry' &&
      type != 'staff_invite') {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      token: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  final token = uri.queryParameters['token'];
  if (type == 'staff_invite' && (token == null || token.isEmpty)) {
    return const QrResolveResult(
      valid: false,
      type: 'unknown',
      eventId: null,
      token: null,
      reason: 'invalid',
      requiredRole: null,
      grantedRole: null,
    );
  }

  return QrResolveResult(
    valid: true,
    type: type,
    eventId: eventId,
    token: token,
    reason: null,
    requiredRole: type == 'entry'
        ? 'entry'
        : type == 'admin_config'
            ? 'admin'
            : type == 'staff_entry'
                ? 'entry'
                : 'guest',
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
