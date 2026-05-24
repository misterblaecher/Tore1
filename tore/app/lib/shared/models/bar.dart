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
    );
  }

  static String? _optionalText(dynamic value) {
    final text = value?.toString() ?? '';
    return text.trim().isEmpty ? null : text;
  }
}
