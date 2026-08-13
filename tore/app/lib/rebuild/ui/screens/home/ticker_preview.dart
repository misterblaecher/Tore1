import 'package:flutter/material.dart';

import '../../../models/backend_models.dart';
import '../../theme/tore_theme.dart';

class TickerPreview extends StatelessWidget {
  const TickerPreview({super.key, required this.items});

  final List<TickerItemDto> items;

  @override
  Widget build(BuildContext context) {
    final visible = items.take(4).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(ToreTokens.s12),
        child: Column(
          children: [
            for (var i = 0; i < visible.length; i++) ...[
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      color: ToreTokens.yellowCta,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: ToreTokens.s12),
                  Expanded(child: Text(visible[i].message)),
                  const Icon(Icons.chevron_right,
                      color: Colors.white38, size: 18),
                ],
              ),
              if (i != visible.length - 1)
                const Divider(color: ToreTokens.border, height: 22),
            ],
          ],
        ),
      ),
    );
  }
}
