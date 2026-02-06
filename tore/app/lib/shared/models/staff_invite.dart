class StaffInvite {
  final int eventId;
  final String role;
  final String token;
  final String inviteQr;
  final String? expiresAt;

  const StaffInvite({
    required this.eventId,
    required this.role,
    required this.token,
    required this.inviteQr,
    required this.expiresAt,
  });

  factory StaffInvite.fromJson(Map<String, dynamic> json) {
    return StaffInvite(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      role: (json['role'] ?? 'entry').toString(),
      token: (json['token'] ?? '').toString(),
      inviteQr: (json['invite_qr'] ?? '').toString(),
      expiresAt: json['expires_at']?.toString(),
    );
  }
}

class StaffAcceptResult {
  final bool ok;
  final String roleGranted;

  const StaffAcceptResult({
    required this.ok,
    required this.roleGranted,
  });

  factory StaffAcceptResult.fromJson(Map<String, dynamic> json) {
    return StaffAcceptResult(
      ok: json['ok'] == true,
      roleGranted: (json['role_granted'] ?? 'entry').toString(),
    );
  }
}
