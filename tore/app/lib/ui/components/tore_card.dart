import 'package:flutter/material.dart';
import 'package:tore/theme/theme.dart';

class ToreCard extends StatelessWidget {
  final Widget? header;
  final Widget child;
  final bool focused;
  final ToreThemeMode themeMode;
  final EdgeInsets padding;

  const ToreCard({
    super.key,
    this.header,
    required this.child,
    this.focused = false,
    this.themeMode = ToreThemeMode.ritual,
    this.padding = const EdgeInsets.all(ToreSpace.s4),
  });

  @override
  Widget build(BuildContext context) {
    final theme = ToreTheme(themeMode);
    final borderColor =
        focused ? ToreSemantic.accentPrimary : theme.cardBorderColor;

    return Container(
      decoration: BoxDecoration(
        color: ToreSemantic.surfaceCard,
        borderRadius: BorderRadius.circular(ToreRadii.md),
        border: Border.all(color: borderColor, width: ToreStroke.hairline),
        boxShadow: [
          // shadow.card léger, pas énorme
          const BoxShadow(
            blurRadius: 10,
            spreadRadius: 0,
            offset: Offset(0, 4),
            color: Color(0x22000000),
          ),
          if (focused && theme.allowGlow)
            BoxShadow(
              blurRadius: 18,
              spreadRadius: 0,
              offset: const Offset(0, 0),
              color: ToreColors.rubyGlow.withValues(alpha: 0.18),
            ),
        ],
      ),
      child: Padding(
        padding: padding,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (header != null) ...[
              header!,
              const SizedBox(height: ToreSpace.s3),
            ],
            child,
          ],
        ),
      ),
    );
  }
}
