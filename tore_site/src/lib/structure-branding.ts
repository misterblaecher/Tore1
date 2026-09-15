export const TORE_PRIMARY = "#BA1733";
export const TORE_SECONDARY = "#F4C430";
export const TORE_SURFACE = "#111014";
export const TORE_TEXT_LIGHT = "#FFFFFF";
export const TORE_TEXT_DARK = "#111014";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export function isHexColor(value?: string | null): value is string {
  return Boolean(value && HEX_RE.test(value.trim()));
}

export function normalizeHex(value: string | null | undefined, fallback: string): string {
  return isHexColor(value) ? value.trim().toUpperCase() : fallback;
}

function channel(value: number): number {
  const srgb = value / 255;
  return srgb <= 0.04045 ? srgb / 12.92 : Math.pow((srgb + 0.055) / 1.055, 2.4);
}

export function relativeLuminance(hex: string): number {
  const normalized = normalizeHex(hex, TORE_TEXT_DARK);
  const red = channel(Number.parseInt(normalized.slice(1, 3), 16));
  const green = channel(Number.parseInt(normalized.slice(3, 5), 16));
  const blue = channel(Number.parseInt(normalized.slice(5, 7), 16));
  return (0.2126 * red) + (0.7152 * green) + (0.0722 * blue);
}

export function contrastRatio(foreground: string, background: string): number {
  const left = relativeLuminance(foreground);
  const right = relativeLuminance(background);
  const lighter = Math.max(left, right);
  const darker = Math.min(left, right);
  return (lighter + 0.05) / (darker + 0.05);
}

export function readableTextColor(background: string): string {
  const whiteRatio = contrastRatio(TORE_TEXT_LIGHT, background);
  const darkRatio = contrastRatio(TORE_TEXT_DARK, background);
  return whiteRatio >= darkRatio ? TORE_TEXT_LIGHT : TORE_TEXT_DARK;
}

export type ResolvedStructureBranding = {
  primary: string;
  primaryText: string;
  primaryContrast: number;
  secondary: string;
  secondaryText: string;
  secondaryContrast: number;
  accent: string;
  accentContrast: number;
  usedToreFallback: boolean;
};

/**
 * Keeps brand backgrounds intact whenever readable foreground text can be chosen.
 * Secondary is also used as text/accent on TORÈ's dark surface; when it misses
 * WCAG AA (4.5:1), the public page falls back to TORÈ yellow for that use only.
 */
export function resolveStructureBranding(
  primaryColor?: string | null,
  secondaryColor?: string | null,
): ResolvedStructureBranding {
  let primary = normalizeHex(primaryColor, TORE_PRIMARY);
  let primaryText = readableTextColor(primary);
  let primaryContrast = contrastRatio(primaryText, primary);
  let usedToreFallback = !isHexColor(primaryColor ?? TORE_PRIMARY) || !isHexColor(secondaryColor ?? TORE_SECONDARY);

  if (primaryContrast < 4.5) {
    primary = TORE_PRIMARY;
    primaryText = readableTextColor(primary);
    primaryContrast = contrastRatio(primaryText, primary);
    usedToreFallback = true;
  }

  const secondary = normalizeHex(secondaryColor, TORE_SECONDARY);
  const secondaryText = readableTextColor(secondary);
  const secondaryContrast = contrastRatio(secondaryText, secondary);

  const requestedAccentContrast = contrastRatio(secondary, TORE_SURFACE);
  const accent = requestedAccentContrast >= 4.5 ? secondary : TORE_SECONDARY;
  const accentContrast = contrastRatio(accent, TORE_SURFACE);
  if (accent !== secondary) usedToreFallback = true;

  return {
    primary,
    primaryText,
    primaryContrast,
    secondary,
    secondaryText,
    secondaryContrast,
    accent,
    accentContrast,
    usedToreFallback,
  };
}

function loadImage(source: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Impossible de lire cette image."));
    image.src = source;
  });
}

export async function cropImageToBlob(
  source: string,
  targetWidth: number,
  targetHeight: number,
  zoom: number,
  positionX: number,
  positionY: number,
): Promise<Blob> {
  const image = await loadImage(source);
  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Le recadrage n’est pas disponible dans ce navigateur.");

  const baseScale = Math.max(targetWidth / image.naturalWidth, targetHeight / image.naturalHeight);
  const scale = baseScale * Math.max(1, zoom);
  const drawWidth = image.naturalWidth * scale;
  const drawHeight = image.naturalHeight * scale;
  const overflowX = Math.max(0, drawWidth - targetWidth);
  const overflowY = Math.max(0, drawHeight - targetHeight);
  const drawX = -overflowX * (Math.min(100, Math.max(0, positionX)) / 100);
  const drawY = -overflowY * (Math.min(100, Math.max(0, positionY)) / 100);

  context.drawImage(image, drawX, drawY, drawWidth, drawHeight);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Impossible d’exporter l’image recadrée.")), "image/webp", 0.9);
  });
}
