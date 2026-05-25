import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class ShowcaseFeatureScreen extends StatelessWidget {
  const ShowcaseFeatureScreen({
    super.key,
    required this.title,
    required this.badges,
    required this.heroMetric,
    required this.heroLabel,
    required this.items,
    this.network = ConnectivityState.online,
    this.actions = const <ShowcaseAction>[],
  });

  final String title;
  final List<String> badges;
  final String heroMetric;
  final String heroLabel;
  final List<ShowcaseItem> items;
  final ConnectivityState network;
  final List<ShowcaseAction> actions;

  @override
  Widget build(BuildContext context) {
    return ScreenScaffold(
      title: title,
      connectivity: network,
      scopeBadges: badges,
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Row(children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(heroLabel,
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s4),
                    Text(heroMetric,
                        style: ToreTypography.monoNumber(context, size: 34)),
                  ],
                ),
              ),
              ToreBadge(label: 'SHOWCASE', color: ToreTokens.yellowCta),
            ]),
          ),
        ),
        const SizedBox(height: ToreTokens.s8),
        for (final item in items) _ShowcaseTile(item: item),
        if (actions.isNotEmpty) ...[
          const SizedBox(height: ToreTokens.s12),
          Wrap(
            spacing: ToreTokens.s8,
            runSpacing: ToreTokens.s8,
            children: [
              for (final action in actions)
                FilledButton.icon(
                  onPressed: action.enabled ? () {} : null,
                  icon: Icon(action.icon),
                  label: Text(action.label),
                ),
            ],
          ),
        ],
      ]),
    );
  }
}

class ShowcaseItem {
  const ShowcaseItem({
    required this.title,
    required this.subtitle,
    required this.status,
    this.icon = Icons.check_circle_outline,
    this.color = ToreTokens.ruby,
  });

  final String title;
  final String subtitle;
  final String status;
  final IconData icon;
  final Color color;
}

class ShowcaseAction {
  const ShowcaseAction({
    required this.label,
    required this.icon,
    this.enabled = true,
  });

  final String label;
  final IconData icon;
  final bool enabled;
}

class _ShowcaseTile extends StatelessWidget {
  const _ShowcaseTile({required this.item});

  final ShowcaseItem item;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(item.icon, color: item.color),
        title: Text(item.title),
        subtitle: Text(item.subtitle),
        trailing: ToreBadge(label: item.status, color: item.color),
      ),
    );
  }
}
