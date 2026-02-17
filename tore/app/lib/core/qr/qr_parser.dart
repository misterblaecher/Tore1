import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

enum QrType {
  joinEvent,
  menu,
  staffEntry,
  staffBar,
  wifi,
  hunt,
  battle,
  order,
  polymarket,
  orga,
  staffInvite,
  staffBackup,
  orgaInvite,
  unknown,
}

class QrPayload {
  const QrPayload({
    required this.type,
    required this.raw,
    required this.parsedAt,
    this.version = 'v1',
    this.eventId,
    this.barId,
    this.committeeId,
    this.orderId,
    this.tokenId,
    this.battleId,
    this.betId,
    this.reason,
    this.fields = const {},
    this.expiresAt,
    this.signature,
    this.revokeToken,
  });

  final QrType type;
  final String raw;
  final DateTime parsedAt;
  final String version;
  final int? eventId;
  final int? barId;
  final int? committeeId;
  final int? orderId;
  final String? tokenId;
  final int? battleId;
  final int? betId;
  final String? reason;
  final DateTime? expiresAt;
  final String? signature;
  final String? revokeToken;
  final Map<String, String> fields;

  bool get isUnknown => type == QrType.unknown;
}

class QrParser {
  QrPayload parse(String raw) {
    final trimmed = raw.trim();
    final now = DateTime.now();
    if (trimmed.isEmpty) {
      return QrPayload(type: QrType.unknown, raw: trimmed, parsedAt: now, reason: 'format invalide');
    }

    final jsonPayload = _parseJson(trimmed);
    if (jsonPayload != null) {
      return _fromMap(trimmed, jsonPayload, now);
    }

    final uri = Uri.tryParse(trimmed);
    if (uri != null && uri.hasScheme) {
      return _fromUri(trimmed, uri, now);
    }

    return QrPayload(
      type: QrType.unknown,
      raw: trimmed,
      parsedAt: now,
      reason: 'format invalide',
      fields: {'manual_code': trimmed.toUpperCase()},
    );
  }

  QrPayload _fromUri(String raw, Uri uri, DateTime now) {
    final host = (uri.host.isNotEmpty ? uri.host : uri.pathSegments.isNotEmpty ? uri.pathSegments.first : '').toLowerCase();
    final query = uri.queryParameters.map((key, value) => MapEntry(key.toLowerCase(), value));
    final type = _mapType(host, query['type']);

    if (type == QrType.unknown) {
      return QrPayload(type: QrType.unknown, raw: raw, parsedAt: now, reason: 'format invalide', fields: query);
    }

    return QrPayload(
      type: type,
      raw: raw,
      parsedAt: now,
      eventId: _toInt(query['event_id'] ?? query['id']),
      barId: _toInt(query['bar_id']),
      committeeId: _toInt(query['committee_id'] ?? query['org_id']),
      orderId: _toInt(query['order_id']),
      tokenId: query['token'] ?? query['ot'] ?? query['token_id'] ?? query['code'],
      battleId: _toInt(query['battle_id']),
      betId: _toInt(query['bet_id']),
      expiresAt: _parseDate(query['exp'] ?? query['expires_at']),
      signature: query['sig'] ?? query['signature'] ?? query['jwt'],
      revokeToken: query['rid'] ?? query['revoke_id'],
      fields: query,
    );
  }

  QrPayload _fromMap(String raw, Map<String, dynamic> source, DateTime now) {
    final mapped = source.map((key, value) => MapEntry(key.toLowerCase(), value?.toString() ?? ''));
    final rawType = mapped['type'] ?? mapped['qr_type'] ?? mapped['kind'];
    final type = _mapType(rawType, rawType);
    return QrPayload(
      type: type,
      raw: raw,
      parsedAt: now,
      eventId: _toInt(mapped['event_id'] ?? mapped['id']),
      barId: _toInt(mapped['bar_id']),
      committeeId: _toInt(mapped['committee_id'] ?? mapped['org_id']),
      orderId: _toInt(mapped['order_id']),
      tokenId: mapped['token'] ?? mapped['ot'] ?? mapped['token_id'] ?? mapped['code'],
      battleId: _toInt(mapped['battle_id']),
      betId: _toInt(mapped['bet_id']),
      expiresAt: _parseDate(mapped['exp'] ?? mapped['expires_at']),
      signature: mapped['sig'] ?? mapped['signature'] ?? mapped['jwt'],
      revokeToken: mapped['rid'] ?? mapped['revoke_id'],
      fields: mapped,
      reason: type == QrType.unknown ? 'format invalide' : null,
    );
  }

  QrType _mapType(String? primary, String? fallback) {
    final first = (primary ?? '').toLowerCase().trim();
    final second = (fallback ?? '').toLowerCase().trim();
    final normalized = (first.isEmpty || first == 'open' || first == 'qr') ? second : first;
    switch (normalized) {
      case 'join':
      case 'join_event':
      case 'event':
        return QrType.joinEvent;
      case 'menu':
      case 'market':
        return QrType.menu;
      case 'staff_entry':
      case 'entry_staff':
      case 'entry':
        return QrType.staffEntry;
      case 'bar_staff':
      case 'staff_bar':
      case 'staff':
        return QrType.staffBar;
      case 'wifi':
      case 'wifi_token':
        return QrType.wifi;
      case 'hunt':
      case 'hunt_checkpoint':
        return QrType.hunt;
      case 'battle':
      case 'affond':
        return QrType.battle;
      case 'order':
      case 'order_client':
        return QrType.order;
      case 'polymarket':
      case 'polymarket_bet':
      case 'pm':
      case 'resolver':
        return QrType.polymarket;
      case 'orga':
      case 'orga_detail':
      case 'organization':
        return QrType.orga;
      case 'staff_invite':
      case 'event_staff_invite':
        return QrType.staffInvite;
      case 'staff_backup':
      case 'event_staff_backup':
        return QrType.staffBackup;
      case 'orga_invite':
        return QrType.orgaInvite;
      default:
        return QrType.unknown;
    }
  }

  Map<String, dynamic>? _parseJson(String input) {
    if (!(input.startsWith('{') && input.endsWith('}'))) return null;
    try {
      final decoded = jsonDecode(input);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) {
        return decoded.map((key, value) => MapEntry(key.toString(), value));
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  int? _toInt(String? value) => value == null ? null : int.tryParse(value);

  DateTime? _parseDate(String? value) {
    if (value == null || value.isEmpty) return null;
    final numeric = int.tryParse(value);
    if (numeric != null) {
      if (value.length >= 13) {
        return DateTime.fromMillisecondsSinceEpoch(numeric, isUtc: true).toLocal();
      }
      return DateTime.fromMillisecondsSinceEpoch(numeric * 1000, isUtc: true).toLocal();
    }
    return DateTime.tryParse(value)?.toLocal();
  }
}

final qrParserProvider = Provider<QrParser>((ref) => QrParser());
