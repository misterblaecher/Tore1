enum ToreMode { user, orga, bar }
enum EventState { draft, live, paused, readOnly, ended }
enum ModuleState { on, off, frozen, readOnly }
enum ScopeBadge { global, bar, event }
enum ConnectivityState { online, degraded, offline }

class ModuleDefinition {
  const ModuleDefinition({
    required this.id,
    required this.title,
    required this.mode,
    required this.scope,
    this.sensitive = false,
    this.writeAction,
    this.details = const [],
  });

  final String id;
  final String title;
  final ToreMode mode;
  final ScopeBadge scope;
  final bool sensitive;
  final String? writeAction;
  final List<String> details;
}

class SensitiveReason {
  const SensitiveReason({required this.code, required this.text});

  final String code;
  final String text;
}
