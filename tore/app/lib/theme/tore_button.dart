import 'package:flutter/material.dart';
import 'tore_colors.dart';

enum ToreButtonKind { rubine, jaune, ghost }

class ToreButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final ToreButtonKind kind;
  final double? width;
  final bool dense;

  const ToreButton({
    super.key,
    required this.label,
    required this.onPressed,
    required this.kind,
    this.width,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    final bg = switch (kind) {
      ToreButtonKind.rubine => ToreColors.rubine,
      ToreButtonKind.jaune => ToreColors.jaune,
      ToreButtonKind.ghost => ToreColors.surface2,
    };

    // Jaune -> texte noir, Rubine/Ghost -> texte clair
    final fg = (kind == ToreButtonKind.jaune) ? Colors.black : ToreColors.text;

    final h = dense ? 40.0 : 46.0;
    final br = BorderRadius.circular(14);

    final child = ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: bg,
        foregroundColor: fg,
        elevation: 0,
        padding: EdgeInsets.symmetric(horizontal: dense ? 14 : 16),
        shape: RoundedRectangleBorder(borderRadius: br),
      ),
      onPressed: onPressed,
      child: Text(label),
    );

    return SizedBox(
      height: h,
      width: width,
      child: child,
    );
  }
}
