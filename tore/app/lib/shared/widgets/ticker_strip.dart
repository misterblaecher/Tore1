import 'package:flutter/material.dart';
import '../../theme/tore_colors.dart';

class TickerItem {
  final String label;
  final String value;
  final Color color;
  const TickerItem(this.label, this.value, this.color);
}

class TickerStrip extends StatelessWidget {
  final List<TickerItem> items;
  const TickerStrip({super.key, required this.items});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: items.length,
        separatorBuilder: (_, __) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final it = items[i];
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: it.color.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: it.color.withValues(alpha: 0.35)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  it.label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: ToreColors.text,
                        fontFamily: 'monospace',
                      ),
                ),
                const SizedBox(width: 10),
                Text(
                  it.value,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: ToreColors.text,
                        fontFamily: 'monospace',
                      ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
