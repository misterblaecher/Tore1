import 'package:flutter/material.dart';
import '../../theme/tokens.dart';
import '../../theme/themes.dart';

enum ToreChipVariant { live, closed, authority, ok, warn, bad, info }

class ToreChip extends StatelessWidget {
  final String label;
  final ToreChipVariant variant;
  final ToreThemeMode themeMode;

  const ToreChip({
    super.key,
    required this.label,
    required this.variant,
    this.themeMode = ToreThemeMode.ritual,
  });

  @override
  Widget build(BuildContext context) {
    final theme = ToreTheme(themeMode);

    Color bg;
    Color fg;
    Color? glow;

    switch (variant) {
      case ToreChipVariant.live:
        bg = ToreSemantic.accentPrimary;
        fg = ToreSemantic.textPrimary;
        glow = theme.allowGlow ? ToreColors.rubyGlow.withOpacity(0.22) : null;
        break;
      case ToreChipVariant.closed:
        bg = ToreSemantic.surfacePanel;
        fg = ToreSemantic.textMuted;
        glow = null;
        break;
      case ToreChipVariant.authority:
        bg = ToreColors.goldCore;
        fg = ToreColors.goldInk;
        glow = null;
        break;
      case ToreChipVariant.ok:
        bg = ToreSemantic.success;
        fg = ToreSemantic.textPrimary;
        glow = null;
        break;
      case ToreChipVariant.warn:
        bg = ToreSemantic.warning;
        fg = ToreColors.ink0;
        glow = null;
        break;
      case ToreChipVariant.bad:
        bg = ToreSemantic.danger;
        fg = ToreSemantic.textPrimary;
        glow = null;
        break;
      case ToreChipVariant.info:
        bg = ToreSemantic.info;
        fg = ToreSemantic.textPrimary;
        glow = null;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
        boxShadow: glow != null
            ? [BoxShadow(color: glow!, blurRadius: 16, offset: const Offset(0, 0))]
            : const [],
      ),
      child: Text(
        label,
        style: ToreType.meta.copyWith(color: fg, fontWeight: FontWeight.w600),
      ),
    );
  }
}
