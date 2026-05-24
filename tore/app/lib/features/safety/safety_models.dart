class SafetyBuddyRef {
  const SafetyBuddyRef({required this.id, this.displayNameMasked});

  final String id;
  final String? displayNameMasked;

  factory SafetyBuddyRef.fromJson(Map<String, dynamic> json) {
    return SafetyBuddyRef(
      id: (json['id'] ?? json['userId'] ?? '').toString(),
      displayNameMasked:
          (json['displayNameMasked'] ?? json['display_name_masked'])
              ?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        if (displayNameMasked != null) 'displayNameMasked': displayNameMasked,
      };
}

class SafetyHistoryItem {
  const SafetyHistoryItem(
      {required this.type, required this.createdAt, this.resolvedAt});

  final String type;
  final DateTime createdAt;
  final DateTime? resolvedAt;

  factory SafetyHistoryItem.fromJson(Map<String, dynamic> json) {
    return SafetyHistoryItem(
      type: (json['type'] ?? '').toString().toUpperCase(),
      createdAt:
          DateTime.tryParse((json['createdAt'] ?? '').toString())?.toUtc() ??
              DateTime.now().toUtc(),
      resolvedAt:
          DateTime.tryParse((json['resolvedAt'] ?? '').toString())?.toUtc(),
    );
  }

  Map<String, dynamic> toJson() => {
        'type': type,
        'createdAt': createdAt.toUtc().toIso8601String(),
        if (resolvedAt != null)
          'resolvedAt': resolvedAt!.toUtc().toIso8601String(),
      };
}

class SafetyState {
  const SafetyState({
    required this.enabled,
    this.orgaPhone,
    this.messageHint,
    this.myBuddy,
    this.myLastCheckin,
    this.buddyLastCheckin,
  });

  final bool enabled;
  final String? orgaPhone;
  final String? messageHint;
  final SafetyBuddyRef? myBuddy;
  final SafetyHistoryItem? myLastCheckin;
  final SafetyHistoryItem? buddyLastCheckin;

  factory SafetyState.fromJson(Map<String, dynamic> json) {
    final myBuddyJson = json['myBuddy'];
    final myLastJson = json['myLastCheckin'];
    final buddyLastJson = json['buddyLastCheckin'];
    return SafetyState(
      enabled: json['enabled'] != false,
      orgaPhone: json['orgaPhone']?.toString(),
      messageHint: json['messageHint']?.toString(),
      myBuddy: myBuddyJson is Map
          ? SafetyBuddyRef.fromJson(Map<String, dynamic>.from(myBuddyJson))
          : null,
      myLastCheckin: myLastJson is Map
          ? SafetyHistoryItem.fromJson(Map<String, dynamic>.from(myLastJson))
          : null,
      buddyLastCheckin: buddyLastJson is Map
          ? SafetyHistoryItem.fromJson(Map<String, dynamic>.from(buddyLastJson))
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        if (orgaPhone != null) 'orgaPhone': orgaPhone,
        if (messageHint != null) 'messageHint': messageHint,
        if (myBuddy != null) 'myBuddy': myBuddy!.toJson(),
        if (myLastCheckin != null) 'myLastCheckin': myLastCheckin!.toJson(),
        if (buddyLastCheckin != null)
          'buddyLastCheckin': buddyLastCheckin!.toJson(),
      };
}

class SafetyHistoryResponse {
  const SafetyHistoryResponse({required this.items, this.buddyLastCheckin});

  final List<SafetyHistoryItem> items;
  final SafetyHistoryItem? buddyLastCheckin;

  factory SafetyHistoryResponse.fromJson(Map<String, dynamic> json) {
    final raw = (json['items'] as List<dynamic>? ?? const <dynamic>[]);
    final buddyLast = json['buddyLastCheckin'];
    return SafetyHistoryResponse(
      items: raw
          .whereType<Map>()
          .map((item) =>
              SafetyHistoryItem.fromJson(Map<String, dynamic>.from(item)))
          .toList(growable: false),
      buddyLastCheckin: buddyLast is Map
          ? SafetyHistoryItem.fromJson(Map<String, dynamic>.from(buddyLast))
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'items': items.map((item) => item.toJson()).toList(growable: false),
        if (buddyLastCheckin != null)
          'buddyLastCheckin': buddyLastCheckin!.toJson(),
      };
}
