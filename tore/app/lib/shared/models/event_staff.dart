class EventStaffMember {
  final String userId;
  final String? displayName;
  final String role;
  final bool isActive;
  final String? createdAt;
  final String? createdByUserId;
  final String? revokedAt;
  final String? revokedByUserId;

  const EventStaffMember({
    required this.userId,
    required this.displayName,
    required this.role,
    required this.isActive,
    required this.createdAt,
    required this.createdByUserId,
    required this.revokedAt,
    required this.revokedByUserId,
  });

  factory EventStaffMember.fromJson(Map<String, dynamic> json) {
    return EventStaffMember(
      userId: (json['user_id'] ?? '').toString(),
      displayName: json['display_name']?.toString(),
      role: (json['role'] ?? 'entry').toString(),
      isActive: json['is_active'] == true,
      createdAt: json['created_at']?.toString(),
      createdByUserId: json['created_by_user_id']?.toString(),
      revokedAt: json['revoked_at']?.toString(),
      revokedByUserId: json['revoked_by_user_id']?.toString(),
    );
  }
}
