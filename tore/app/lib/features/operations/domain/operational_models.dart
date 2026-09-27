enum OperationalMode { user, orga, bar }

class ScopedCapability {
  const ScopedCapability({
    required this.id,
    required this.type,
    required this.scope,
    required this.role,
    required this.actions,
    required this.source,
    this.eventId,
    this.barId,
    this.expiresAt,
    this.event = const {},
    this.bar = const {},
  });

  final String id;
  final String type;
  final String scope;
  final int? eventId;
  final int? barId;
  final String role;
  final Set<String> actions;
  final String source;
  final DateTime? expiresAt;
  final Map<String, dynamic> event;
  final Map<String, dynamic> bar;

  bool get isEvent => type == 'EVENT' && eventId != null;
  bool get isBar => type == 'BAR' && barId != null;
  bool allows(String action) => actions.contains(action);

  String get displayName =>
      (isEvent ? event['name'] : bar['name'])?.toString() ?? scope;

  factory ScopedCapability.fromJson(Map<String, dynamic> json) {
    Set<String> strings(dynamic value) =>
        (value as List? ?? const []).map((item) => item.toString()).toSet();
    Map<String, dynamic> map(dynamic value) =>
        value is Map ? value.cast<String, dynamic>() : <String, dynamic>{};
    return ScopedCapability(
      id: (json['id'] ?? '').toString(),
      type: (json['type'] ?? '').toString().toUpperCase(),
      scope: (json['scope'] ?? '').toString(),
      eventId: (json['event_id'] as num?)?.toInt(),
      barId: (json['bar_id'] as num?)?.toInt(),
      role: (json['role'] ?? '').toString().toUpperCase(),
      actions: strings(json['actions']),
      source: (json['source'] ?? '').toString(),
      expiresAt: DateTime.tryParse(json['expires_at']?.toString() ?? ''),
      event: map(json['event']),
      bar: map(json['bar']),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'scope': scope,
        'event_id': eventId,
        'bar_id': barId,
        'role': role,
        'actions': actions.toList()..sort(),
        'source': source,
        'expires_at': expiresAt?.toIso8601String(),
        if (event.isNotEmpty) 'event': event,
        if (bar.isNotEmpty) 'bar': bar,
      };
}

class OperationalCapabilities {
  const OperationalCapabilities({
    required this.userId,
    this.events = const [],
    this.bars = const [],
    this.evaluatedAt,
  });

  final String userId;
  final List<ScopedCapability> events;
  final List<ScopedCapability> bars;
  final DateTime? evaluatedAt;

  bool get canUseOrga => events.isNotEmpty;
  bool get canUseBar => bars.isNotEmpty;

  factory OperationalCapabilities.fromJson(Map<String, dynamic> json) {
    List<ScopedCapability> capabilities(dynamic value) => (value as List? ??
            const [])
        .whereType<Map>()
        .map((item) => ScopedCapability.fromJson(item.cast<String, dynamic>()))
        .toList(growable: false);
    return OperationalCapabilities(
      userId: (json['user_id'] ?? '').toString(),
      events: capabilities(json['events'])
          .where((item) => item.isEvent)
          .toList(growable: false),
      bars: capabilities(json['bars'])
          .where((item) => item.isBar)
          .toList(growable: false),
      evaluatedAt: DateTime.tryParse(json['evaluated_at']?.toString() ?? ''),
    );
  }
}

class OperationalSelection {
  const OperationalSelection.user()
      : mode = OperationalMode.user,
        scopeId = null,
        capability = null;

  const OperationalSelection.scoped({
    required this.mode,
    required this.scopeId,
    required this.capability,
  });

  final OperationalMode mode;
  final int? scopeId;
  final ScopedCapability? capability;
}

class OperationalGuard {
  const OperationalGuard._();

  // The existing report API requires the event admin role. Operational
  // MANAGER and ADMIN are the corresponding scoped capabilities.
  static bool canViewReport(ScopedCapability capability, int eventId) =>
      capability.isEvent &&
      capability.eventId == eventId &&
      capability.allows('event.view_ops') &&
      (capability.role == 'MANAGER' || capability.role == 'ADMIN');

  static bool canEnter({
    required OperationalMode mode,
    required int scopeId,
    required OperationalCapabilities capabilities,
  }) {
    if (mode == OperationalMode.orga) {
      return capabilities.events.any((item) => item.eventId == scopeId);
    }
    if (mode == OperationalMode.bar) {
      return capabilities.bars.any((item) => item.barId == scopeId);
    }
    return false;
  }

  static bool canPerform({
    required ScopedCapability? capability,
    required String action,
    required OperationalMode mode,
    required int scopeId,
  }) {
    if (capability == null || !capability.allows(action)) return false;
    if (mode == OperationalMode.orga) return capability.eventId == scopeId;
    if (mode == OperationalMode.bar) return capability.barId == scopeId;
    return false;
  }

  static bool allowsDeepLink({
    required OperationalCapabilities capabilities,
    required OperationalMode mode,
    required int scopeId,
    required String action,
  }) {
    final candidates = mode == OperationalMode.orga
        ? capabilities.events
        : mode == OperationalMode.bar
            ? capabilities.bars
            : const <ScopedCapability>[];
    final capability = candidates.where((item) =>
        (mode == OperationalMode.orga ? item.eventId : item.barId) == scopeId);
    return capability.any((item) => item.allows(action));
  }
}
