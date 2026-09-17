import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { useParams } from "react-router-dom";
import { Image as ImageIcon, Link2, Palette, Save, Settings, ShieldCheck, Upload, ZoomIn } from "lucide-react";
import { API_BASE, ApiError, apiFetch } from "@/lib/api";
import { cropImageToBlob, isHexColor, resolveStructureBranding, TORE_PRIMARY, TORE_SECONDARY } from "@/lib/structure-branding";
import "@/styles/forum.css";
import "@/styles/structure-branding.css";

type StructureSettings = {
  id?: number;
  name: string;
  slug?: string;
  type?: string;
  description?: string | null;
  city?: string | null;
  websiteUrl?: string | null;
  instagramHandle?: string | null;
  logoUrl?: string | null;
  bannerUrl?: string | null;
  primaryColor?: string | null;
  secondaryColor?: string | null;
};

type StoredFilePayload = { id: string; purpose: string; visibility: string };
type MediaKind = "logo" | "banner";

function newIdem() { return `forum-brand-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`; }
function actionHeaders() { return { "Idempotency-Key": newIdem() }; }
function managedFileId(url?: string | null): string | null { return url?.match(/\/forum\/public\/files\/([0-9a-f-]{36})(?:$|[?#])/i)?.[1] ?? null; }
function validateImportedUrl(value: string): string | null { try { const parsed = new URL(value); return parsed.protocol === "https:" || parsed.protocol === "http:" ? null : "Utilisez une URL http(s)."; } catch { return "URL invalide."; } }

export default function StructurePortalSettings({ slug: slugProp }: { slug?: string } = {}) {
  const { slug: routeSlug } = useParams();
  const slug = slugProp || routeSlug || "";
  const [data, setData] = useState<StructureSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!slug) { setError("Structure introuvable."); return; }
    let active = true;
    setError(null);
    void apiFetch<StructureSettings>(`/forum/structures/${encodeURIComponent(slug)}/settings`)
      .then((payload) => { if (active) setData(payload); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError && reason.status === 403 ? "Les paramètres de marque sont réservés aux rôles de gestion." : reason instanceof Error ? reason.message : "Impossible de charger les paramètres."); });
    return () => { active = false; };
  }, [slug]);

  const primaryValid = isHexColor(data?.primaryColor || TORE_PRIMARY);
  const secondaryValid = isHexColor(data?.secondaryColor || TORE_SECONDARY);
  const branding = useMemo(() => resolveStructureBranding(data?.primaryColor, data?.secondaryColor), [data?.primaryColor, data?.secondaryColor]);

  async function patchSettings(patch: Record<string, unknown>): Promise<StructureSettings> {
    return apiFetch<StructureSettings>(`/forum/structures/${encodeURIComponent(slug)}/settings`, { method: "PATCH", headers: actionHeaders(), body: JSON.stringify(patch) });
  }

  async function saveIdentity(event: FormEvent) {
    event.preventDefault(); if (!data) return; setSaving(true); setError(null); setNotice(null);
    try { const next = await patchSettings({ name: data.name, description: data.description || null, city: data.city || null, website_url: data.websiteUrl || null, instagram_handle: data.instagramHandle || null }); setData(next); setNotice("Identité enregistrée."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Enregistrement impossible."); }
    finally { setSaving(false); }
  }

  async function saveColors(event: FormEvent) {
    event.preventDefault(); if (!data || !primaryValid || !secondaryValid) return; setSaving(true); setError(null); setNotice(null);
    try { const next = await patchSettings({ primary_color: (data.primaryColor || TORE_PRIMARY).toUpperCase(), secondary_color: (data.secondaryColor || TORE_SECONDARY).toUpperCase() }); setData(next); setNotice("Couleurs enregistrées."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Enregistrement impossible."); }
    finally { setSaving(false); }
  }

  async function setMediaUrl(kind: MediaKind, url: string) {
    if (!data) return;
    const oldUrl = kind === "logo" ? data.logoUrl : data.bannerUrl;
    const field = kind === "logo" ? "logo_url" : "banner_url";
    setSaving(true); setError(null); setNotice(null);
    try {
      const next = await patchSettings({ [field]: url }); setData(next); setNotice(kind === "logo" ? "Logo enregistré." : "Bannière enregistrée.");
      const oldId = managedFileId(oldUrl); const newId = managedFileId(url);
      if (oldId && oldId !== newId) void apiFetch(`/forum/structures/${encodeURIComponent(slug)}/files/${oldId}`, { method: "DELETE" }).catch(() => undefined);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Enregistrement du média impossible."); throw reason; }
    finally { setSaving(false); }
  }

  async function uploadMedia(kind: MediaKind, file: File) {
    const form = new FormData(); form.append("purpose", kind === "logo" ? "LOGO" : "BANNER"); form.append("file", file);
    const uploaded = await apiFetch<StoredFilePayload>(`/forum/structures/${encodeURIComponent(slug)}/files`, { method: "POST", body: form });
    try {
      await apiFetch(`/forum/structures/${encodeURIComponent(slug)}/files/${uploaded.id}/visibility`, { method: "PATCH", body: JSON.stringify({ visibility: "PUBLIC", confirm_public: true }) });
      await setMediaUrl(kind, `${API_BASE}/forum/public/files/${uploaded.id}`);
    } catch (reason) { void apiFetch(`/forum/structures/${encodeURIComponent(slug)}/files/${uploaded.id}`, { method: "DELETE" }).catch(() => undefined); throw reason; }
  }

  if (error && !data) return <main className="forum-main"><div className="forum-alert">{error}</div></main>;
  if (!data) return <main className="forum-main"><div className="forum-empty">Chargement des paramètres…</div></main>;

  const previewStyle = { "--structure-primary": branding.primary, "--structure-primary-text": branding.primaryText, "--structure-secondary": branding.secondary, "--structure-secondary-text": branding.secondaryText, "--structure-accent": branding.accent } as CSSProperties;

  return <main className="forum-main structure-branding-settings">
    <div className="forum-main__head"><div><span className="forum-eyebrow">Identité publique</span><h1>Logo, bannière & branding</h1><p>Importez, recadrez et publiez les médias de la structure sans hébergement externe.</p></div><span className="forum-badge"><Settings size={14} /> Paramètres</span></div>
    {error ? <div className="forum-alert">{error}</div> : null}{notice ? <div className="structure-branding-notice">{notice}</div> : null}
    <div className="structure-branding-layout">
      <div className="structure-branding-stack">
        <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Médias</span><h2>Identité visuelle</h2></div><ImageIcon size={20} /></div><div className="structure-media-grid"><StructureMediaEditor kind="logo" currentUrl={data.logoUrl} disabled={saving} onUpload={(file) => uploadMedia("logo", file)} onImport={(url) => setMediaUrl("logo", url)} /><StructureMediaEditor kind="banner" currentUrl={data.bannerUrl} disabled={saving} onUpload={(file) => uploadMedia("banner", file)} onImport={(url) => setMediaUrl("banner", url)} /></div></section>
        <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Palette</span><h2>Couleurs de la structure</h2></div><Palette size={20} /></div><form className="structure-color-form" onSubmit={saveColors}><ColorField label="Couleur primaire" value={data.primaryColor || TORE_PRIMARY} valid={primaryValid} fallback={TORE_PRIMARY} onChange={(value) => setData({ ...data, primaryColor: value })} /><ColorField label="Couleur secondaire" value={data.secondaryColor || TORE_SECONDARY} valid={secondaryValid} fallback={TORE_SECONDARY} onChange={(value) => setData({ ...data, secondaryColor: value })} /><button className="forum-button forum-button--primary" disabled={saving || !primaryValid || !secondaryValid} type="submit"><Save size={15} /> Enregistrer les couleurs</button></form><div className="structure-contrast-grid"><ContrastLine label="Texte sur primaire" ratio={branding.primaryContrast} pass={branding.primaryContrast >= 4.5} /><ContrastLine label="Accent sur fond TORÈ" ratio={branding.accentContrast} pass={branding.accentContrast >= 4.5} /></div>{branding.accent !== branding.secondary ? <div className="structure-contrast-warning"><ShieldCheck size={16} /> Le secondaire choisi n’atteint pas 4,5:1 sur le fond sombre. L’accent public utilise automatiquement le jaune TORÈ, sans modifier votre couleur enregistrée.</div> : null}</section>
        <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Informations</span><h2>Identité de la structure</h2></div><Settings size={20} /></div><form className="forum-form" onSubmit={saveIdentity}><label>Nom<input required value={data.name} onChange={(event) => setData({ ...data, name: event.target.value })} /></label><label>Description<textarea value={data.description ?? ""} onChange={(event) => setData({ ...data, description: event.target.value })} /></label><div className="structure-form-columns"><label>Ville<input value={data.city ?? ""} onChange={(event) => setData({ ...data, city: event.target.value })} /></label><label>Instagram<input value={data.instagramHandle ?? ""} onChange={(event) => setData({ ...data, instagramHandle: event.target.value })} /></label></div><label>Site web<input type="url" value={data.websiteUrl ?? ""} onChange={(event) => setData({ ...data, websiteUrl: event.target.value })} /></label><button className="forum-button forum-button--primary" disabled={saving} type="submit"><Save size={15} /> Enregistrer l’identité</button></form></section>
      </div>
      <aside className="structure-branding-preview forum-card" style={previewStyle}><span className="forum-eyebrow">Aperçu en temps réel</span><div className="structure-branding-preview__hero" style={{ backgroundImage: data.bannerUrl ? `linear-gradient(90deg, rgba(8,8,9,.93), rgba(8,8,9,.52)), url(${data.bannerUrl})` : undefined }}><div className="structure-branding-preview__identity"><div className="structure-branding-preview__logo" style={{ backgroundImage: data.logoUrl ? `url(${data.logoUrl})` : undefined }}>{!data.logoUrl ? data.name.slice(0, 1).toUpperCase() : null}</div><div><small>Page officielle TORÈ</small><h2>{data.name}</h2><p>{data.description || "La présentation publique de votre structure."}</p></div></div><button data-testid="branding-preview-button" type="button" style={{ background: branding.primary, color: branding.primaryText, borderColor: branding.primary }}>Espace membre</button></div><div className="structure-branding-preview__content"><strong style={{ color: branding.accent }}>Prochain événement</strong><p>Les textes de contenu restent sur une surface TORÈ lisible. Seuls les accents sûrs utilisent les couleurs de marque.</p><span style={{ background: branding.secondary, color: branding.secondaryText }}>Couleur secondaire</span></div></aside>
    </div>
  </main>;
}

function ColorField({ label, value, valid, fallback, onChange }: { label: string; value: string; valid: boolean; fallback: string; onChange: (value: string) => void }) { return <div className="structure-color-field"><label>{label}<div className="structure-color-inputs"><input aria-label={`${label} picker`} type="color" value={valid ? value : fallback} onChange={(event) => onChange(event.target.value.toUpperCase())} /><input aria-label={`${label} (HEX)`} value={value} onChange={(event) => onChange(event.target.value)} maxLength={7} spellCheck={false} /></div></label>{!valid ? <small className="structure-field-error">Format HEX attendu, par ex. #BA1733.</small> : null}</div>; }
function ContrastLine({ label, ratio, pass }: { label: string; ratio: number; pass: boolean }) { return <div className="structure-contrast-line"><span>{label}</span><strong>{ratio.toFixed(2)}:1 · {pass ? "AA" : "insuffisant"}</strong></div>; }

function StructureMediaEditor({ kind, currentUrl, disabled, onUpload, onImport }: { kind: MediaKind; currentUrl?: string | null; disabled: boolean; onUpload: (file: File) => Promise<void>; onImport: (url: string) => Promise<void> }) {
  const [source, setSource] = useState<string | null>(null); const [zoom, setZoom] = useState(1); const [positionX, setPositionX] = useState(50); const [positionY, setPositionY] = useState(50); const [urlValue, setUrlValue] = useState(currentUrl || ""); const [localError, setLocalError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const isLogo = kind === "logo"; const label = isLogo ? "logo" : "bannière";
  useEffect(() => setUrlValue(currentUrl || ""), [currentUrl]);
  useEffect(() => () => { if (source?.startsWith("blob:")) URL.revokeObjectURL(source); }, [source]);
  function selectFile(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (!file) return; if (!file.type.startsWith("image/")) { setLocalError("Sélectionnez une image."); return; } if (file.size > 20 * 1024 * 1024) { setLocalError("Image trop lourde (20 Mo maximum)."); return; } if (source?.startsWith("blob:")) URL.revokeObjectURL(source); setSource(URL.createObjectURL(file)); setZoom(1); setPositionX(50); setPositionY(50); setLocalError(null); }
  async function saveCrop() { if (!source) return; setBusy(true); setLocalError(null); try { const blob = await cropImageToBlob(source, isLogo ? 800 : 1920, isLogo ? 800 : 600, zoom, positionX, positionY); await onUpload(new File([blob], `${kind}.webp`, { type: "image/webp" })); if (source.startsWith("blob:")) URL.revokeObjectURL(source); setSource(null); } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "Upload impossible."); } finally { setBusy(false); } }
  async function importUrl() { const validation = validateImportedUrl(urlValue.trim()); if (validation) { setLocalError(validation); return; } setBusy(true); setLocalError(null); try { await onImport(urlValue.trim()); } catch (reason) { setLocalError(reason instanceof Error ? reason.message : "Import impossible."); } finally { setBusy(false); } }
  const preview = source || currentUrl;
  return <div className={`structure-media-editor structure-media-editor--${kind}`}><div className="structure-media-editor__head"><div><strong>{isLogo ? "Logo" : "Bannière"}</strong><small>{isLogo ? "Carré · export 800 × 800" : "Panoramique · export 1920 × 600"}</small></div><Upload size={17} /></div><div className="structure-media-editor__viewport" data-kind={kind}>{preview ? <img src={preview} alt={`Aperçu ${label}`} style={{ objectPosition: `${positionX}% ${positionY}%`, transform: source ? `scale(${zoom})` : undefined, transformOrigin: `${positionX}% ${positionY}%` }} /> : <div className="structure-media-editor__empty"><ImageIcon size={24} /> Aucun {label}</div>}</div><label className="forum-button forum-button--ghost structure-upload-button"><Upload size={15} /> Importer un {label}<input aria-label={`Importer un ${label}`} type="file" accept="image/png,image/jpeg,image/webp" disabled={disabled || busy} onChange={selectFile} /></label>{source ? <div className="structure-crop-controls"><label><ZoomIn size={14} /> Zoom<input aria-label={`Zoom ${label}`} type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => setZoom(Number(event.target.value))} /></label><label>Horizontal<input aria-label={`Position horizontale ${label}`} type="range" min="0" max="100" value={positionX} onChange={(event) => setPositionX(Number(event.target.value))} /></label><label>Vertical<input aria-label={`Position verticale ${label}`} type="range" min="0" max="100" value={positionY} onChange={(event) => setPositionY(Number(event.target.value))} /></label><button className="forum-button forum-button--primary" type="button" disabled={disabled || busy} onClick={() => void saveCrop()}><Save size={15} /> {busy ? "Envoi…" : "Recadrer et enregistrer"}</button></div> : null}<details className="structure-url-import"><summary><Link2 size={14} /> Importer depuis une URL</summary><div><input type="url" value={urlValue} onChange={(event) => setUrlValue(event.target.value)} placeholder="https://…" /><button className="forum-button forum-button--ghost" type="button" disabled={disabled || busy} onClick={() => void importUrl()}>Utiliser l’URL</button></div></details>{localError ? <small className="structure-field-error">{localError}</small> : null}</div>;
}
