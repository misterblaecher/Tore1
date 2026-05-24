import 'package:flutter/material.dart';

import '../../models/rebuild_types.dart';
import '../widgets/common_widgets.dart';

class ScreenView extends StatelessWidget {
  const ScreenView(
      {super.key,
      required this.definition,
      required this.state,
      required this.onWrite,
      required this.writeAllowed});

  final ModuleDefinition definition;
  final ModuleState state;
  final bool writeAllowed;
  final Future<void> Function()? onWrite;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(definition.title)),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Wrap(
            spacing: 8,
            children: [
              ToreBadge(label: definition.mode.name.toUpperCase()),
              ToreBadge(label: definition.scope.name.toUpperCase()),
              ToreBadge(label: state.name.toUpperCase()),
            ],
          ),
          const SizedBox(height: 12),
          for (final line in definition.details)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('• $line'),
            ),
          if (onWrite != null)
            FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFF4C430),
                  foregroundColor: Colors.black),
              onPressed: writeAllowed ? onWrite : null,
              child: Text(writeAllowed
                  ? (definition.writeAction ?? 'Write')
                  : 'Write blocked (offline/readonly)'),
            ),
        ],
      ),
    );
  }
}
