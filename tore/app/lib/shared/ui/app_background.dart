import 'package:flutter/material.dart';

class AppBackground extends StatelessWidget {
  final Widget child;

  const AppBackground({
    super.key,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // Background chart
        Positioned.fill(
          child: Opacity(
            opacity: 0.12,
            child: Image.asset(
              'assets/da/bg_chart.png',
              fit: BoxFit.cover,
            ),
          ),
        ),

        // Noise overlay
        Positioned.fill(
          child: Opacity(
            opacity: 0.08,
            child: Image.asset(
              'assets/da/noise.png',
              fit: BoxFit.cover,
            ),
          ),
        ),

        // Screen content
        Positioned.fill(child: child),
      ],
    );
  }
}
