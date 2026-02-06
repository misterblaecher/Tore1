class EventConfig {
  final int eventId;
  final bool menuEnabled;
  final bool walletEnabled;
  final bool entryEnabled;
  final bool checkinEnabled;
  final bool battlesEnabled;
  final bool huntEnabled;
  final bool reportEnabled;
  final String? updatedAt;
  final String? updatedByUserId;
  final String? role;

  const EventConfig({
    required this.eventId,
    required this.menuEnabled,
    required this.walletEnabled,
    required this.entryEnabled,
    required this.checkinEnabled,
    required this.battlesEnabled,
    required this.huntEnabled,
    required this.reportEnabled,
    required this.updatedAt,
    required this.updatedByUserId,
    required this.role,
  });

  factory EventConfig.fromJson(Map<String, dynamic> json) {
    return EventConfig(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      menuEnabled: json['menu_enabled'] == true,
      walletEnabled: json['wallet_enabled'] == true,
      entryEnabled: json['entry_enabled'] == true,
      checkinEnabled: json['checkin_enabled'] == true,
      battlesEnabled: json['battles_enabled'] == true,
      huntEnabled: json['hunt_enabled'] == true,
      reportEnabled: json['report_enabled'] == true,
      updatedAt: json['updated_at']?.toString(),
      updatedByUserId: json['updated_by_user_id']?.toString(),
      role: json['role']?.toString(),
    );
  }

  static EventConfig fallback(int eventId) {
    return EventConfig(
      eventId: eventId,
      menuEnabled: true,
      walletEnabled: true,
      entryEnabled: false,
      checkinEnabled: false,
      battlesEnabled: false,
      huntEnabled: false,
      reportEnabled: false,
      updatedAt: null,
      updatedByUserId: null,
      role: null,
    );
  }
}
