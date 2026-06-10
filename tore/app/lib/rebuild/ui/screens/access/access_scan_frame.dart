import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';

class AccessScanFrame extends StatelessWidget {
  const AccessScanFrame({
    super.key,
    this.onTap,
    this.height = 260,
    this.live = false,
    this.child,
  });

  final VoidCallback? onTap;
  final double height;
  final bool live;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF17070B), Color(0xFF09090D)],
          ),
          border: Border.all(color: ToreTokens.yellowCta, width: 1.4),
          boxShadow: [
            BoxShadow(
              color: ToreTokens.yellowCta.withValues(alpha: 0.16),
              blurRadius: 32,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Stack(
          fit: StackFit.expand,
          children: [
            if (child != null) child!,
            Center(
              child: Container(
                width: 214,
                height: 214,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(
                    color: live ? ToreTokens.yellowCta : ToreTokens.ruby,
                    width: 2.5,
                  ),
                ),
              ),
            ),
            const Positioned(
              top: 18,
              left: 18,
              child: Text(
                'ACCÈS',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.1,
                ),
              ),
            ),
            Positioned(
              right: 18,
              bottom: 18,
              child: Text(
                'TORÈ',
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.22),
                  fontSize: 28,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 3,
                ),
              ),
            ),
            Positioned(
              left: 18,
              bottom: 18,
              child: Row(
                children: [
                  Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: live ? ToreTokens.ok : ToreTokens.yellowCta,
                    ),
                  ),
                  const SizedBox(width: ToreTokens.s8),
                  Text(
                    live ? 'scan caméra actif' : 'zone premium prête',
                    style: const TextStyle(
                      color: Colors.white70,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
