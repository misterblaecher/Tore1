import { useState, type FormEvent } from "react";
import { CalendarDays } from "lucide-react";
import { useStructureResource, useStructureWrite } from "@/hooks/use-structure-resource";
import { ApiError } from "@/lib/api";

type EventItem = { id: number; name: string; startsAt?: string; endsAt?: string; venue?: string; city?: string; description?: string; publicationStatus?: string; visibility?: string };
const dateLabel = (value?: string) => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString("fr-BE") : "Date à confirmer";

export default function StructureEvents({ slug, canCreate, canManage }: { slug: string; canCreate: boolean; canManage: boolean }) {
  const base = `/forum/structures/${encodeURIComponent(slug)}/events`;
  const { data, error, loading, reload } = useStructureResource<{ items: EventItem[] }>(base);
  const mutation = useStructureWrite();
  const [name, setName] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [description, setDescription] = useState("");
  const [venue, setVenue] = useState("");
  const [validation, setValidation] = useState("");
  const [saved, setSaved] = useState("");
  async function create(event: FormEvent) {
    event.preventDefault(); setValidation(""); setSaved("");
    if (Date.parse(endsAt) <= Date.parse(startsAt)) { setValidation("La fin doit être postérieure au début de l’événement."); return; }
    const result = await mutation.write<EventItem>(base, "POST", { name: name.trim(), starts_at: new Date(startsAt).toISOString(), ends_at: new Date(endsAt).toISOString(), description, venue, visibility: "PRIVATE", publication_status: "DRAFT" });
    if (!result) return;
    setName(""); setStartsAt(""); setEndsAt(""); setDescription(""); setVenue(""); setSaved("Brouillon enregistré. Vous pouvez maintenant le publier."); reload();
  }
  async function publish(item: EventItem, published: boolean) {
    setSaved("");
    const result = await mutation.write<EventItem>(`${base}/${item.id}`, "PATCH", { publication_status: published ? "PUBLISHED" : "DRAFT", visibility: published ? "PUBLIC" : "PRIVATE" });
    if (result) { setSaved(published ? "Événement publié pour la découverte dans TORÈ. La page de la structure respecte ses réglages de visibilité." : "Événement retiré de la publication publique."); reload(); }
  }
  const failure = error || mutation.error;
  return <div className="forum-grid-2"><section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Calendrier de la structure</span><h2>Événements liés</h2></div><CalendarDays size={20} /></div>
    {failure ? <p className="forum-alert" role="alert">{failure instanceof ApiError ? failure.message : "Impossible de charger ou enregistrer les événements."}<button onClick={reload}>Réessayer</button></p> : null}
    {saved ? <p role="status">{saved}</p> : null}
    {loading ? <p role="status">Chargement des événements…</p> : <div className="forum-list">{data?.items.length ? data.items.map(item => <article className="forum-row" key={item.id}><div><strong>{item.name}</strong><p>{dateLabel(item.startsAt)} · {item.venue || item.city || "Lieu à confirmer"}</p><span className="forum-badge">{item.publicationStatus === "PUBLISHED" && item.visibility === "PUBLIC" ? "Public" : "Brouillon / privé"}</span></div>{canManage ? <button className="forum-button forum-button--ghost" disabled={mutation.busy} onClick={() => void publish(item, !(item.publicationStatus === "PUBLISHED" && item.visibility === "PUBLIC"))}>{item.publicationStatus === "PUBLISHED" && item.visibility === "PUBLIC" ? "Retirer la publication" : "Publier dans TORÈ"}</button> : null}</article>) : !error ? <p className="forum-empty">Aucun événement lié à cette structure.</p> : null}</div>}
  </section>{canCreate ? <section className="forum-card" id="create-event"><span className="forum-eyebrow">Préparation</span><h2>Créer un événement</h2><form className="forum-form" onSubmit={create}><fieldset disabled={mutation.busy} className="forum-form"><label>Nom<input required minLength={2} maxLength={180} value={name} onChange={e => setName(e.target.value)} /></label><label>Début<input required type="datetime-local" value={startsAt} onChange={e => setStartsAt(e.target.value)} /></label><label>Fin<input required type="datetime-local" value={endsAt} onChange={e => setEndsAt(e.target.value)} /></label><label>Lieu<input maxLength={255} value={venue} onChange={e => setVenue(e.target.value)} /></label><label>Description<textarea maxLength={10000} value={description} onChange={e => setDescription(e.target.value)} /></label>{validation ? <p role="alert">{validation}</p> : null}<button className="forum-button forum-button--primary" type="submit">{mutation.busy ? "Enregistrement…" : "Créer le brouillon"}</button></fieldset></form></section> : null}</div>;
}
