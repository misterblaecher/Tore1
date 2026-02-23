import 'package:flutter/material.dart';

import '../../models/event_context.dart';
import '../../models/rebuild_types.dart';
import '../../models/snapshot.dart';
import '../theme/tore_theme.dart';

class HeaderCard extends StatelessWidget {
  const HeaderCard({super.key, required this.userSnapshot, required this.eventContext});
  final UserSnapshot? userSnapshot;
  final EventContext? eventContext;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('roles: ${userSnapshot?.roles.join(', ') ?? '-'}'),
          Text('caps: ${userSnapshot?.capabilities.join(', ') ?? '-'}'),
          Text('event: ${eventContext?.eventId ?? '-'} • ${eventContext?.eventState.name.toUpperCase() ?? 'DRAFT'}'),
          Text('synced: ${eventContext?.syncedAt.toIso8601String() ?? 'never'}', style: const TextStyle(fontFamily: 'monospace')),
        ]),
      ),
    );
  }
}

class ToreBadge extends StatelessWidget {
  const ToreBadge({super.key, required this.label, this.color = ToreTokens.ruby});
  final String label;
  final Color color;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: ToreTokens.s8, vertical: ToreTokens.s4),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)),
      child: Text(label, style: const TextStyle(fontSize: 11)),
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
    return Card(
      child: ListTile(
        title: Text(def.title),
        subtitle: Text('${def.id} • ${state.name.toUpperCase()}'),
        trailing: ToreBadge(label: def.scope.name.toUpperCase()),
        onTap: onOpen,
      ),
    );
  }
}

class NetworkBanner extends StatelessWidget {
  const NetworkBanner({super.key, required this.state});
  final ConnectivityState state;

  @override
  Widget build(BuildContext context) {
    if (state == ConnectivityState.online) return const SizedBox.shrink();
    final offline = state == ConnectivityState.offline;
    return Card(
      color: offline ? Colors.red.withOpacity(0.15) : Colors.orange.withOpacity(0.15),
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s8),
        child: Text(offline ? 'Offline: cache-only read, writes blocked.' : 'Network degraded: cache-first read enabled.'),
      ),
    );
  }
}

class ConfirmDialogWithReason extends StatefulWidget {
  const ConfirmDialogWithReason({super.key, required this.title});
  final String title;

  static Future<SensitiveReason?> show(BuildContext context, {required String title}) {
    return showDialog<SensitiveReason>(context: context, builder: (_) => ConfirmDialogWithReason(title: title));
  }

  @override
  State<ConfirmDialogWithReason> createState() => _ConfirmDialogWithReasonState();
}

class _ConfirmDialogWithReasonState extends State<ConfirmDialogWithReason> {
  final _code = TextEditingController();
  final _text = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: _code, decoration: const InputDecoration(labelText: 'reason_code')),
        const SizedBox(height: ToreTokens.s8),
        TextField(controller: _text, decoration: const InputDecoration(labelText: 'reason_text')),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () {
            if (_code.text.trim().isEmpty || _text.text.trim().isEmpty) return;
            Navigator.pop(context, SensitiveReason(code: _code.text.trim(), text: _text.text.trim()));
          },
          child: const Text('Confirm'),
        )
      ],
    );
  }
}

class SkeletonBlock extends StatelessWidget {
  const SkeletonBlock({super.key, this.height = 52});
  final double height;
  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: ToreTokens.s8),
      height: height,
      decoration: BoxDecoration(color: ToreTokens.surfaceAlt, borderRadius: BorderRadius.circular(8)),
    );
  }
}

class ErrorStateView extends StatelessWidget {
  const ErrorStateView({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(message), const SizedBox(height: 8), FilledButton(onPressed: onRetry, child: const Text('Retry'))]));
}

class EmptyStateView extends StatelessWidget {
  const EmptyStateView({super.key, required this.message});
  final String message;
  @override
  Widget build(BuildContext context) => Center(child: Text(message));
}
