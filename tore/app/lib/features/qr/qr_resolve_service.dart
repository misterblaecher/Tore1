import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../../core/network/providers.dart';

class QrResolveResult {
  final bool valid;
  final String type;
  final int? eventId;
  final String? reason;
  final String? requiredRole;
  final String? grantedRole;

  const QrResolveResult({
    required this.valid,
    required this.type,
    required this.eventId,
    required this.reason,
    required this.requiredRole,
    required this.grantedRole,
  });

  factory QrResolveResult.fromJson(Map<String, dynamic> json) {
    return QrResolveResult(
      valid: json['valid'] == true,
      type: (json['type'] ?? 'unknown').toString(),
      eventId: json['event_id'] is num ? (json['event_id'] as num).toInt() : null,
      reason: json['reason']?.toString(),
      requiredRole: json['required_role']?.toString(),
      grantedRole: json['granted_role']?.toString(),
    );
  }
}

class QrResolveService {
  QrResolveService(this._client);

  final ApiClient _client;

  Future<QrResolveResult> resolve(String raw) async {
    final res = await _client.dio.post('/qr/resolve', data: {'raw': raw});
    return QrResolveResult.fromJson(
      Map<String, dynamic>.from(res.data as Map),
    );
  }
}

final qrResolveServiceProvider = Provider<QrResolveService>((ref) {
  final client = ref.watch(apiClientProvider);
  return QrResolveService(client);
});
