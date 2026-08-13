class EventPublicView {
  const EventPublicView({
    required this.id,
    required this.name,
    required this.startAt,
    required this.endAt,
    required this.eventState,
    required this.modulesOn,
    required this.canJoin,
    required this.webUrl,
    required this.openUrl,
    required this.deeplink,
    required this.hostName,
    required this.hostInstagram,
    required this.venueName,
    required this.barName,
    required this.city,
    required this.barId,
    required this.entryPriceCents,
    required this.charterRequired,
    required this.charterVersion,
    required this.description,
    required this.currency,
    required this.accessType,
    this.shortDescription,
    this.bannerUrl,
    this.thumbnailUrl,
    this.eventType,
    this.capacity,
    this.address,
    this.lat,
    this.lng,
    this.mapUrl,
  });

  final int id;
  final String name;
  final DateTime? startAt;
  final DateTime? endAt;
  final String eventState;
  final List<String> modulesOn;
  final bool canJoin;
  final String webUrl;
  final String openUrl;
  final String deeplink;
  final String? hostName;
  final String? hostInstagram;
  final String? venueName;
  final String? barName;
  final String? city;
  final int? barId;
  final int entryPriceCents;
  final bool charterRequired;
  final String? charterVersion;
  final String? description;
  final String currency;
  final String accessType;
  final String? shortDescription;
  final String? bannerUrl;
  final String? thumbnailUrl;
  final String? eventType;
  final int? capacity;
  final String? address;
  final double? lat;
  final double? lng;
  final String? mapUrl;

  String? get imageUrl => bannerUrl ?? thumbnailUrl;

  bool get isFree => entryPriceCents <= 0;

  factory EventPublicView.fromJson(Map<String, dynamic> json) {
    final host = Map<String, dynamic>.from(
        (json['host'] as Map?) ?? const <String, dynamic>{});
    final links = Map<String, dynamic>.from(
        (json['links'] as Map?) ?? const <String, dynamic>{});
    final flags = Map<String, dynamic>.from(
        (json['flags'] as Map?) ?? const <String, dynamic>{});
    final venue = Map<String, dynamic>.from(
        (json['venue'] as Map?) ?? const <String, dynamic>{});
    final pricing = Map<String, dynamic>.from(
        (json['pricing'] as Map?) ?? const <String, dynamic>{});
    final accessPolicy = Map<String, dynamic>.from(
        (json['accessPolicy'] as Map?) ?? const <String, dynamic>{});
    final modules =
        (json['modulesOn'] as List?)?.map((e) => e.toString()).toList() ??
            const <String>[];
    return EventPublicView(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startAt: DateTime.tryParse((json['startAt'] ?? '').toString())?.toLocal(),
      endAt: DateTime.tryParse((json['endAt'] ?? '').toString())?.toLocal(),
      eventState: (json['eventState'] ?? 'LIVE').toString(),
      modulesOn: modules,
      canJoin: flags['canJoin'] == true,
      webUrl: (links['webUrl'] ?? '').toString(),
      openUrl: (links['openUrl'] ?? '').toString(),
      deeplink: (links['deeplink'] ?? '').toString(),
      hostName: host['name']?.toString(),
      hostInstagram: host['instagram']?.toString(),
      venueName: _optionalText(venue['name'] ?? venue['barName']),
      barName: _optionalText(venue['barName']),
      city: _optionalText(venue['city']),
      barId: (venue['barId'] as num?)?.toInt(),
      entryPriceCents: (pricing['entryPriceCents'] as num?)?.toInt() ?? 0,
      charterRequired: accessPolicy['charterRequired'] == true,
      charterVersion: _optionalText(accessPolicy['charterVersion']),
      description: _optionalText(json['description']),
      currency: _optionalText(pricing['currency'])?.toUpperCase() ?? 'EUR',
      accessType: _optionalText(accessPolicy['type'])?.toUpperCase() ?? 'OPEN',
      shortDescription: _optionalText(json['shortDescription']),
      bannerUrl: _httpUrl(json['bannerUrl']),
      thumbnailUrl: _httpUrl(json['thumbnailUrl']),
      eventType: _optionalText(json['eventType']),
      capacity: (json['capacity'] as num?)?.toInt(),
      address: _optionalText(venue['address']),
      lat: (venue['lat'] as num?)?.toDouble(),
      lng: (venue['lng'] as num?)?.toDouble(),
      mapUrl: _httpUrl(venue['mapUrl']),
    );
  }

  static String? _optionalText(dynamic value) {
    final text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }

  static String? _httpUrl(dynamic value) {
    final text = _optionalText(value);
    final uri = text == null ? null : Uri.tryParse(text);
    return uri != null && (uri.scheme == 'http' || uri.scheme == 'https')
        ? uri.toString()
        : null;
  }
}
