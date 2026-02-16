class MyEventSummary {
  final int id;
  final String name;
  final DateTime startAt;
  final DateTime endAt;
  final String? venue;
  final String visibility;
  final String status;
  final Map<String, dynamic> modulesOn;
  final String hostType;
  final String? hostId;
  final String roleForMe;
  final bool canManage;
  final bool joined;

  const MyEventSummary({
    required this.id,
    required this.name,
    required this.startAt,
    required this.endAt,
    required this.venue,
    required this.visibility,
    required this.status,
    required this.modulesOn,
    required this.hostType,
    required this.hostId,
    required this.roleForMe,
    required this.canManage,
    required this.joined,
  });

  factory MyEventSummary.fromJson(Map<String, dynamic> json) {
    return MyEventSummary(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startAt: DateTime.tryParse((json['startAt'] ?? '').toString()) ?? DateTime.fromMillisecondsSinceEpoch(0),
      endAt: DateTime.tryParse((json['endAt'] ?? '').toString()) ?? DateTime.fromMillisecondsSinceEpoch(0),
      venue: json['venue']?.toString(),
      visibility: (json['visibility'] ?? 'PRIVATE').toString(),
      status: (json['status'] ?? 'LIVE').toString(),
      modulesOn: Map<String, dynamic>.from((json['modulesOn'] as Map?) ?? const <String, dynamic>{}),
      hostType: (json['host_type'] ?? 'user').toString(),
      hostId: json['host_id']?.toString(),
      roleForMe: (json['roleForMe'] ?? 'MEMBER').toString(),
      canManage: json['canManage'] == true,
      joined: json['joined'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'startAt': startAt.toIso8601String(),
        'endAt': endAt.toIso8601String(),
        'venue': venue,
        'visibility': visibility,
        'status': status,
        'modulesOn': modulesOn,
        'host_type': hostType,
        'host_id': hostId,
        'roleForMe': roleForMe,
        'canManage': canManage,
        'joined': joined,
      };
}

class MyEventsFetchResult {
  final Map<String, List<MyEventSummary>> buckets;
  final bool fromCache;
  final DateTime? lastSyncAt;

  const MyEventsFetchResult({
    required this.buckets,
    required this.fromCache,
    required this.lastSyncAt,
  });
}

class ManageSnapshot {
  final int eventId;
  final String publicationStatus;
  final String visibility;
  final String runtimeState;
  final String? runtimeUpdatedAt;
  final Map<String, dynamic> share;
  final bool qrPackAvailable;
  final String? staffInviteCodeCurrent;

  const ManageSnapshot({
    required this.eventId,
    required this.publicationStatus,
    required this.visibility,
    required this.runtimeState,
    required this.runtimeUpdatedAt,
    required this.share,
    required this.qrPackAvailable,
    required this.staffInviteCodeCurrent,
  });

  factory ManageSnapshot.fromJson(Map<String, dynamic> json) {
    final runtime = Map<String, dynamic>.from((json['runtime'] as Map?) ?? const <String, dynamic>{});
    return ManageSnapshot(
      eventId: (json['eventId'] as num?)?.toInt() ?? 0,
      publicationStatus: (json['publicationStatus'] ?? 'DRAFT').toString(),
      visibility: (json['visibility'] ?? 'PRIVATE').toString(),
      runtimeState: (runtime['eventState'] ?? 'LIVE').toString(),
      runtimeUpdatedAt: runtime['lastUpdatedAt']?.toString(),
      share: Map<String, dynamic>.from((json['share'] as Map?) ?? const <String, dynamic>{}),
      qrPackAvailable: json['qrPackAvailable'] == true,
      staffInviteCodeCurrent: json['staffInviteCodeCurrent']?.toString(),
    );
  }
}
