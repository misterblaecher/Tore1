import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Settings } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { structurePath } from "@/lib/forum-navigation";
import { defaultPortal, portalBlockLabels, type PortalBlock, type PortalContent, type PortalStructure } from "@/lib/structure-portal";
import "@/styles/structure-portal.css";

export default function StructurePortalSettings({ slug, canManage }: { slug: string; canManage: boolean }) {
  const [data, setData] = useState<PortalStructure | null>(null);
  const [portal, setPortal] = useState<PortalContent>(defaultPortal);
  const [sponsors, setSponsors] = useState("");
  const [services, setServices] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!canManage) return;
    let active = true;
    void apiFetch<PortalStructure>(`/forum/structures/${encodeURIComponent(slug)}/settings`).then((next) => {
      if (!active) return;
      setData(next); setPortal({ ...defaultPortal, ...next.portal });
      setSponsors((next.sponsors ?? []).join("\n")); setServices((next.portal?.services ?? []).join("\n"));
    }).catch(() => { if (active) setError("Impossible de charger les paramètres."); });
    return () => { active = false; };
  }, [slug, canManage]);
  if (!canManage) return <p className="forum-empty">La configuration est réservée aux responsables de la structure.</p>;
  if (!data) return <p className={error ? "forum-alert" : "forum-empty"}>{error || "Chargement des paramètres…"}</p>;
  const current = data;
  function update(key: keyof PortalStructure, value: string) { setData((previous) => previous ? { ...previous, [key]: value } : previous); setSaved(false); }
  function updatePortal(key: keyof PortalContent, value: string | PortalBlock[]) { setPortal((previous) => ({ ...previous, [key]: value })); setSaved(false); }
  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSaved(false);
    const lines = (value: string) => value.split("\n").map((line) => line.trim()).filter(Boolean);
    try {
      const next = await apiFetch<PortalStructure>(`/forum/structures/${encodeURIComponent(slug)}/settings`, {
        method: "PATCH", headers: { "Idempotency-Key": `portal-${crypto.randomUUID()}` },
        body: JSON.stringify({
          name: current.name, description: current.description ?? "", org_type: current.type,
          city: current.city ?? "", address: current.address ?? "", contact_email: current.contactEmail ?? "",
          contact_phone: current.contactPhone ?? "", website_url: current.websiteUrl ?? "",
          instagram_handle: current.instagramHandle ?? "", logo_url: current.logoUrl ?? "", banner_url: current.bannerUrl ?? "",
          history: current.history ?? "", sponsors: lines(sponsors), portal: { ...portal, services: lines(services) },
        }),
      });
      setData(next); setSaved(true);
      window.dispatchEvent(new Event("tore:structure-updated"));
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Enregistrement impossible. Réessayez."); }
    finally { setSaving(false); }
  }
  return <section className="forum-card">
    <div className="forum-section-title"><div><span className="forum-eyebrow">Identité & page publique</span><h2>Présenter votre structure</h2></div><Settings size={20} /></div>
    <p className="forum-muted">Ces informations alimentent votre page publique selon les réglages de visibilité de la structure.</p>
    <form className="forum-form" onSubmit={save}>
      <fieldset disabled={saving} className="portal-editor-fields">
        <label>Nom<input required minLength={2} maxLength={140} value={data.name} onChange={(event) => update("name", event.target.value)} /></label>
        <label>Type de structure<select value={data.type} onChange={(event) => update("type", event.target.value)}><option value="COMMITTEE">Comité</option><option value="CIRCLE">Cercle</option><option value="ORDER">Ordre</option><option value="BAR">Bar partenaire</option><option value="ASSOCIATION">Association</option><option value="PARTNER">Structure partenaire</option><option value="OTHER">Autre</option></select></label>
        <label className="portal-editor-wide">Description courte<textarea maxLength={10000} value={data.description ?? ""} onChange={(event) => update("description", event.target.value)} /></label>
        <label>URL du logo<input type="url" maxLength={512} value={data.logoUrl ?? ""} onChange={(event) => update("logoUrl", event.target.value)} placeholder="https://…" /></label>
        <label>URL de la bannière<input type="url" maxLength={1000} value={data.bannerUrl ?? ""} onChange={(event) => update("bannerUrl", event.target.value)} placeholder="https://…" /></label>
        <label>Ville<input maxLength={120} value={data.city ?? ""} onChange={(event) => update("city", event.target.value)} /></label>
        <label>Adresse<input maxLength={255} value={data.address ?? ""} onChange={(event) => update("address", event.target.value)} /></label>
        <label>E-mail de contact<input type="email" maxLength={255} value={data.contactEmail ?? ""} onChange={(event) => update("contactEmail", event.target.value)} /></label>
        <label>Téléphone<input type="tel" maxLength={64} value={data.contactPhone ?? ""} onChange={(event) => update("contactPhone", event.target.value)} /></label>
        <label>Site web<input type="url" maxLength={512} value={data.websiteUrl ?? ""} onChange={(event) => update("websiteUrl", event.target.value)} /></label>
        <label>Instagram<input maxLength={64} value={data.instagramHandle ?? ""} onChange={(event) => update("instagramHandle", event.target.value)} placeholder="@votre_structure" /></label>
        <label className="portal-editor-wide">À propos<textarea maxLength={10000} value={portal.about} onChange={(event) => updatePortal("about", event.target.value)} /></label>
        <label>Horaires<textarea maxLength={2000} value={portal.opening_hours} onChange={(event) => updatePortal("opening_hours", event.target.value)} placeholder="Lundi – vendredi : …" /></label>
        <label>Activités & services — un par ligne<textarea value={services} onChange={(event) => { setServices(event.target.value); setSaved(false); }} /></label>
        <label className="portal-editor-wide">Histoire & folklore<textarea maxLength={10000} value={data.history ?? ""} onChange={(event) => update("history", event.target.value)} /></label>
        <label>Partenaires — un nom par ligne<textarea value={sponsors} onChange={(event) => { setSponsors(event.target.value); setSaved(false); }} /></label>
        <label>Annonce à la une<textarea maxLength={2000} value={portal.announcement} onChange={(event) => updatePortal("announcement", event.target.value)} /></label>
        <div className="portal-editor-wide"><p className="forum-muted">Blocs affichés (les règles de confidentialité restent prioritaires)</p><div className="portal-editor-blocks">{(Object.keys(portalBlockLabels) as PortalBlock[]).map((block) => <label key={block}><input type="checkbox" checked={!portal.hidden_blocks.includes(block)} onChange={(event) => updatePortal("hidden_blocks", event.target.checked ? portal.hidden_blocks.filter((item) => item !== block) : [...portal.hidden_blocks, block])} />{portalBlockLabels[block]}</label>)}</div></div>
      </fieldset>
      {error ? <p className="forum-alert" role="alert">{error}</p> : null}
      {saved ? <p role="status" className="forum-muted">La page de votre structure a été mise à jour.</p> : null}
      <div className="forum-inline"><button className="forum-button forum-button--primary" disabled={saving} type="submit">{saving ? "Enregistrement…" : "Enregistrer"}</button><Link className="forum-button forum-button--ghost" to={structurePath(slug, "public")}>Voir la page publique <ArrowUpRight size={15} /></Link></div>
    </form>
  </section>;
}
