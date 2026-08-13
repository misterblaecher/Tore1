class Bar {
  final int id;
  final String name;
  final String city;
  final String? status;
  final String? district;
  final String? style;
  final String? distanceLabel;
  final String? tickerLine;
  final String? lastEvent;
  final String? description;
  final String? logoUrl;
  final String? bannerUrl;
  final String? primaryColor;
  final String? secondaryColor;
  final String? address;
  final String? practicalInfo;
  final String? mapUrl;
  final double? lat;
  final double? lng;
  final List<String> modules;

  const Bar({
    required this.id,
    required this.name,
    required this.city,
    this.status,
    this.district,
    this.style,
    this.distanceLabel,
    this.tickerLine,
    this.lastEvent,
    this.description,
    this.logoUrl,
    this.bannerUrl,
    this.primaryColor,
    this.secondaryColor,
    this.address,
    this.practicalInfo,
    this.mapUrl,
    this.lat,
    this.lng,
    this.modules = const [],
  });

  factory Bar.fromJson(Map<String, dynamic> json) {
    return Bar(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      city: (json['city'] ?? '').toString(),
      status: _optionalText(json['status']),
      district: _optionalText(json['district'] ?? json['neighborhood']),
      style: _optionalText(json['style']),
      distanceLabel: _optionalText(json['distance'] ?? json['distance_label']),
      tickerLine: _optionalText(json['ticker_line']),
      lastEvent: _optionalText(
          json['lastEvent']?['name'] ?? json['last_event']?['name']),
      description:
          _optionalText(json['description'] ?? json['public_description']),
      logoUrl: _httpUrl(json['logoUrl'] ?? json['logo_url']),
      bannerUrl: _httpUrl(json['bannerUrl'] ?? json['banner_url']),
      primaryColor: _hexColor(json['primaryColor'] ?? json['primary_color']),
      secondaryColor:
          _hexColor(json['secondaryColor'] ?? json['secondary_color']),
      address: _optionalText(json['address']),
      practicalInfo:
          _optionalText(json['practicalInfo'] ?? json['practical_info']),
      mapUrl: _httpUrl(json['mapUrl'] ?? json['map_url']),
      lat: (json['lat'] as num?)?.toDouble(),
      lng: (json['lng'] as num?)?.toDouble(),
      modules: (json['modules'] as List?)
              ?.map((item) => item.toString())
              .toList(growable: false) ??
          const [],
    );
  }

  static String? _optionalText(dynamic value) {
    final text = value?.toString() ?? '';
    return text.trim().isEmpty ? null : text;
  }

  static String? _httpUrl(dynamic value) {
    final text = _optionalText(value);
    final uri = text == null ? null : Uri.tryParse(text);
    return uri != null && (uri.scheme == 'http' || uri.scheme == 'https')
        ? uri.toString()
        : null;
  }

  static String? _hexColor(dynamic value) {
    final text = _optionalText(value)?.toUpperCase();
    return text != null && RegExp(r'^#[0-9A-F]{6}$').hasMatch(text)
        ? text
        : null;
  }
}
