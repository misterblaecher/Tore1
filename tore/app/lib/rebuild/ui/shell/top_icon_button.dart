import 'package:flutter/material.dart';

import '../theme/tore_theme.dart';

class TopIconButton extends StatelessWidget {
  const TopIconButton({
    super.key,
    required this.icon,
    required this.tooltip,
    this.onPressed,
    this.badgeCount,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final int? badgeCount;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: IconButton.filledTonal(
        onPressed: onPressed,
        style: IconButton.styleFrom(
          backgroundColor: ToreTokens.surface,
          foregroundColor: Colors.white,
        ),
        icon: Stack(
          clipBehavior: Clip.none,
          children: [
            Icon(icon),
            if ((badgeCount ?? 0) > 0)
              Positioned(
                top: -6,
                right: -8,
                child: Container(
                  constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                    color: ToreTokens.ruby,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: ToreTokens.black),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '${badgeCount!}',
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
