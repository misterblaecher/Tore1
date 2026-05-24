import 'package:flutter/material.dart';
import 'tore_colors.dart';

class ToreTheme {
  static ThemeData dark() {
    final base = ThemeData.dark(useMaterial3: true);

    return base.copyWith(
      scaffoldBackgroundColor: ToreColors.bg,
      colorScheme: const ColorScheme.dark(
        primary: ToreColors.rubine,
        secondary: ToreColors.jaune,
        surface: ToreColors.surface,
        onSurface: ToreColors.text,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: ToreColors.bg,
        foregroundColor: ToreColors.text,
        elevation: 0,
      ),

      // IMPORTANT: CardThemeData (sinon erreur de compile)
      cardTheme: const CardThemeData(
        color: ToreColors.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
          side: BorderSide(color: ToreColors.border),
        ),
      ),
      dividerTheme:
          DividerThemeData(color: ToreColors.border.withValues(alpha: 0.6)),
      listTileTheme: const ListTileThemeData(
        iconColor: ToreColors.subtext,
        textColor: ToreColors.text,
      ),
    );
  }
}
