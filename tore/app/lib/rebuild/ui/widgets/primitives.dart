import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../models/event_context.dart';
import '../../models/qr_resolve.dart';
import '../../models/rebuild_types.dart';
import '../../models/snapshot.dart';
import '../../services/network_state_resolver.dart';
import '../theme/tore_theme.dart';

class ToreMotion {
  static Duration micro(BuildContext context) => _reduce(context) ? const Duration(milliseconds: 1) : const Duration(milliseconds: 150);
  static Duration transition(BuildContext context) => _reduce(context) ? const Duration(milliseconds: 1) : const Duration(milliseconds: 220);

  static bool _reduce(BuildContext context) => MediaQuery.maybeOf(context)?.disableAnimations ?? false;
}

class ToreFeedback {
  static void success(BuildContext context, String text) {
    HapticFeedback.lightImpact();
    _show(context, text, duration: const Duration(milliseconds: 1800));
  }

  static void warning(BuildContext context, String text) {
    HapticFeedback.mediumImpact();
    _show(context, text, duration: const Duration(milliseconds: 2200));
  }

  static void error(BuildContext context, String text) {
    HapticFeedback.heavyImpact();
    _show(context, text, duration: const Duration(milliseconds: 3400));
  }

  static void _show(BuildContext context, String text, {required Duration duration}) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text), duration: duration));
  }
}

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
          Text('synced: ${eventContext?.syncedAt.toIso8601String() ?? 'never'}', style: ToreTypography.mono),
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
    return ValueListenableBuilder<bool>(
      valueListenable: TorePreferences.highContrast,
      builder: (context, highContrast, _) {
        return Container(
          constraints: const BoxConstraints(minHeight: 28),
          padding: const EdgeInsets.symmetric(horizontal: ToreTokens.s8, vertical: ToreTokens.s4),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(999),
            border: highContrast ? Border.all(color: Colors.white70, width: 1.4) : null,
          ),
          child: Text(label, style: const TextStyle(fontSize: 11)),
        );
      },
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
    return AnimatedScale(
      scale: 1,
      duration: ToreMotion.micro(context),
      child: Card(
        child: ListTile(
          title: Text(def.title),
          subtitle: Text('${def.id} • ${state.name.toUpperCase()}'),
          trailing: ToreBadge(label: def.scope.name.toUpperCase()),
          onTap: onOpen,
        ),
      ),
    );
  }
}

class ScreenScaffold extends StatelessWidget {
  const ScreenScaffold({
    super.key,
    required this.title,
    required this.body,
    this.connectivity,
    this.scopeBadges = const <String>[],
    this.footer,
  });

  final String title;
  final Widget body;
  final ConnectivityState? connectivity;
  final List<String> scopeBadges;
  final Widget? footer;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      if (connectivity != null) NetworkBanner(state: connectivity!),
      if (scopeBadges.isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(bottom: ToreTokens.s12),
          child: Wrap(
            spacing: ToreTokens.s8,
            runSpacing: ToreTokens.s8,
            children: [for (final badge in scopeBadges) ToreBadge(label: badge)],
          ),
        ),
      AnimatedSwitcher(duration: ToreMotion.transition(context), child: body),
      if (footer != null) ...[
        const SizedBox(height: ToreTokens.s16),
        footer!,
      ],
    ];

    return ValueListenableBuilder<bool>(
      valueListenable: TorePreferences.highContrast,
      builder: (context, highContrast, _) {
        final textColor = highContrast ? Colors.white : null;
        return Scaffold(
          appBar: AppBar(title: Text(title)),
          body: SafeArea(
            child: DefaultTextStyle.merge(
              style: TextStyle(color: textColor),
              child: ListView(
                padding: ToreTokens.pagePadding,
                children: children,
              ),
            ),
          ),
        );
      },
    );
  }
}

class NetworkBanner extends StatelessWidget {
  const NetworkBanner({super.key, required this.state});
  final ConnectivityState state;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: TorePreferences.highContrast,
      builder: (context, highContrast, _) {
        if (state == ConnectivityState.online) return const SizedBox.shrink();
        final offline = state == ConnectivityState.offline;
        return Semantics(
          label: offline ? 'État réseau hors ligne' : 'État réseau dégradé',
          child: Card(
            color: offline ? Colors.red.withOpacity(highContrast ? 0.28 : 0.18) : Colors.orange.withOpacity(highContrast ? 0.28 : 0.18),
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Row(
                children: [
                  Icon(offline ? Icons.cloud_off : Icons.network_check),
                  const SizedBox(width: ToreTokens.s8),
                  Expanded(
                    child: Text(
                      offline
                          ? resolveUiCopy('offline_write_blocked').message
                          : 'Connexion dégradée. Cache prioritaire actif et rafraîchissement ralenti.',
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class LoadingSkeleton extends StatelessWidget {
  const LoadingSkeleton({super.key, this.lines = 5, this.blockHeight = 52});
  final int lines;
  final double blockHeight;

  @override
  Widget build(BuildContext context) {
    return Column(children: [for (var i = 0; i < lines; i++) SkeletonBlock(height: blockHeight)]);
  }
}

class BlockedStateView extends StatelessWidget {
  const BlockedStateView({super.key, required this.title, required this.message, this.ctaLabel, this.onTap});
  final String title;
  final String message;
  final String? ctaLabel;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s16),
        child: AnimatedOpacity(
          opacity: 1,
          duration: ToreMotion.micro(context),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.block, size: 42),
              const SizedBox(height: ToreTokens.s8),
              Text(title, style: Theme.of(context).textTheme.titleMedium, textAlign: TextAlign.center),
              const SizedBox(height: ToreTokens.s8),
              Text(message, textAlign: TextAlign.center),
              if (ctaLabel != null && onTap != null) ...[
                const SizedBox(height: ToreTokens.s12),
                FilledButton(onPressed: onTap, child: Text(ctaLabel!)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class ConfirmDialogWithReason extends StatefulWidget {
  const ConfirmDialogWithReason({super.key, required this.title});
  final String title;

  static const reasonPresets = <String>[
    'network_retry',
    'customer_error',
    'fraud_suspected',
    'manual_override',
    'other',
  ];

  static Future<SensitiveReason?> show(BuildContext context, {required String title}) {
    return showDialog<SensitiveReason>(context: context, builder: (_) => ConfirmDialogWithReason(title: title));
  }

  @override
  State<ConfirmDialogWithReason> createState() => _ConfirmDialogWithReasonState();
}

class _ConfirmDialogWithReasonState extends State<ConfirmDialogWithReason> {
  String _selected = ConfirmDialogWithReason.reasonPresets.first;
  final _text = TextEditingController();

  bool get _requiresText => _selected == 'other' || _selected.isEmpty;
  bool get _canSubmit => !_requiresText || _text.text.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField<String>(
          value: _selected,
          decoration: const InputDecoration(labelText: 'Motif'),
          items: ConfirmDialogWithReason.reasonPresets.map((reason) => DropdownMenuItem(value: reason, child: Text(reason))).toList(),
          onChanged: (value) => setState(() => _selected = value ?? ''),
        ),
        const SizedBox(height: ToreTokens.s8),
        TextField(
          controller: _text,
          decoration: InputDecoration(
            labelText: _requiresText ? 'Détail (obligatoire)' : 'Détail (optionnel)',
          ),
          onChanged: (_) => setState(() {}),
        ),
      ]),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
        FilledButton(
          onPressed: _canSubmit
              ? () {
                  Navigator.pop(
                    context,
                    SensitiveReason(
                      code: _selected.trim().isEmpty ? 'other' : _selected,
                      text: _text.text.trim(),
                    ),
                  );
                }
              : null,
          child: const Text('Confirmer'),
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
  Widget build(BuildContext context) => Center(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: ToreTokens.s8),
          FilledButton(onPressed: onRetry, child: const Text('Réessayer')),
        ]),
      );
}

class EmptyStateView extends StatelessWidget {
  const EmptyStateView({super.key, required this.message, this.icon = Icons.inbox_outlined});
  final String message;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 36),
            const SizedBox(height: ToreTokens.s8),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      );
}

class WriteGuardButton extends StatelessWidget {
  const WriteGuardButton({super.key, required this.network, required this.onPressed, required this.label, this.semanticsLabel});
  final ConnectivityState network;
  final VoidCallback onPressed;
  final String label;
  final String? semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final resolver = NetworkStateResolver();
    final enabled = resolver.canWrite(network);
    return Semantics(
      button: true,
      label: semanticsLabel ?? label,
      child: FilledButton(
        onPressed: enabled
            ? onPressed
            : () => ToreFeedback.warning(context, resolveUiCopy('offline_write_blocked').message),
        child: Text(label),
      ),
    );
  }
}
