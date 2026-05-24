import 'rebuild_types.dart';
import 'safe_parsing.dart';

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
        roles: safeGetList(map, 'roles')
            .map((e) => e.toString())
            .where((e) => e.isNotEmpty)
            .toSet(),
        capabilities: safeGetList(map, 'capabilities')
            .map((e) => e.toString())
            .where((e) => e.isNotEmpty)
            .toSet(),
        globalModules:
            safeGetMap(map, 'globalModules', aliases: const ['global_modules'])
                .map(
          (k, v) => MapEntry(k, _moduleStateFrom(v)),
        ),
        syncedAt: tryParseDateTime(map['syncedAt'], fallback: DateTime.now()),
      );
}

ModuleState _moduleStateFrom(Object? value) {
  final name = value?.toString() ?? '';
  for (final state in ModuleState.values) {
    if (state.name == name) return state;
  }
  return ModuleState.off;
}
