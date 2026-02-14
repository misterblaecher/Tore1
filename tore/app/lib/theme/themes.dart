import 'package:flutter/material.dart';
import 'tokens.dart';

enum ToreThemeMode { ritual, ops, admin }

class ToreTheme {
  final ToreThemeMode mode;
  const ToreTheme(this.mode);

  bool get allowGlow => mode != ToreThemeMode.admin;
  bool get allowGrain => mode == ToreThemeMode.ritual;
  bool get allowEmbers => mode == ToreThemeMode.ritual;

  Color get cardBorderColor {
    switch (mode) {
      case ToreThemeMode.admin:
        return ToreSemantic.divider;
      case ToreThemeMode.ops:
      case ToreThemeMode.ritual:
        return ToreSemantic.accentBorder;
    }
  }

  Color get primaryCTA => ToreSemantic.accentPrimary;
  Color get authority => ToreSemantic.accentAuthority;
}

/// Provide via Riverpod / InheritedWidget selon ton archi.
/// Ici juste un ThemeData prêt à brancher.
ThemeData buildToreThemeData(ToreThemeMode mode) {
  final base = ThemeData.dark(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: ToreSemantic.bg,
    colorScheme: base.colorScheme.copyWith(
      primary: ToreSemantic.accentPrimary,
      secondary: ToreSemantic.accentAuthority,
      surface: ToreSemantic.surfaceBase,
      error: ToreSemantic.danger,
    ),
    dividerColor: ToreSemantic.divider,
    textTheme: base.textTheme.apply(
      bodyColor: ToreSemantic.textPrimary,
      displayColor: ToreSemantic.textPrimary,
    ),
  );
}
