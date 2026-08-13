import 'package:flutter/material.dart';
import 'tokens.dart' as tokens;

class ToreTheme {
  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);

    return base.copyWith(
      scaffoldBackgroundColor: tokens.ToreSemantic.bg,
      colorScheme: const ColorScheme.dark(
        primary: tokens.ToreSemantic.accentPrimary,
        secondary: tokens.ToreSemantic.accentAuthority,
        surface: tokens.ToreSemantic.surfaceBase,
        onSurface: tokens.ToreSemantic.textPrimary,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: tokens.ToreSemantic.bg,
        foregroundColor: tokens.ToreSemantic.textPrimary,
        elevation: 0,
      ),

      // IMPORTANT: CardThemeData (sinon erreur de compile)
      cardTheme: const CardThemeData(
        color: tokens.ToreSemantic.surfaceCard,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(tokens.ToreRadii.md)),
          side: BorderSide(color: tokens.ToreSemantic.divider),
        ),
      ),
      dividerTheme: DividerThemeData(color: tokens.ToreSemantic.divider),
      listTileTheme: const ListTileThemeData(
        iconColor: tokens.ToreSemantic.textSecondary,
        textColor: tokens.ToreSemantic.textPrimary,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: tokens.ToreSemantic.accentAuthority,
          foregroundColor: tokens.ToreColors.goldInk,
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(tokens.ToreRadii.sm),
          ),
        ),
      ),
    );
  }
}
