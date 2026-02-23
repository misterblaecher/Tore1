import 'package:flutter/material.dart';

import '../../models/event_context.dart';
import '../../models/rebuild_types.dart';
import '../../models/snapshot.dart';

class HeaderCard extends StatelessWidget {
  const HeaderCard({super.key, required this.userSnapshot, required this.eventContext});

  final UserSnapshot? userSnapshot;
  final EventContext? eventContext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Snapshot /me: roles=${userSnapshot?.roles.join(',') ?? '-'} | caps=${userSnapshot?.capabilities.join(',') ?? '-'}'),
            const SizedBox(height: 6),
            Text('Context /events/{id}/context: state=${eventContext?.eventState.name.toUpperCase() ?? 'DRAFT'}'),
            const SizedBox(height: 6),
            Text('Event synced: ${eventContext?.syncedAt.toIso8601String() ?? 'never'}', style: const TextStyle(fontFamily: 'monospace')),
          ],
        ),
      ),
    );
  }
}

class ModuleCard extends StatelessWidget {
  const ModuleCard({super.key, required this.def, required this.state, required this.onOpen});

  final ModuleDefinition def;
  final ModuleState state;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final frozen = state == ModuleState.frozen || state == ModuleState.readOnly;
    return Card(
      child: ListTile(
        title: Text(def.title),
        subtitle: Text('${def.scope.name.toUpperCase()} • ${state.name.toUpperCase()}'),
        trailing: Wrap(
          spacing: 8,
          children: [
            ToreBadge(label: def.scope.name.toUpperCase()),
            if (def.sensitive) const ToreBadge(label: 'SENSITIVE'),
          ],
        ),
        onTap: frozen ? null : onOpen,
      ),
    );
  }
}

/// Keep a Tore-specific name to avoid collisions with Flutter Material widgets (e.g., Badge).
class ToreBadge extends StatelessWidget {
  const ToreBadge({super.key, required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFFBA1733),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: const TextStyle(fontSize: 11)),
    );
  }
}

class ModeChip extends StatelessWidget {
  const ModeChip({super.key, required this.mode, required this.onChanged, required this.allowed});
  final ToreMode mode;
  final ValueChanged<ToreMode> onChanged;
  final bool Function(ToreMode mode) allowed;

  @override
  Widget build(BuildContext context) {
    return DropdownButton<ToreMode>(
      value: mode,
      dropdownColor: const Color(0xFF111118),
      onChanged: (value) {
        if (value != null && allowed(value)) {
          onChanged(value);
        }
      },
      items: ToreMode.values.where(allowed).map((m) => DropdownMenuItem(value: m, child: Text(m.name.toUpperCase()))).toList(growable: false),
    );
  }
}

class NetworkChip extends StatelessWidget {
  const NetworkChip({super.key, required this.network, required this.onChanged});

  final ConnectivityState network;
  final ValueChanged<ConnectivityState> onChanged;

  @override
  Widget build(BuildContext context) {
    return DropdownButton<ConnectivityState>(
      value: network,
      dropdownColor: const Color(0xFF111118),
      onChanged: (value) {
        if (value != null) onChanged(value);
      },
      items: ConnectivityState.values.map((n) => DropdownMenuItem(value: n, child: Text(n.name.toUpperCase()))).toList(growable: false),
    );
  }
}

class NetworkBanner extends StatelessWidget {
  const NetworkBanner({super.key, required this.state});

  final ConnectivityState state;

  @override
  Widget build(BuildContext context) {
    if (state == ConnectivityState.online) {
      return const SizedBox.shrink();
    }
    final message = state == ConnectivityState.degraded
        ? 'DEGRADED: lecture cache prioritaire, latence backend possible.'
        : 'OFFLINE: écritures bloquées, lecture via cache uniquement.';
    final color = state == ConnectivityState.degraded ? Colors.orange : Colors.red;
    return Card(
      color: color.withOpacity(0.15),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Text(message),
      ),
    );
  }
}
