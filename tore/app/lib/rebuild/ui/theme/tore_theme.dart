import 'package:flutter/material.dart';

import '../../config/app_environment.dart';

class ToreTokens {
  static const black = Color(0xFF050506);
  static const surface = Color(0xFF111118);
  static const surfaceAlt = Color(0xFF181820);
  static const ruby = Color(0xFFBA1733);
  static const yellowCta = Color(0xFFF4C430);
  static const ok = Color(0xFF50D890);
  static const warning = Color(0xFFFFA629);

  static const s4 = 4.0;
  static const s8 = 8.0;
  static const s12 = 12.0;
  static const s16 = 16.0;
  static const s24 = 24.0;

  // Spacing rhythm guardrail: use the canonical spacing scale {s8, s12, s16, s24}.
  // Keep non-rhythm spacing out of screen/layout code to avoid token drift.
  static const EdgeInsets pagePadding = EdgeInsets.all(s16);
  static const EdgeInsets sectionPadding = EdgeInsets.symmetric(vertical: s12);
}

class ToreTypography {
  static const TextStyle title = TextStyle(fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: 0.1);
  static const TextStyle section = TextStyle(fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.2);
  static const TextStyle body = TextStyle(fontSize: 14, height: 1.3);
  static const TextStyle mono = TextStyle(fontFamily: 'monospace', letterSpacing: 0.35);

  static TextStyle monoNumber(BuildContext context, {double? size, FontWeight weight = FontWeight.w700}) {
    return Theme.of(context).textTheme.bodyMedium!.merge(
          mono.copyWith(fontSize: size, fontWeight: weight),
        );
  }
}

class TorePreferences {
  static final ValueNotifier<bool> highContrast = ValueNotifier<bool>(false);
}

class ToreTheme {
  static ThemeData build() {
    return ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: ToreTokens.black,
      colorScheme: const ColorScheme.dark(
        primary: ToreTokens.ruby,
        secondary: ToreTokens.yellowCta,
        surface: ToreTokens.surface,
      ),
      cardTheme: const CardThemeData(
        color: ToreTokens.surface,
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: ToreTokens.surfaceAlt,
        border: OutlineInputBorder(),
      ),
      textTheme: const TextTheme(
        headlineMedium: ToreTypography.title,
        titleMedium: ToreTypography.section,
        bodyMedium: ToreTypography.body,
        bodySmall: ToreTypography.mono,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(44),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(44),
        ),
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: ToreTokens.yellowCta,
        foregroundColor: Colors.black,
      ),
    );
  }

  static Color envBadgeColor(AppEnvironment environment) {
    switch (environment) {
      case AppEnvironment.dev:
        return Colors.blueGrey;
      case AppEnvironment.stage:
        return ToreTokens.warning;
      case AppEnvironment.prod:
        return ToreTokens.ok;
    }
  }
}
