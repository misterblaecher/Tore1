import 'package:flutter/material.dart';

import '../../config/app_environment.dart';

class ToreTokens {
  static const black = Color(0xFF050506);
  static const surface = Color(0xFF121217);
  static const surfaceAlt = Color(0xFF1B1A22);
  static const border = Color(0xFF2A2631);
  static const ruby = Color(0xFFBA1733);
  static const rubyDeep = Color(0xFF6E0D18);
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
  static const TextStyle title =
      TextStyle(fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: 0.1);
  static const TextStyle section =
      TextStyle(fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.2);
  static const TextStyle body = TextStyle(fontSize: 14, height: 1.3);
  static const TextStyle mono =
      TextStyle(fontFamily: 'monospace', letterSpacing: 0.35);

  static TextStyle monoNumber(BuildContext context,
      {double? size, FontWeight weight = FontWeight.w700}) {
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
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          side: BorderSide(color: ToreTokens.border),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: ToreTokens.black,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
            color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: ToreTokens.surface,
        indicatorColor: ToreTokens.yellowCta,
        labelTextStyle: WidgetStateProperty.resolveWith(
          (states) => TextStyle(
            color: states.contains(WidgetState.selected)
                ? Colors.white
                : Colors.white70,
            fontSize: 11,
            fontWeight: FontWeight.w700,
          ),
        ),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? ToreTokens.black
                : Colors.white,
            size: 22,
          ),
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: ToreTokens.surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          borderSide: BorderSide(color: ToreTokens.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          borderSide: BorderSide(color: ToreTokens.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(8)),
          borderSide: BorderSide(color: ToreTokens.yellowCta),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.1,
            color: Colors.white),
        headlineSmall: TextStyle(
            fontSize: 22, fontWeight: FontWeight.w700, color: Colors.white),
        titleLarge: TextStyle(
            fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white),
        titleMedium: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.2,
            color: Colors.white),
        bodyMedium: TextStyle(fontSize: 14, height: 1.3, color: Colors.white70),
        bodySmall: TextStyle(
            fontFamily: 'monospace',
            letterSpacing: 0.35,
            color: Colors.white70),
        labelLarge: TextStyle(fontWeight: FontWeight.w700, color: Colors.white),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(44),
          foregroundColor: Colors.white,
          backgroundColor: ToreTokens.ruby,
          disabledForegroundColor: Colors.white54,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(44),
          foregroundColor: Colors.white,
          side: const BorderSide(color: ToreTokens.border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
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
