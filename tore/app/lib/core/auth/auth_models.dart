enum AccountMode { user, organizer, team }

AccountMode accountModeFromJson(dynamic raw) {
  final value = (raw ?? 'user').toString().toLowerCase();
  switch (value) {
    case 'organizer':
      return AccountMode.organizer;
    case 'team':
      return AccountMode.team;
    default:
      return AccountMode.user;
  }
}

String accountModeToJson(AccountMode mode) => mode.name;

class RoleUpgradeRequest {
  final int id;
  final AccountMode requestedMode;
  final String status;

  const RoleUpgradeRequest(
      {required this.id, required this.requestedMode, required this.status});

  factory RoleUpgradeRequest.fromJson(Map<String, dynamic> json) {
    return RoleUpgradeRequest(
      id: (json['id'] as num?)?.toInt() ?? 0,
      requestedMode: accountModeFromJson(json['requested_mode']),
      status: (json['status'] ?? 'pending').toString(),
    );
  }
}

class AppUser {
  final String id;
  final String displayName;
  final String? avatarUrl;
  final String? addressText;
  final bool showAddress;
  final bool showAvatar;
  final bool showIdentityToStaff;
  final String bio;
  final String visibility;
  final bool showIdentityInBar;
  final AccountMode accountMode;
  final RoleUpgradeRequest? roleRequestPending;

  const AppUser({
    required this.id,
    required this.displayName,
    required this.avatarUrl,
    required this.addressText,
    required this.showAddress,
    required this.showAvatar,
    required this.showIdentityToStaff,
    this.bio = '',
    required this.visibility,
    required this.showIdentityInBar,
    this.accountMode = AccountMode.user,
    this.roleRequestPending,
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: (json['id'] ?? '').toString(),
      displayName: (json['display_name'] ?? '').toString(),
      avatarUrl: json['avatar_url']?.toString(),
      addressText: json['address_text']?.toString(),
      showAddress: (json['show_address'] as bool?) ?? false,
      showAvatar: (json['show_avatar'] as bool?) ?? true,
      showIdentityToStaff: (json['show_identity_to_staff'] as bool?) ?? false,
      bio: (json['bio'] ?? '').toString(),
      visibility: (json['visibility'] ?? 'public').toString(),
      showIdentityInBar: (json['show_identity_in_bar'] as bool?) ?? false,
      accountMode: accountModeFromJson(json['account_mode']),
      roleRequestPending: json['role_request_pending'] is Map<String, dynamic>
          ? RoleUpgradeRequest.fromJson(
              json['role_request_pending'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toPatchJson() {
    return {
      'display_name': displayName,
      'avatar_url': avatarUrl,
      'address_text': addressText,
      'show_address': showAddress,
      'show_avatar': showAvatar,
      'show_identity_to_staff': showIdentityToStaff,
      'bio': bio,
      'visibility': visibility,
      'show_identity_in_bar': showIdentityInBar,
      'account_mode': accountModeToJson(accountMode),
    };
  }

  bool get canUseOrganizerMode => accountMode == AccountMode.organizer;

  bool get canUseBarMode => accountMode == AccountMode.team;

  AppUser copyWith({
    String? displayName,
    String? avatarUrl,
    String? addressText,
    bool? showAddress,
    bool? showAvatar,
    bool? showIdentityToStaff,
    String? bio,
    String? visibility,
    bool? showIdentityInBar,
    AccountMode? accountMode,
  }) {
    return AppUser(
      id: id,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      addressText: addressText ?? this.addressText,
      showAddress: showAddress ?? this.showAddress,
      showAvatar: showAvatar ?? this.showAvatar,
      showIdentityToStaff: showIdentityToStaff ?? this.showIdentityToStaff,
      bio: bio ?? this.bio,
      visibility: visibility ?? this.visibility,
      showIdentityInBar: showIdentityInBar ?? this.showIdentityInBar,
      accountMode: accountMode ?? this.accountMode,
      roleRequestPending: roleRequestPending,
    );
  }
}
