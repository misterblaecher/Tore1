import 'package:flutter/material.dart';

/// Simple lightweight sparkline (no external chart library).
///
/// Draws a polyline normalized to the widget bounds.
class Sparkline extends StatelessWidget {
  final List<double> values;
  final double strokeWidth;
  final Color? color;
  final EdgeInsets padding;

  const Sparkline({
    super.key,
    required this.values,
    this.strokeWidth = 2,
    this.color,
    this.padding = const EdgeInsets.all(2),
  });

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) {
      return const SizedBox(width: 64, height: 24);
    }
    return Padding(
      padding: padding,
      child: CustomPaint(
        painter: _SparklinePainter(
          values: values,
          strokeWidth: strokeWidth,
          color: color ?? Theme.of(context).colorScheme.primary,
        ),
        size: const Size(64, 24),
      ),
    );
  }
}

class _SparklinePainter extends CustomPainter {
  final List<double> values;
  final double strokeWidth;
  final Color color;

  _SparklinePainter({
    required this.values,
    required this.strokeWidth,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final minV = values.reduce((a, b) => a < b ? a : b);
    final maxV = values.reduce((a, b) => a > b ? a : b);
    final range = (maxV - minV).abs() < 1e-9 ? 1.0 : (maxV - minV);

    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    final path = Path();
    for (int i = 0; i < values.length; i++) {
      final x = (i / (values.length - 1)) * size.width;
      final yNorm = (values[i] - minV) / range;
      final y = size.height - (yNorm * size.height);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) {
    return oldDelegate.values != values ||
        oldDelegate.strokeWidth != strokeWidth ||
        oldDelegate.color != color;
  }
}
