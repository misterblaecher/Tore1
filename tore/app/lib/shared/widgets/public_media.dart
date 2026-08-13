import 'package:flutter/material.dart';

import '../../ui/app_design_system.dart';

class PublicMedia extends StatelessWidget {
  const PublicMedia({
    super.key,
    required this.imageUrl,
    this.height = 180,
    this.icon = Icons.nightlife_outlined,
    this.borderRadius = const BorderRadius.all(Radius.circular(20)),
    this.fallbackColors,
  });

  final String? imageUrl;
  final double height;
  final IconData icon;
  final BorderRadius borderRadius;
  final List<Color>? fallbackColors;

  @override
  Widget build(BuildContext context) {
    final fallback = Container(
      height: height,
      decoration: BoxDecoration(
        borderRadius: borderRadius,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: fallbackColors ??
              const [Color(0xFF6E0D18), Color(0xFF171018), Color(0xFF050506)],
        ),
      ),
      alignment: Alignment.center,
      child: Icon(icon, size: height * .34, color: AppColors.accentGold),
    );
    if (imageUrl == null) return fallback;
    return ClipRRect(
      borderRadius: borderRadius,
      child: Image.network(
        imageUrl!,
        height: height,
        width: double.infinity,
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) => fallback,
      ),
    );
  }
}
