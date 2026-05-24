class GlossaryCommittee {
  const GlossaryCommittee(
      {required this.id, required this.name, this.shortName});

  final int id;
  final String name;
  final String? shortName;

  factory GlossaryCommittee.fromJson(Map<String, dynamic> json) {
    return GlossaryCommittee(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['name'] ?? '').toString(),
      shortName: (json['shortName'] ?? json['slug'])?.toString(),
    );
  }
}

class GlossarySettings {
  const GlossarySettings(
      {required this.publicEnabled, required this.availableTags});

  final bool publicEnabled;
  final List<String> availableTags;

  factory GlossarySettings.fromJson(Map<String, dynamic> json) {
    return GlossarySettings(
      publicEnabled:
          json['publicEnabled'] == true || json['public_enabled'] == true,
      availableTags: ((json['availableTags'] as List?) ?? const <dynamic>[])
          .map((e) => e.toString())
          .toList(growable: false),
    );
  }

  Map<String, dynamic> toJson() => {
        'publicEnabled': publicEnabled,
        'availableTags': availableTags,
      };
}

class GlossaryTerm {
  const GlossaryTerm({
    required this.id,
    required this.committeeId,
    this.yearId,
    required this.term,
    required this.definition,
    this.examples,
    required this.tags,
    required this.isOfficial,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final int committeeId;
  final int? yearId;
  final String term;
  final String definition;
  final String? examples;
  final List<String> tags;
  final bool isOfficial;
  final String status;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory GlossaryTerm.fromJson(Map<String, dynamic> json) {
    return GlossaryTerm(
      id: (json['id'] as num?)?.toInt() ?? 0,
      committeeId: (json['committeeId'] as num?)?.toInt() ?? 0,
      yearId: (json['yearId'] as num?)?.toInt(),
      term: (json['term'] ?? '').toString(),
      definition: (json['definition'] ?? '').toString(),
      examples: json['examples']?.toString(),
      tags: ((json['tags'] as List?) ?? const <dynamic>[])
          .map((e) => e.toString())
          .toList(growable: false),
      isOfficial: json['isOfficial'] == true,
      status: (json['status'] ?? '').toString(),
      createdAt:
          DateTime.tryParse((json['createdAt'] ?? '').toString())?.toUtc() ??
              DateTime.now().toUtc(),
      updatedAt:
          DateTime.tryParse((json['updatedAt'] ?? '').toString())?.toUtc() ??
              DateTime.now().toUtc(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'committeeId': committeeId,
        'yearId': yearId,
        'term': term,
        'definition': definition,
        'examples': examples,
        'tags': tags,
        'isOfficial': isOfficial,
        'status': status,
        'createdAt': createdAt.toIso8601String(),
        'updatedAt': updatedAt.toIso8601String(),
      };
}

class GlossaryTermsPage {
  const GlossaryTermsPage(
      {required this.items, this.nextCursor, this.serverTime});

  final List<GlossaryTerm> items;
  final String? nextCursor;
  final DateTime? serverTime;

  factory GlossaryTermsPage.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['items'] as List?) ?? const <dynamic>[];
    return GlossaryTermsPage(
      items: rawItems
          .whereType<Map>()
          .map((e) => GlossaryTerm.fromJson(Map<String, dynamic>.from(e)))
          .toList(growable: false),
      nextCursor: json['nextCursor']?.toString(),
      serverTime:
          DateTime.tryParse((json['serverTime'] ?? '').toString())?.toUtc(),
    );
  }

  Map<String, dynamic> toJson() => {
        'items': items.map((e) => e.toJson()).toList(growable: false),
        'nextCursor': nextCursor,
        'serverTime': serverTime?.toIso8601String(),
      };
}
