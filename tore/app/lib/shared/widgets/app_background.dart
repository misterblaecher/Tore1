import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../theme/tore_colors.dart';

/// Fond "trading" : dégradé sombre + texture légère (candles + noise).
class AppBackground extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;

  const AppBackground({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(12),
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        const Positioned.fill(child: _BackgroundPaint()),
        SafeArea(
          child: Padding(
            padding: padding,
            child: child,
          ),
        ),
      ],
    );
  }
}

class _BackgroundPaint extends StatelessWidget {
  const _BackgroundPaint();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0.8, -0.6),
          radius: 1.2,
          colors: [
            Color(0xFF141A24),
            ToreColors.bg,
          ],
        ),
      ),
      child: RepaintBoundary(
        child: CustomPaint(
          painter: _ChartTexturePainter(),
          child: const SizedBox.expand(),
        ),
      ),
    );
  }
}

class _ChartTexturePainter extends CustomPainter {
  const _ChartTexturePainter();

  @override
  void paint(Canvas canvas, Size size) {
    // Candles very subtle
    final rnd = math.Random(7);
    final candlePaintUp = Paint()..color = ToreColors.up.withOpacity(0.10);
    final candlePaintDown = Paint()..color = ToreColors.rubine.withOpacity(0.10);
    final wickPaint = Paint()
      ..color = Colors.white.withOpacity(0.05)
      ..strokeWidth = 1;

    final count = (size.width / 14).clamp(18, 80).toInt();
    final baseY = size.height * 0.28;
    final amp = size.height * 0.22;

    for (int i = 0; i < count; i++) {
      final x = (i + 2) * (size.width / (count + 6));
      final h = (0.20 + rnd.nextDouble() * 0.8) * amp;
      final top = baseY + (rnd.nextDouble() - 0.5) * amp * 0.45;
      final rect = Rect.fromLTWH(x, top, 6, h);
      final up = rnd.nextBool();
      canvas.drawRect(rect, up ? candlePaintUp : candlePaintDown);

      // wick
      final wickTop = top - 8 - rnd.nextDouble() * 18;
      final wickBot = top + h + 8 + rnd.nextDouble() * 18;
      canvas.drawLine(Offset(x + 3, wickTop), Offset(x + 3, wickBot), wickPaint);
    }

    // Noise overlay (tiny dots)
    final dotPaint = Paint()..color = Colors.white.withOpacity(0.03);
    final dots = (size.width * size.height / 2200).clamp(400, 1800).toInt();
    for (int i = 0; i < dots; i++) {
      final x = rnd.nextDouble() * size.width;
      final y = rnd.nextDouble() * size.height;
      canvas.drawRect(Rect.fromLTWH(x, y, 1, 1), dotPaint);
    }

    // subtle vignette
    final vignette = Paint()
      ..shader = RadialGradient(
        center: Alignment.center,
        radius: 1.1,
        colors: [
          Colors.transparent,
          Colors.black.withOpacity(0.35),
        ],
        stops: const [0.6, 1.0],
      ).createShader(Offset.zero & size);

    canvas.drawRect(Offset.zero & size, vignette);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}