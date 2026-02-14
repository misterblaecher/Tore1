class AppUser {
  final String id;
  final String displayName;
  final String? avatarUrl;
  final String? addressText;
  final bool showAddress;
  final bool showAvatar;
  final bool showIdentityToStaff;

  const AppUser({
    required this.id,
    required this.displayName,
    required this.avatarUrl,
    required this.addressText,
    required this.showAddress,
    required this.showAvatar,
    required this.showIdentityToStaff,
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
    };
  }

  AppUser copyWith({
    String? displayName,
    String? avatarUrl,
    String? addressText,
    bool? showAddress,
    bool? showAvatar,
    bool? showIdentityToStaff,
  }) {
    return AppUser(
      id: id,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      addressText: addressText ?? this.addressText,
      showAddress: showAddress ?? this.showAddress,
      showAvatar: showAvatar ?? this.showAvatar,
      showIdentityToStaff: showIdentityToStaff ?? this.showIdentityToStaff,
    );
  }
}
