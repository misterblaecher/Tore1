enum ProfileVisibility { public, toreUsers, private }

ProfileVisibility profileVisibilityFromJson(dynamic raw) {
  switch ((raw ?? 'PRIVATE').toString().toUpperCase()) {
    case 'PUBLIC':
      return ProfileVisibility.public;
    case 'TORE_USERS':
      return ProfileVisibility.toreUsers;
    default:
      return ProfileVisibility.private;
  }
}

String profileVisibilityToJson(ProfileVisibility value) {
  switch (value) {
    case ProfileVisibility.public:
      return 'PUBLIC';
    case ProfileVisibility.toreUsers:
      return 'TORE_USERS';
    case ProfileVisibility.private:
      return 'PRIVATE';
  }
}

class ProfilePrivacy {
  final ProfileVisibility profile;
  final ProfileVisibility photo;
  final ProfileVisibility bio;
  final ProfileVisibility affiliations;
  final ProfileVisibility badges;
  final ProfileVisibility eventHistory;
  final ProfileVisibility participations;
  final ProfileVisibility gamification;
  final bool eventHistoryOptIn;
  final bool participationsOptIn;
  final bool gamificationOptIn;

  const ProfilePrivacy({
    required this.profile,
    required this.photo,
    required this.bio,
    required this.affiliations,
    required this.badges,
    required this.eventHistory,
    required this.participations,
    required this.gamification,
    required this.eventHistoryOptIn,
    required this.participationsOptIn,
    required this.gamificationOptIn,
  });

  factory ProfilePrivacy.fromJson(Map<String, dynamic> json) => ProfilePrivacy(
        profile: profileVisibilityFromJson(json['profile']),
        photo: profileVisibilityFromJson(json['photo']),
        bio: profileVisibilityFromJson(json['bio']),
        affiliations: profileVisibilityFromJson(json['affiliations']),
        badges: profileVisibilityFromJson(json['badges']),
        eventHistory: profileVisibilityFromJson(json['event_history']),
        participations: profileVisibilityFromJson(json['participations']),
        gamification: profileVisibilityFromJson(json['gamification']),
        eventHistoryOptIn: json['event_history_opt_in'] == true,
        participationsOptIn: json['participations_opt_in'] == true,
        gamificationOptIn: json['gamification_opt_in'] == true,
      );

  Map<String, dynamic> toJson() => {
        'profile': profileVisibilityToJson(profile),
        'photo': profileVisibilityToJson(photo),
        'bio': profileVisibilityToJson(bio),
        'affiliations': profileVisibilityToJson(affiliations),
        'badges': profileVisibilityToJson(badges),
        'event_history': profileVisibilityToJson(eventHistory),
        'participations': profileVisibilityToJson(participations),
        'gamification': profileVisibilityToJson(gamification),
        'event_history_opt_in': eventHistoryOptIn,
        'participations_opt_in': participationsOptIn,
        'gamification_opt_in': gamificationOptIn,
      };
}

class ProfileStructure {
  final int id;
  final String name;
  final String? slug;
  final String? city;
  final String? publicPath;

  const ProfileStructure(
      {required this.id,
      required this.name,
      this.slug,
      this.city,
      this.publicPath});

  factory ProfileStructure.fromJson(Map<String, dynamic> json) =>
      ProfileStructure(
        id: (json['id'] as num?)?.toInt() ?? 0,
        name: (json['name'] ?? '').toString(),
        slug: json['slug']?.toString(),
        city: json['city']?.toString(),
        publicPath: json['public_path']?.toString(),
      );
}

class Affiliation {
  final int id;
  final ProfileStructure structure;
  final String role;
  final String status;
  final String? startsAt;
  final String? endsAt;
  final String? mandate;
  final ProfileVisibility visibility;
  final String validationSource;

  const Affiliation({
    required this.id,
    required this.structure,
    required this.role,
    required this.status,
    this.startsAt,
    this.endsAt,
    this.mandate,
    required this.visibility,
    required this.validationSource,
  });

  factory Affiliation.fromJson(Map<String, dynamic> json) => Affiliation(
        id: (json['id'] as num?)?.toInt() ?? 0,
        structure: ProfileStructure.fromJson(
            (json['structure'] as Map).cast<String, dynamic>()),
        role: (json['role'] ?? 'MEMBER').toString(),
        status: (json['status'] ?? 'PENDING').toString(),
        startsAt: json['starts_at']?.toString(),
        endsAt: json['ends_at']?.toString(),
        mandate: json['mandate']?.toString(),
        visibility: profileVisibilityFromJson(json['visibility']),
        validationSource: (json['validation_source'] ?? 'LEGACY').toString(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'structure': {
          'id': structure.id,
          'name': structure.name,
          'slug': structure.slug,
          'city': structure.city,
          'public_path': structure.publicPath,
        },
        'role': role,
        'status': status,
        'starts_at': startsAt,
        'ends_at': endsAt,
        'mandate': mandate,
        'visibility': profileVisibilityToJson(visibility),
        'validation_source': validationSource,
      };
}

class ToreProfile {
  final String id;
  final String? username;
  final String displayName;
  final String? avatarUrl;
  final String? oripeaux;
  final String bio;
  final String? city;
  final String? createdAt;
  final String? updatedAt;
  final String accountStatus;
  final ProfilePrivacy? privacy;
  final List<Affiliation> affiliations;
  final List<Map<String, dynamic>> eventHistory;

  const ToreProfile({
    required this.id,
    this.username,
    required this.displayName,
    this.avatarUrl,
    this.oripeaux,
    required this.bio,
    this.city,
    this.createdAt,
    this.updatedAt,
    this.accountStatus = 'ACTIVE',
    this.privacy,
    this.affiliations = const [],
    this.eventHistory = const [],
  });

  bool get isMinimal => username == null || username!.isEmpty;

  factory ToreProfile.fromJson(Map<String, dynamic> json) => ToreProfile(
        id: (json['id'] ?? '').toString(),
        username: json['username']?.toString(),
        displayName: (json['display_name'] ?? '').toString(),
        avatarUrl: json['avatar_url']?.toString(),
        oripeaux: json['oripeaux']?.toString(),
        bio: (json['bio'] ?? '').toString(),
        city: json['city']?.toString(),
        createdAt: json['created_at']?.toString(),
        updatedAt: json['updated_at']?.toString(),
        accountStatus: (json['account_status'] ?? 'ACTIVE').toString(),
        privacy: json['privacy'] is Map
            ? ProfilePrivacy.fromJson(
                (json['privacy'] as Map).cast<String, dynamic>())
            : null,
        affiliations: (json['affiliations'] as List? ?? const [])
            .whereType<Map>()
            .map((item) => Affiliation.fromJson(item.cast<String, dynamic>()))
            .toList(),
        eventHistory: (json['event_history'] as List? ?? const [])
            .whereType<Map>()
            .map((item) => item.cast<String, dynamic>())
            .toList(),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'username': username,
        'display_name': displayName,
        'avatar_url': avatarUrl,
        'oripeaux': oripeaux,
        'bio': bio,
        'city': city,
        'created_at': createdAt,
        'updated_at': updatedAt,
        'account_status': accountStatus,
        if (privacy != null) 'privacy': privacy!.toJson(),
        'affiliations': affiliations.map((item) => item.toJson()).toList(),
        'event_history': eventHistory,
      };
}

class EffectiveCapabilities {
  final List<String> globalRoles;
  final List<Map<String, dynamic>> structures;
  final List<Map<String, dynamic>> events;
  final List<Map<String, dynamic>> bars;
  final bool canUseOrganizerMode;
  final bool canUseBarMode;

  const EffectiveCapabilities({
    this.globalRoles = const [],
    this.structures = const [],
    this.events = const [],
    this.bars = const [],
    this.canUseOrganizerMode = false,
    this.canUseBarMode = false,
  });

  factory EffectiveCapabilities.fromJson(Map<String, dynamic> json,
      {bool allowOperationalModes = true}) {
    List<Map<String, dynamic>> maps(dynamic value) =>
        (value as List? ?? const [])
            .whereType<Map>()
            .map((item) => item.cast<String, dynamic>())
            .toList();
    final modes = json['modes'] is Map
        ? (json['modes'] as Map).cast<String, dynamic>()
        : const <String, dynamic>{};
    return EffectiveCapabilities(
      globalRoles: (json['global_roles'] as List? ?? const [])
          .map((item) => item.toString())
          .toList(),
      structures: maps(json['structures']),
      events: maps(json['events']),
      bars: maps(json['bars']),
      canUseOrganizerMode: allowOperationalModes && modes['organizer'] == true,
      canUseBarMode: allowOperationalModes && modes['bar'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
        'global_roles': globalRoles,
        'structures': structures,
        'events': events,
        'bars': bars,
        'modes': {
          'organizer': canUseOrganizerMode,
          'bar': canUseBarMode,
        },
      };
}
