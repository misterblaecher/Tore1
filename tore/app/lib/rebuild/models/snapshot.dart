import 'rebuild_types.dart';

class UserSnapshot {
  const UserSnapshot({
    required this.roles,
    required this.capabilities,
    required this.globalModules,
    required this.syncedAt,
  });

  final Set<String> roles;
  final Set<String> capabilities;
  final Map<String, ModuleState> globalModules;
  final DateTime syncedAt;

  Map<String, dynamic> toJson() => {
        'roles': roles.toList(growable: false),
        'capabilities': capabilities.toList(growable: false),
        'globalModules': globalModules.map((k, v) => MapEntry(k, v.name)),
        'syncedAt': syncedAt.toIso8601String(),
      };

  static UserSnapshot fromJson(Map<String, dynamic> map) => UserSnapshot(
        roles: (map['roles'] as List<dynamic>).cast<String>().toSet(),
        capabilities: (map['capabilities'] as List<dynamic>).cast<String>().toSet(),
        globalModules: (map['globalModules'] as Map<String, dynamic>).map(
          (k, v) => MapEntry(k, ModuleState.values.byName(v as String)),
        ),
        syncedAt: DateTime.parse(map['syncedAt'] as String),
      );
}
