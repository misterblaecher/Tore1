import 'package:flutter/material.dart';

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
}

class ToreTheme {
  static ThemeData build() {
    const mono = TextStyle(fontFamily: 'monospace');
    return ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: ToreTokens.black,
      colorScheme: const ColorScheme.dark(
        primary: ToreTokens.ruby,
        secondary: ToreTokens.yellowCta,
        surface: ToreTokens.surface,
      ),
      cardTheme: const CardThemeData(color: ToreTokens.surface),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: ToreTokens.surfaceAlt,
        border: OutlineInputBorder(),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(fontWeight: FontWeight.w700),
        titleMedium: TextStyle(fontWeight: FontWeight.w600),
        bodySmall: mono,
      ),
      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: ToreTokens.yellowCta,
        foregroundColor: Colors.black,
      ),
    );
  }
}
