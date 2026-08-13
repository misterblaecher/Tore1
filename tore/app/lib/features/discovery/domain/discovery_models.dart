enum DiscoveryStatus { all, live, tonight, upcoming }

extension DiscoveryStatusQuery on DiscoveryStatus {
  String? get apiValue {
    switch (this) {
      case DiscoveryStatus.all:
        return null;
      case DiscoveryStatus.live:
        return 'LIVE';
      case DiscoveryStatus.tonight:
        return 'TONIGHT';
      case DiscoveryStatus.upcoming:
        return 'UPCOMING';
    }
  }

  String get label {
    switch (this) {
      case DiscoveryStatus.all:
        return 'Tout';
      case DiscoveryStatus.live:
        return 'Live';
      case DiscoveryStatus.tonight:
        return 'Ce soir';
      case DiscoveryStatus.upcoming:
        return 'À venir';
    }
  }
}

class DiscoveryQuery {
  const DiscoveryQuery({
    this.search = '',
    this.status = DiscoveryStatus.all,
    this.city,
    this.barId,
    this.structureId,
  });

  final String search;
  final DiscoveryStatus status;
  final String? city;
  final int? barId;
  final int? structureId;

  Map<String, dynamic> toQueryParameters() => {
        if (search.trim().isNotEmpty) 'query': search.trim(),
        if (status.apiValue != null) 'status': status.apiValue,
        if ((city ?? '').trim().isNotEmpty) 'city': city!.trim(),
        if (barId != null) 'bar_id': barId,
        if (structureId != null) 'structure_id': structureId,
        'limit': 100,
      };

  DiscoveryQuery copyWith({
    String? search,
    DiscoveryStatus? status,
    String? city,
    int? barId,
    int? structureId,
    bool clearBar = false,
    bool clearCity = false,
    bool clearStructure = false,
  }) {
    return DiscoveryQuery(
      search: search ?? this.search,
      status: status ?? this.status,
      city: clearCity ? null : (city ?? this.city),
      barId: clearBar ? null : (barId ?? this.barId),
      structureId: clearStructure ? null : (structureId ?? this.structureId),
    );
  }

  @override
  bool operator ==(Object other) =>
      other is DiscoveryQuery &&
      other.search == search &&
      other.status == status &&
      other.city == city &&
      other.barId == barId &&
      other.structureId == structureId;

  @override
  int get hashCode => Object.hash(search, status, city, barId, structureId);
}

class DiscoveryEvent {
  const DiscoveryEvent({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.endsAt,
    required this.status,
    required this.eventState,
    required this.entryPriceCents,
    required this.modules,
    this.barId,
    this.barName,
    this.city,
    this.venue,
    this.hostName,
    this.hostType,
    this.shortDescription,
    this.bannerUrl,
    this.thumbnailUrl,
    this.eventType,
    this.capacity,
    this.accessType,
    this.currency = 'EUR',
    this.address,
    this.lat,
    this.lng,
  });

  final int id;
  final String name;
  final DateTime startsAt;
  final DateTime endsAt;
  final String status;
  final String eventState;
  final int entryPriceCents;
  final List<String> modules;
  final int? barId;
  final String? barName;
  final String? city;
  final String? venue;
  final String? hostName;
  final String? hostType;
  final String? shortDescription;
  final String? bannerUrl;
  final String? thumbnailUrl;
  final String? eventType;
  final int? capacity;
  final String? accessType;
  final String currency;
  final String? address;
  final double? lat;
  final double? lng;

  String? get imageUrl => bannerUrl ?? thumbnailUrl;

  bool get isLive => status.toUpperCase() == 'LIVE';
  bool get isFree => entryPriceCents <= 0;

  factory DiscoveryEvent.fromJson(Map<String, dynamic> json) {
    final host = Map<String, dynamic>.from(
        (json['host'] as Map?) ?? const <String, dynamic>{});
    return DiscoveryEvent(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startsAt:
          DateTime.tryParse((json['starts_at'] ?? '').toString())?.toLocal() ??
              DateTime.fromMillisecondsSinceEpoch(0),
      endsAt:
          DateTime.tryParse((json['ends_at'] ?? '').toString())?.toLocal() ??
              DateTime.fromMillisecondsSinceEpoch(0),
      status: (json['status'] ?? 'UPCOMING').toString(),
      eventState: (json['eventState'] ?? 'LIVE').toString(),
      entryPriceCents: (json['entry_price_cents'] as num?)?.toInt() ?? 0,
      modules: (json['modulesOn'] as List?)
              ?.map((item) => item.toString())
              .toList(growable: false) ??
          const [],
      barId: (json['bar_id'] as num?)?.toInt(),
      barName: _optionalText(json['barName']),
      city: _optionalText(json['city']),
      venue: _optionalText(json['venue']),
      hostName: _optionalText(host['name']),
      hostType: _optionalText(host['type']),
      shortDescription: _optionalText(json['shortDescription']),
      bannerUrl: _httpUrl(json['bannerUrl']),
      thumbnailUrl: _httpUrl(json['thumbnailUrl']),
      eventType: _optionalText(json['eventType']),
      capacity: (json['capacity'] as num?)?.toInt(),
      accessType: _optionalText(json['accessType']),
      currency: _optionalText(json['currency'])?.toUpperCase() ?? 'EUR',
      address: _optionalText(json['address']),
      lat: (json['lat'] as num?)?.toDouble(),
      lng: (json['lng'] as num?)?.toDouble(),
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

class DiscoveryResult {
  const DiscoveryResult({
    required this.events,
    required this.fromCache,
    required this.lastSyncAt,
  });

  final List<DiscoveryEvent> events;
  final bool fromCache;
  final DateTime lastSyncAt;
}
