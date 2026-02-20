class MyEventSummary {
  final int id;
  final String name;
  final DateTime startAt;
  final DateTime endAt;
  final String? venue;
  final String visibility;
  final String publicationStatus;
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
    required this.publicationStatus,
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
      publicationStatus: (json['publicationStatus'] ?? 'DRAFT').toString(),
      status: (json['eventState'] ?? json['status'] ?? 'LIVE').toString(),
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
        'publicationStatus': publicationStatus,
        'status': status,
        'modulesOn': modulesOn,
        'host_type': hostType,
        'host_id': hostId,
        'roleForMe': roleForMe,
        'canManage': canManage,
        'joined': joined,
      };
}

typedef OrgaEventSummary = MyEventSummary;



class OrgaSummary {
  const OrgaSummary({
    required this.id,
    required this.name,
    required this.city,
    required this.type,
    required this.joinMode,
    required this.followersCount,
    required this.lastActiveAt,
  });

  final int id;
  final String name;
  final String? city;
  final String? type;
  final String joinMode;
  final int followersCount;
  final DateTime? lastActiveAt;

  factory OrgaSummary.fromJson(Map<String, dynamic> json) {
    return OrgaSummary(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      city: json['city']?.toString(),
      type: (json['type'] ?? json['org_type'])?.toString(),
      joinMode: (json['joinMode'] ?? json['join_mode'] ?? 'OPEN_MEMBERSHIP').toString(),
      followersCount: (json['followersCount'] as num?)?.toInt() ?? 0,
      lastActiveAt: DateTime.tryParse((json['lastActiveAt'] ?? '').toString()),
    );
  }
}

class OrgaEventsResult {
  final Map<String, List<OrgaEventSummary>> buckets;
  final String? nextCursor;
  final bool isCached;
  final DateTime? lastSyncAt;

  const OrgaEventsResult({
    required this.buckets,
    required this.nextCursor,
    required this.isCached,
    required this.lastSyncAt,
  });
}

enum OrgaJoinMode { followOnly, openMembership, requestToJoin }
enum MembershipRole { owner, manager, staff, member, follower }
enum MembershipStatus { active, pending, rejected, left }

OrgaJoinMode parseOrgaJoinMode(String? raw) {
  switch ((raw ?? '').toUpperCase()) {
    case 'FOLLOW_ONLY':
      return OrgaJoinMode.followOnly;
    case 'REQUEST_TO_JOIN':
      return OrgaJoinMode.requestToJoin;
    default:
      return OrgaJoinMode.openMembership;
  }
}

MembershipStatus parseMembershipStatus(String? raw) {
  switch ((raw ?? '').toUpperCase()) {
    case 'PENDING':
      return MembershipStatus.pending;
    case 'REJECTED':
      return MembershipStatus.rejected;
    case 'LEFT':
      return MembershipStatus.left;
    default:
      return MembershipStatus.active;
  }
}

String orgaPrimaryCtaLabel({required OrgaJoinMode joinMode, MembershipStatus? status}) {
  if (status == MembershipStatus.pending) return 'Demande envoyée';
  if (status == MembershipStatus.active) return 'Quitter';
  switch (joinMode) {
    case OrgaJoinMode.followOnly:
      return 'Suivre';
    case OrgaJoinMode.requestToJoin:
      return 'Demander à rejoindre';
    case OrgaJoinMode.openMembership:
      return 'Rejoindre';
  }
}

class OrgaMembership {
  const OrgaMembership({required this.userId, required this.role, required this.status});

  final String userId;
  final MembershipRole role;
  final MembershipStatus status;

  factory OrgaMembership.fromJson(Map<String, dynamic> json) {
    return OrgaMembership(
      userId: (json['user_id'] ?? '').toString(),
      role: _parseMembershipRole(json['role']?.toString()),
      status: parseMembershipStatus(json['status']?.toString()),
    );
  }
}

MembershipRole _parseMembershipRole(String? raw) {
  switch ((raw ?? '').toUpperCase()) {
    case 'OWNER':
      return MembershipRole.owner;
    case 'MANAGER':
      return MembershipRole.manager;
    case 'STAFF':
      return MembershipRole.staff;
    case 'FOLLOWER':
      return MembershipRole.follower;
    default:
      return MembershipRole.member;
  }
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
