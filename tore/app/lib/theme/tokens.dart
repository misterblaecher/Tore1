import 'package:flutter/material.dart';

/// TORÈ V1 — primitives + semantics
/// Source de vérité: Design tokens TORÈ V1 (Night/Ruby/Gold/States)
class ToreColors {
  // Neutres “Night”
  static const ink0 = Color(0xFF070607);
  static const ink1 = Color(0xFF0E0C0F);
  static const ink2 = Color(0xFF151218);
  static const ink3 = Color(0xFF1E1A22);

  static const lineWeak = Color(0xFF2A2430);

  static const text0 = Color(0xFFF6F1F6);
  static const text1 = Color(0xFFCFC6D2);
  static const text2 = Color(0xFF9A8FA0);

  // Ruby
  static const rubyCore = Color(0xFFCA005D);
  static const rubyHot = Color(0xFFFF2A4D);
  static const rubyDeep = Color(0xFF7A0037);
  static const rubyGlow = Color(0xFFFF3B6A);

  // Gold
  static const goldCore = Color(0xFFF5C400);
  static const goldDim = Color(0xFFC8A100);
  static const goldInk = Color(0xFF2B2206);

  // States (terrain)
  static const ok = Color(0xFF2ECC71);
  static const warn = Color(0xFFFFB020);
  static const bad = Color(0xFFFF3B30);
  static const info = Color(0xFF59A8FF);
}

/// Semantic tokens — “ce que les devs utilisent vraiment”
class ToreSemantic {
  // Surfaces
  static const bg = ToreColors.ink0;
  static const surfaceBase = ToreColors.ink1;
  static const surfaceCard = ToreColors.ink2;
  static const surfacePanel = ToreColors.ink3;
  static const divider = ToreColors.lineWeak;

  // Texte
  static const textPrimary = ToreColors.text0;
  static const textSecondary = ToreColors.text1;
  static const textMuted = ToreColors.text2;

  // Actions
  static const accentPrimary = ToreColors.rubyHot;
  static const accentAmbient = ToreColors.rubyCore;
  static const accentBorder = ToreColors.rubyDeep;
  static const accentAuthority = ToreColors.goldCore;

  // Feedback
  static const success = ToreColors.ok;
  static const warning = ToreColors.warn;
  static const danger = ToreColors.bad;
  static const info = ToreColors.info;
}

class ToreRadii {
  static const sm = 10.0;
  static const md = 14.0;
  static const lg = 18.0;
}

class ToreStroke {
  static const hairline = 1.0;
  static const strong = 2.0;
}

class ToreSpace {
  static const s1 = 4.0;
  static const s2 = 8.0;
  static const s3 = 12.0;
  static const s4 = 16.0;
  static const s5 = 20.0;
  static const s6 = 24.0;
}

/// Typo scale
class ToreType {
  static const uiFont = 'Inter';
  static const monoFont = 'SpaceMono';

  static const h1 = TextStyle(
      fontFamily: uiFont,
      fontSize: 28,
      height: 32 / 28,
      fontWeight: FontWeight.w700);
  static const h2 = TextStyle(
      fontFamily: uiFont,
      fontSize: 22,
      height: 28 / 22,
      fontWeight: FontWeight.w700);
  static const h3 = TextStyle(
      fontFamily: uiFont,
      fontSize: 18,
      height: 24 / 18,
      fontWeight: FontWeight.w600);

  static const body = TextStyle(
      fontFamily: uiFont,
      fontSize: 15,
      height: 22 / 15,
      fontWeight: FontWeight.w500);
  static const meta = TextStyle(
      fontFamily: uiFont,
      fontSize: 13,
      height: 18 / 13,
      fontWeight: FontWeight.w500);

  static const monoMetric = TextStyle(
      fontFamily: monoFont,
      fontSize: 16,
      height: 20 / 16,
      fontWeight: FontWeight.w600);
  // mono.big: pour compteurs (40–64) -> à utiliser au cas par cas
}
