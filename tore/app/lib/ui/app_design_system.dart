import 'package:flutter/material.dart';

class AppColors {
  static const accent = Color(0xFFF4B400);
  static const accentSoft = Color(0x33F4B400);
  static const surface = Color(0xFF14141C);
  static const cardBorder = Color(0x40F4B400);
  static const success = Color(0xFF5ED8A6);
  static const warning = Color(0xFFF1B34A);

  // Solar Brutalism
  static const backgroundPrimary = Color(0xFF08080C);
  static const accentGold = Color(0xFFF4B400);
  static const accentRed = Color(0xFFD72638);
  static const accentAmber = Color(0xFFFF6A00);
  static const solarBackground = backgroundPrimary;
  static const solarGold = accentGold;
  static const solarRed = accentRed;
  static const solarRedSoft = Color(0x33E0442F);
  static BoxDecoration get solarCardDecoration => BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accentGold.withValues(alpha: 0.22), width: 1),
        boxShadow: [
          BoxShadow(
              color: accentGold.withValues(alpha: 0.12),
              blurRadius: 20,
              spreadRadius: 0.3),
        ],
      );

  static BoxDecoration get solarHaloBackground => const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -0.8),
          radius: 1.2,
          colors: [
            Color(0x2AF4B400),
            Color(0x14FF6A00),
            backgroundPrimary,
            backgroundPrimary,
          ],
        ),
      );
}

class AppSpacing {
  static const xs = 8.0;
  static const sm = 12.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}

class AppRadii {
  static const sm = 10.0;
  static const md = 16.0;
  static const lg = 22.0;
}

class AppTextStyles {
  static const sectionTitle =
      TextStyle(fontSize: 18, fontWeight: FontWeight.w700);
  static const massiveTitle =
      TextStyle(fontSize: 28, fontWeight: FontWeight.w900, letterSpacing: 0.4);
  static const muted = TextStyle(fontSize: 13, color: Colors.white70);
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton(
      {super.key,
      required this.label,
      required this.onPressed,
      this.icon,
      this.loading = false});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: loading ? null : onPressed,
      icon: loading
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2))
          : Icon(icon ?? Icons.arrow_forward),
      label: Text(label),
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.accentGold,
        foregroundColor: Colors.black,
        minimumSize: const Size.fromHeight(52),
      ),
    );
  }
}

class ToreButton extends StatelessWidget {
  const ToreButton.primary({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.loading = false,
  }) : secondary = false;

  const ToreButton.secondary({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
  })  : secondary = true,
        loading = false;

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;
  final bool secondary;

  @override
  Widget build(BuildContext context) {
    if (secondary) {
      return OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon ?? Icons.chevron_right),
        style: OutlinedButton.styleFrom(
          side: const BorderSide(color: AppColors.accentRed),
          foregroundColor: AppColors.accentRed,
          minimumSize: const Size.fromHeight(52),
        ),
        label: Text(label),
      );
    }
    return PrimaryButton(
        label: label, onPressed: onPressed, icon: icon, loading: loading);
  }
}

class SolarPrimaryButton extends StatelessWidget {
  const SolarPrimaryButton(
      {super.key,
      required this.label,
      required this.onPressed,
      this.icon,
      this.loading = false});

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return PrimaryButton(
        label: label, onPressed: onPressed, icon: icon, loading: loading);
  }
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton(
      {super.key, required this.label, required this.onPressed, this.icon});

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
      child:
          Padding(padding: const EdgeInsets.all(AppSpacing.md), child: child),
    );
  }
}

class ToreCard extends StatelessWidget {
  const ToreCard(
      {super.key,
      required this.child,
      this.padding = const EdgeInsets.all(AppSpacing.md)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) =>
      SolarCard(padding: padding, child: child);
}

class SolarCard extends StatelessWidget {
  const SolarCard(
      {super.key,
      required this.child,
      this.padding = const EdgeInsets.all(AppSpacing.md)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppColors.solarCardDecoration,
      child: Padding(padding: padding, child: child),
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

class ToreSectionHeader extends StatelessWidget {
  const ToreSectionHeader(this.text, {super.key, this.trailing});

  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) =>
      SolarSectionTitle(text, trailing: trailing);
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

class SolarChip extends StatelessWidget {
  const SolarChip({super.key, required this.label, this.color});

  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) => AppChip(label: label, color: color);
}

class SolarSectionTitle extends StatelessWidget {
  const SolarSectionTitle(this.text, {super.key, this.trailing});

  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        children: [
          Expanded(
              child: Text(text,
                  style: AppTextStyles.sectionTitle
                      .copyWith(fontSize: 20, fontWeight: FontWeight.w800))),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}

class SolarBackground extends StatelessWidget {
  const SolarBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: AppColors.solarHaloBackground,
      child: child,
    );
  }
}

class HaloBackground extends StatelessWidget {
  const HaloBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => SolarBackground(child: child);
}

class AuthRequiredNotice extends StatelessWidget {
  const AuthRequiredNotice({super.key, required this.message, this.onLogin});

  final String message;
  final VoidCallback? onLogin;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: AppColors.solarCardDecoration,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text("Connecte-toi pour continuer",
              style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 6),
          Text(message, style: AppTextStyles.muted),
          if (onLogin != null) ...[
            const SizedBox(height: 10),
            PrimaryButton(
                label: "Créer un compte / Se connecter",
                onPressed: onLogin,
                icon: Icons.lock_open),
          ],
        ],
      ),
    );
  }
}
