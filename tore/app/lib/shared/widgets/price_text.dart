import 'dart:ui';
import 'package:flutter/material.dart';
import '../../theme/tore_colors.dart';

class PriceText extends StatelessWidget {
  final String text;
  final Color? color;

  const PriceText(this.text, {super.key, this.color});

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.titleMedium?.copyWith(
          fontFamily: 'monospace',
          fontFeatures: const [FontFeature.tabularFigures()],
          letterSpacing: 0.2,
          color: color ?? ToreColors.text,
          fontWeight: FontWeight.w600,
        );

    return Text(text, style: style);
  }
}