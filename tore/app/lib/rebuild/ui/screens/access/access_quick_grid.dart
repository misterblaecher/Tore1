import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';

class AccessQuickAction {
  const AccessQuickAction({
    required this.label,
    required this.subtitle,
    required this.icon,
    required this.route,
  });

  final String label;
  final String subtitle;
  final IconData icon;
  final String route;
}

class AccessQuickGrid extends StatelessWidget {
  const AccessQuickGrid({
    super.key,
    required this.actions,
    required this.onOpenRoute,
  });

  final List<AccessQuickAction> actions;
  final ValueChanged<String> onOpenRoute;

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: actions.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: ToreTokens.s8,
        crossAxisSpacing: ToreTokens.s8,
        childAspectRatio: 1.5,
      ),
      itemBuilder: (context, index) {
        final action = actions[index];
        return InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => onOpenRoute(action.route),
          child: Ink(
            decoration: BoxDecoration(
              color: ToreTokens.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: ToreTokens.border),
            ),
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: ToreTokens.ruby.withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Icon(action.icon, color: ToreTokens.yellowCta),
                  ),
                  const Spacer(),
                  Text(
                    action.label,
                    style: Theme.of(context).textTheme.titleMedium,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: ToreTokens.s4),
                  Text(
                    action.subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white60, fontSize: 12),
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
