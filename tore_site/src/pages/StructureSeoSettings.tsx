import { FormEvent, useEffect, useState } from "react";
import { Search, Save } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, apiFetch } from "@/lib/api";
import "@/styles/forum.css";

type SeoPayload = {
  slug: string;
  name?: string;
  title?: string | null;
  description?: string | null;
  imageUrl?: string | null;
  indexable: boolean;
};

type SeoUpdate = { slug: string; previousSlug?: string | null; seo: { indexable: boolean; title?: string | null; description?: string | null; imageUrl?: string | null } };

export default function StructureSeoSettingsPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<SeoPayload | null>(null);
  const [nextSlug, setNextSlug] = useState(slug);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    setError(null);
    void apiFetch<SeoPayload>(`/forum/seo/structures/${encodeURIComponent(slug)}/settings`)
      .then((payload) => { if (active) { setData(payload); setNextSlug(payload.slug); } })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Impossible de charger les paramètres SEO."); });
    return () => { active = false; };
  }, [slug]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!data) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      const result = await apiFetch<SeoUpdate>(`/forum/seo/structures/${encodeURIComponent(slug)}`, {
        method: "PATCH",
        body: JSON.stringify({
          slug: nextSlug,
          indexable: data.indexable,
          title: data.title || "",
          description: data.description || "",
          image_url: data.imageUrl || "",
        }),
      });
      setData({ ...data, slug: result.slug, ...result.seo });
      setNotice("SEO et URL enregistrés. Les anciens slugs restent redirigés en 301.");
      if (result.slug !== slug) navigate(`/forum/structures/${result.slug}/seo`, { replace: true });
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) setError("Ce slug est déjà utilisé ou réservé par un ancien slug.");
      else setError(reason instanceof Error ? reason.message : "Enregistrement impossible.");
    } finally { setSaving(false); }
  }

  if (error && !data) return <main className="forum-main"><div className="forum-alert">{error}</div></main>;
  if (!data) return <main className="forum-main"><div className="forum-empty">Chargement du SEO…</div></main>;

  return <main className="forum-main">
    <div className="forum-main__head"><div><span className="forum-eyebrow">Référencement</span><h1>SEO & partage</h1><p>Contrôlez l’URL publique, l’indexation et les aperçus de partage de la structure et de ses événements publics.</p></div><span className="forum-badge"><Search size={14} /> SEO</span></div>
    {error ? <div className="forum-alert">{error}</div> : null}
    {notice ? <div className="forum-alert">{notice}</div> : null}
    <section className="forum-card">
      <form className="forum-form" onSubmit={save}>
        <label>Slug public<input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" minLength={2} maxLength={160} value={nextSlug} onChange={(event) => setNextSlug(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} /><small>/forum/structures/{nextSlug}</small></label>
        <label>Titre SEO<input maxLength={180} value={data.title ?? ""} onChange={(event) => setData({ ...data, title: event.target.value })} placeholder={`${data.name || "Structure"} — TORÈ`} /></label>
        <label>Description SEO<textarea maxLength={320} value={data.description ?? ""} onChange={(event) => setData({ ...data, description: event.target.value })} /></label>
        <label>Image de partage<input type="url" value={data.imageUrl ?? ""} onChange={(event) => setData({ ...data, imageUrl: event.target.value })} placeholder="https://…" /></label>
        <label className="forum-inline"><input type="checkbox" checked={data.indexable} onChange={(event) => setData({ ...data, indexable: event.target.checked })} /> Autoriser l’indexation de cette structure et de ses événements publics</label>
        <p className="forum-muted">Désactivé, les pages restent partageables mais renvoient <code>noindex,nofollow</code> et sont absentes des sitemaps.</p>
        <button className="forum-button forum-button--primary" disabled={saving} type="submit"><Save size={15} /> Enregistrer</button>
      </form>
    </section>
  </main>;
}
