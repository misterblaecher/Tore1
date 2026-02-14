import 'package:flutter/material.dart';
import 'package:tore/theme/theme.dart';

enum ToreCTAStyle { primary, secondary, destructive }

class ToreCTA extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final ToreCTAStyle style;
  final bool busy;

  const ToreCTA({
    super.key,
    required this.label,
    this.onPressed,
    this.style = ToreCTAStyle.primary,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !busy;

    Color bg;
    Color fg;
    BorderSide? border;

    switch (style) {
      case ToreCTAStyle.primary:
        bg = ToreSemantic.accentPrimary;
        fg = ToreSemantic.textPrimary;
        border = null;
        break;
      case ToreCTAStyle.secondary:
        bg = Colors.transparent;
        fg = ToreSemantic.textPrimary;
        border = BorderSide(color: ToreSemantic.divider, width: ToreStroke.hairline);
        break;
      case ToreCTAStyle.destructive:
        bg = ToreSemantic.danger;
        fg = ToreSemantic.textPrimary;
        border = null;
        break;
    }

    return SizedBox(
      height: 46,
      child: ElevatedButton(
        onPressed: enabled ? onPressed : null,
        style: ElevatedButton.styleFrom(
          backgroundColor: bg,
          foregroundColor: fg,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(ToreRadii.md),
            side: border ?? BorderSide.none,
          ),
          elevation: 0,
        ),
        child: busy
            ? const SizedBox(height: 18, width: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : Text(label, style: ToreType.body.copyWith(fontWeight: FontWeight.w600)),
      ),
    );
  }
}
