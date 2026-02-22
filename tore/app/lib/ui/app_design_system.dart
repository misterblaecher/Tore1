import 'package:flutter/material.dart';

class AppColors {
  static const accent = Color(0xFFE83D84);
  static const accentSoft = Color(0x33E83D84);
  static const surface = Color(0xFF161622);
  static const cardBorder = Color(0xFF2A2B3A);
  static const success = Color(0xFF5ED8A6);
  static const warning = Color(0xFFF1B34A);
}

class AppSpacing {
  static const xs = 8.0;
  static const sm = 12.0;
  static const md = 16.0;
  static const lg = 24.0;
}

class AppTextStyles {
  static const sectionTitle = TextStyle(fontSize: 18, fontWeight: FontWeight.w700);
  static const muted = TextStyle(fontSize: 13, color: Colors.white70);
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({super.key, required this.label, required this.onPressed, this.icon, this.loading = false});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: loading ? null : onPressed,
      icon: loading
          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          : Icon(icon ?? Icons.arrow_forward),
      label: Text(label),
      style: FilledButton.styleFrom(backgroundColor: AppColors.accent),
    );
  }
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton({super.key, required this.label, required this.onPressed, this.icon});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon ?? Icons.chevron_right),
      label: Text(label),
    );
  }
}

class AppCard extends StatelessWidget {
  const AppCard({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.cardBorder),
      ),
      color: AppColors.surface,
      child: Padding(padding: const EdgeInsets.all(AppSpacing.md), child: child),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
        child: Text(text, style: AppTextStyles.sectionTitle),
      );
}

class AppChip extends StatelessWidget {
  const AppChip({super.key, required this.label, this.color});

  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(label),
      backgroundColor: color ?? AppColors.accentSoft,
      side: BorderSide.none,
    );
  }
}
