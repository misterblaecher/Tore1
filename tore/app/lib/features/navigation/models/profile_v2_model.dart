class ProfileV2Model {
  ProfileV2Model({
    required this.id,
    required this.displayName,
    this.photoUrl,
    this.bio,
    this.instagramHandle,
    required this.visibility,
  });

  final String id;
  final String displayName;
  final String? photoUrl;
  final String? bio;
  final String? instagramHandle;
  final String visibility;

  factory ProfileV2Model.fromJson(Map<String, dynamic> json) => ProfileV2Model(
        id: json['id']?.toString() ?? '',
        displayName: json['display_name']?.toString() ?? '',
        photoUrl: json['photo_url']?.toString(),
        bio: json['bio']?.toString(),
        instagramHandle: json['instagram_handle']?.toString(),
        visibility: json['visibility']?.toString() ?? 'PUBLIC',
      );
}
