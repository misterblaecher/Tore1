import '../models/rebuild_types.dart';
import '../models/snapshot.dart';

class RouteGuards {
  bool modeAllowed(ToreMode mode, UserSnapshot? userSnapshot) {
    final roles = userSnapshot?.roles ?? const <String>{};
    final caps = userSnapshot?.capabilities ?? const <String>{};
    if (mode == ToreMode.user) return true;
    if (mode == ToreMode.orga) return roles.contains('ORGA') || caps.contains('can_access_orga');
    return roles.contains('BAR') || caps.contains('can_access_bar');
  }

  bool deepLinkAllowed(ModuleState state) => state != ModuleState.off;
}
