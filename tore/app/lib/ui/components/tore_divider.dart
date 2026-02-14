import 'package:flutter/material.dart';
import 'package:tore/theme/theme.dart';

class ToreDivider extends StatelessWidget {
  final bool gold;
  const ToreDivider({super.key, this.gold = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: ToreStroke.hairline,
      color: gold ? ToreColors.goldDim : ToreSemantic.divider,
    );
  }
}
