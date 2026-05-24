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

  factory EventPublicView.fromJson(Map<String, dynamic> json) {
    final host = Map<String, dynamic>.from(
        (json['host'] as Map?) ?? const <String, dynamic>{});
    final links = Map<String, dynamic>.from(
        (json['links'] as Map?) ?? const <String, dynamic>{});
    final flags = Map<String, dynamic>.from(
        (json['flags'] as Map?) ?? const <String, dynamic>{});
    final venue = Map<String, dynamic>.from(
        (json['venue'] as Map?) ?? const <String, dynamic>{});
    final modules =
        (json['modulesOn'] as List?)?.map((e) => e.toString()).toList() ??
            const <String>[];
    return EventPublicView(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      startAt: DateTime.tryParse((json['startAt'] ?? '').toString()),
      endAt: DateTime.tryParse((json['endAt'] ?? '').toString()),
      eventState: (json['eventState'] ?? 'LIVE').toString(),
      modulesOn: modules,
      canJoin: flags['canJoin'] == true,
      webUrl: (links['webUrl'] ?? '').toString(),
      openUrl: (links['openUrl'] ?? '').toString(),
      deeplink: (links['deeplink'] ?? '').toString(),
      hostName: host['name']?.toString(),
      hostInstagram: host['instagram']?.toString(),
      venueName: (venue['name'] ?? venue['barName'])?.toString(),
    );
  }
}
