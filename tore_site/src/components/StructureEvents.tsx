import { useMemo, useState, type FormEvent } from "react";
import { Link2, CalendarDays, ChevronLeft, ExternalLink, Image as ImageIcon, Layers3, RefreshCw, Save, Search, Users } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { useStructureResource, useStructureWrite } from "@/hooks/use-structure-resource";
import { ApiError } from "@/lib/api";
import "@/styles/forum-events-v341.css";

type Lifecycle = "DRAFT" | "PUBLISHED" | "SYNCED_TO_APP" | "LIVE" | "CLOSED" | "RECAP_DRAFT" | "RECAP_PUBLISHED" | "ARCHIVED";
type EventItem = {
  id: number;
  name: string;
  startsAt?: string | null;
  endsAt?: string | null;
  venue?: string | null;
  city?: string | null;
  description?: string | null;
  publicationStatus: "DRAFT" | "PUBLISHED";
  visibility: "PUBLIC" | "PRIVATE";
  entryPriceCents: number;
  capacity?: number | null;
  coverUrl?: string | null;
  modules: string[];
  coOrganizers: string[];
  recap: string;
  lifecycleStatus: Lifecycle;
  appSyncStatus: "SYNCED" | "NOT_SYNCED";
  staffCount: number;
  documentCount: number;
  albumId?: number | null;
};

type EventForm = {
  name: string;
  startsAt: string;
  endsAt: string;
  venue: string;
  city: string;
  description: string;
  capacity: string;
  price: string;
  coverUrl: string;
  visibility: "PUBLIC" | "PRIVATE";
  modules: string[];
  coOrganizers: string;
  recap: string;
};

const lifecycle: Lifecycle[] = ["DRAFT", "PUBLISHED", "SYNCED_TO_APP", "LIVE", "CLOSED", "RECAP_DRAFT", "RECAP_PUBLISHED", "ARCHIVED"];
const lifecycleLabels: Record<Lifecycle, string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publié",
  SYNCED_TO_APP: "Synchronisé app",
  LIVE: "En cours",
  CLOSED: "Terminé",
  RECAP_DRAFT: "Récap en préparation",
  RECAP_PUBLISHED: "Récap publié",
  ARCHIVED: "Archivé",
};
const allowedTransitions: Record<Lifecycle, Lifecycle[]> = {
  DRAFT: ["PUBLISHED"],
  PUBLISHED: ["DRAFT", "SYNCED_TO_APP"],
  SYNCED_TO_APP: ["PUBLISHED", "LIVE"],
  LIVE: ["CLOSED"],
  CLOSED: ["RECAP_DRAFT", "ARCHIVED"],
  RECAP_DRAFT: ["CLOSED", "RECAP_PUBLISHED"],
  RECAP_PUBLISHED: ["RECAP_DRAFT", "ARCHIVED"],
  ARCHIVED: [],
};
const moduleOptions = ["entry", "feed", "predictions", "ranking", "music", "orders", "wallet", "photos"];
const moduleLabels: Record<string, string> = { entry: "Entrées", feed: "Feed live", predictions: "Predictions", ranking: "Classement", music: "Musique", orders: "Commandes", wallet: "Credits", photos: "Photos" };

function toLocalInput(value?: string | null) {
  if (!value || Number.isNaN(Date.parse(value))) return "";
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}
function dateLabel(value?: string | null) {
  return value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Date à confirmer";
}
function money(cents: number) { return `${(cents / 100).toLocaleString("fr-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`; }
function emptyForm(): EventForm {
  return { name: "", startsAt: "", endsAt: "", venue: "", city: "", description: "", capacity: "", price: "0", coverUrl: "", visibility: "PUBLIC", modules: [], coOrganizers: "", recap: "" };
}
function eventToForm(event: EventItem): EventForm {
  return {
    name: event.name,
    startsAt: toLocalInput(event.startsAt),
    endsAt: toLocalInput(event.endsAt),
    venue: event.venue || "",
    city: event.city || "",
    description: event.description || "",
    capacity: event.capacity ? String(event.capacity) : "",
    price: String((event.entryPriceCents || 0) / 100),
    coverUrl: event.coverUrl || "",
    visibility: event.visibility,
    modules: event.modules || [],
    coOrganizers: (event.coOrganizers || []).join(", "),
    recap: event.recap || "",
  };
}
function normalizeList(value: string) { return value.split(",").map(item => item.trim()).filter(Boolean); }
function apiFailure(error: unknown) { return error instanceof ApiError ? error.message : "La modification n’a pas été enregistrée sur le serveur."; }

export default function StructureEvents({ slug, canCreate, canManage }: { slug: string; canCreate: boolean; canManage: boolean }) {
  const base = `/forum/structures/${encodeURIComponent(slug)}/event-workspace`;
  const { data, error, loading, reload } = useStructureResource<{ items: EventItem[] }>(base);
  const mutation = useStructureWrite();
  const [params, setParams] = useSearchParams();
  const selectedId = Number(params.get("event") || 0) || null;
  const selected = data?.items.find(item => item.id === selectedId) ?? null;
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState<EventForm>(emptyForm());
  const [editForm, setEditForm] = useState<EventForm | null>(null);
  const [notice, setNotice] = useState("");
  const [validation, setValidation] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("fr");
    return (data?.items ?? []).filter(item => {
      const text = `${item.name} ${item.venue || ""} ${item.city || ""} ${item.lifecycleStatus}`.toLocaleLowerCase("fr");
      return (!needle || text.includes(needle)) && (!status || item.lifecycleStatus === status);
    });
  }, [data?.items, query, status]);

  const failure = error || mutation.error;
  function openEvent(item: EventItem) {
    setNotice(""); setValidation(""); setEditForm(eventToForm(item));
    const next = new URLSearchParams(params); next.set("event", String(item.id)); setParams(next);
  }
  function closeEvent() {
    setEditForm(null); setNotice(""); setValidation("");
    const next = new URLSearchParams(params); next.delete("event"); setParams(next);
  }
  function validateForm(form: EventForm) {
    if (!form.name.trim()) return "Le nom est obligatoire.";
    if (!form.startsAt || !form.endsAt) return "Les dates de début et de fin sont obligatoires.";
    if (Date.parse(form.endsAt) <= Date.parse(form.startsAt)) return "La fin doit être postérieure au début de l’événement.";
    if (form.capacity && Number(form.capacity) <= 0) return "La capacité doit être positive.";
    if (Number(form.price) < 0) return "Le prix ne peut pas être négatif.";
    return "";
  }
  function payload(form: EventForm) {
    return {
      name: form.name.trim(),
      starts_at: new Date(form.startsAt).toISOString(),
      ends_at: new Date(form.endsAt).toISOString(),
      venue: form.venue.trim() || null,
      city: form.city.trim() || null,
      description: form.description,
      visibility: form.visibility,
      entry_price_cents: Math.round((Number(form.price) || 0) * 100),
      capacity: form.capacity ? Number(form.capacity) : null,
      banner_url: form.coverUrl.trim() || null,
      modules: form.modules,
      co_organizers: normalizeList(form.coOrganizers),
      recap: form.recap,
    };
  }

  async function create(event: FormEvent) {
    event.preventDefault(); setNotice("");
    const invalid = validateForm(createForm); setValidation(invalid); if (invalid) return;
    const result = await mutation.write<EventItem>(base, "POST", { ...payload(createForm), publication_status: createForm.visibility === "PUBLIC" ? "PUBLISHED" : "DRAFT" });
    if (!result) return;
    setCreateForm(emptyForm()); setShowCreate(false); setValidation("");
    setNotice("Brouillon enregistré sur le serveur. Les données resteront disponibles après rechargement et nouvelle session.");
    reload();
    const next = new URLSearchParams(params); next.set("event", String(result.id)); setParams(next); setEditForm(eventToForm(result));
  }

  async function save(event: FormEvent) {
    event.preventDefault(); if (!selected || !editForm) return;
    setNotice(""); const invalid = validateForm(editForm); setValidation(invalid); if (invalid) return;
    const result = await mutation.write<EventItem>(`${base}/${selected.id}`, "PATCH", payload(editForm));
    if (!result) return;
    setEditForm(eventToForm(result)); setValidation("");
    setNotice("Modifications confirmées par le serveur."); reload();
  }

  async function transition(nextStatus: Lifecycle) {
    if (!selected) return;
    setNotice(""); setValidation("");
    const result = await mutation.write<EventItem>(`${base}/${selected.id}`, "PATCH", {
      lifecycle_status: nextStatus,
      ...(nextStatus === "PUBLISHED" ? { publication_status: "PUBLISHED", visibility: "PUBLIC" } : {}),
    });
    if (!result) return;
    setEditForm(eventToForm(result));
    setNotice(`Cycle de vie mis à jour : ${lifecycleLabels[nextStatus]}.`); reload();
  }

  if (selected) return <EventDetail item={selected} form={editForm ?? eventToForm(selected)} setForm={setEditForm} canManage={canManage} busy={mutation.busy} failure={failure} notice={notice} validation={validation} onBack={closeEvent} onSave={save} onTransition={transition} />;

  return <div className="forum-events-v341">
    <header className="forum-events-v341__head">
      <div><span className="forum-eyebrow">Organisation & publication</span><h1>Events</h1><p>Créer, publier, synchroniser et archiver les événements depuis le portail TORÈ.</p></div>
      {canCreate ? <button className="forum-button forum-button--primary" onClick={() => setShowCreate(value => !value)}>{showCreate ? "Fermer" : "+ Créer un événement"}</button> : null}
    </header>

    {failure ? <div className="forum-alert" role="alert">{apiFailure(failure)} <button onClick={reload}>Réessayer</button></div> : null}
    {notice ? <p className="forum-events-v341__notice" role="status">{notice}</p> : null}

    {showCreate && canCreate ? <EventFormCard title="Nouveau brouillon" form={createForm} setForm={setCreateForm} busy={mutation.busy} validation={validation} onSubmit={create} submitLabel="Enregistrer le brouillon" /> : null}

    <div className="forum-events-v341__toolbar">
      <label><Search size={16} /><input aria-label="Rechercher un événement" placeholder="Rechercher un événement…" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <select aria-label="Filtrer par statut" value={status} onChange={event => setStatus(event.target.value)}><option value="">Tous les statuts</option>{lifecycle.map(value => <option key={value} value={value}>{lifecycleLabels[value]}</option>)}</select>
      <button className="forum-button forum-button--ghost" onClick={reload}><RefreshCw size={14} /> Actualiser</button>
    </div>

    <section className="forum-events-v341__table-card">
      {loading ? <p className="forum-empty">Chargement des événements…</p> : filtered.length ? <div className="forum-events-v341__table-wrap"><table><thead><tr><th>Event</th><th>Date</th><th>Lieu</th><th>Capacité</th><th>Statut</th><th>App TORÈ</th><th>Visibilité</th><th /></tr></thead><tbody>{filtered.map(item => <tr key={item.id}><td><button className="forum-events-v341__event-link" onClick={() => openEvent(item)}><strong>{item.name}</strong><span>{item.description || "Aucune description"}</span></button></td><td>{dateLabel(item.startsAt)}</td><td>{item.venue || item.city || "À confirmer"}</td><td>{item.capacity || "—"}</td><td><span className={`forum-events-v341__status is-${item.lifecycleStatus.toLowerCase()}`}>{lifecycleLabels[item.lifecycleStatus]}</span></td><td>{item.appSyncStatus === "SYNCED" ? "Synchronisé" : "Non synchronisé"}</td><td>{item.visibility === "PUBLIC" ? "Public" : "Privé"}</td><td><button aria-label={`Ouvrir ${item.name}`} className="forum-events-v341__open" onClick={() => openEvent(item)}>→</button></td></tr>)}</tbody></table></div> : <p className="forum-empty">Aucun événement ne correspond aux filtres.</p>}
    </section>
  </div>;
}

function EventDetail({ item, form, setForm, canManage, busy, failure, notice, validation, onBack, onSave, onTransition }: { item: EventItem; form: EventForm; setForm: (form: EventForm) => void; canManage: boolean; busy: boolean; failure: unknown; notice: string; validation: string; onBack: () => void; onSave: (event: FormEvent) => void; onTransition: (next: Lifecycle) => void }) {
  return <div className="forum-events-v341 forum-events-v341--detail">
    <button className="forum-events-v341__back" onClick={onBack}><ChevronLeft size={16} /> Retour aux events</button>
    <header className="forum-events-v341__detail-head"><div><span className="forum-eyebrow">{lifecycleLabels[item.lifecycleStatus]}</span><h1>{item.name}</h1><p>{dateLabel(item.startsAt)} · {item.venue || item.city || "Lieu à confirmer"}</p></div><div className="forum-events-v341__head-actions"><span className="forum-events-v341__status">{item.visibility === "PUBLIC" ? "Public" : "Privé"}</span>{canManage ? <button form="event-workspace-form" className="forum-button forum-button--primary" disabled={busy}><Save size={15} /> {busy ? "Enregistrement…" : "Enregistrer"}</button> : null}</div></header>
    {failure ? <div className="forum-alert" role="alert">{apiFailure(failure)}</div> : null}{notice ? <p className="forum-events-v341__notice" role="status">{notice}</p> : null}
    <div className="forum-events-v341__detail-grid">
      <div>
        <EventFormCard id="event-workspace-form" title="Informations de l’événement" form={form} setForm={setForm} busy={busy || !canManage} validation={validation} onSubmit={onSave} submitLabel="Enregistrer" hideSubmit />
        <section className="forum-events-v341__linked"><h2>Ressources liées</h2><div><span><Users size={16} /> Staff</span><strong>{item.staffCount}</strong></div><div><span><Link2 size={16} /> Documents</span><strong>{item.documentCount}</strong></div><div><span><ImageIcon size={16} /> Album</span><strong>{item.albumId ? `#${item.albumId}` : "Aucun"}</strong></div><div><span><Layers3 size={16} /> Modules actifs</span><strong>{item.modules.length}</strong></div></section>
      </div>
      <aside>
        <section className="forum-events-v341__lifecycle"><h2>Cycle de vie</h2>{lifecycle.map(value => <div key={value} className={value === item.lifecycleStatus ? "is-current" : lifecycle.indexOf(value) < lifecycle.indexOf(item.lifecycleStatus) ? "is-done" : ""}><i /><span>{lifecycleLabels[value]}</span></div>)}{canManage && allowedTransitions[item.lifecycleStatus].length ? <div className="forum-events-v341__transition-actions">{allowedTransitions[item.lifecycleStatus].map(value => <button key={value} disabled={busy} className={value === "PUBLISHED" || value === "SYNCED_TO_APP" ? "forum-button forum-button--primary" : "forum-button forum-button--ghost"} onClick={() => void onTransition(value)}>{value === "SYNCED_TO_APP" ? "Publier dans l’app TORÈ" : `→ ${lifecycleLabels[value]}`}</button>)}</div> : null}</section>
        <section className="forum-events-v341__summary"><h2>Résumé</h2><div><span>Prix d’entrée</span><strong>{money(item.entryPriceCents)}</strong></div><div><span>Publication</span><strong>{item.publicationStatus === "PUBLISHED" ? "Publiée" : "Brouillon"}</strong></div><div><span>App TORÈ</span><strong>{item.appSyncStatus === "SYNCED" ? "Synchronisé" : "À synchroniser"}</strong></div>{item.coverUrl ? <a href={item.coverUrl} target="_blank" rel="noreferrer">Voir la couverture <ExternalLink size={13} /></a> : null}</section>
      </aside>
    </div>
  </div>;
}

function EventFormCard({ id, title, form, setForm, busy, validation, onSubmit, submitLabel, hideSubmit = false }: { id?: string; title: string; form: EventForm; setForm: (form: EventForm) => void; busy: boolean; validation: string; onSubmit: (event: FormEvent) => void; submitLabel: string; hideSubmit?: boolean }) {
  const update = <K extends keyof EventForm>(key: K, value: EventForm[K]) => setForm({ ...form, [key]: value });
  const toggleModule = (name: string) => update("modules", form.modules.includes(name) ? form.modules.filter(value => value !== name) : [...form.modules, name]);
  return <section className="forum-events-v341__editor"><div className="forum-events-v341__section-title"><CalendarDays size={18} /><div><span className="forum-eyebrow">Serveur TORÈ</span><h2>{title}</h2></div></div><form id={id} onSubmit={onSubmit}><fieldset disabled={busy}><div className="forum-events-v341__fields"><label className="is-wide">Nom<input required value={form.name} maxLength={180} onChange={event => update("name", event.target.value)} /></label><label>Début<input required type="datetime-local" value={form.startsAt} onChange={event => update("startsAt", event.target.value)} /></label><label>Fin<input required type="datetime-local" value={form.endsAt} onChange={event => update("endsAt", event.target.value)} /></label><label>Lieu<input value={form.venue} maxLength={255} onChange={event => update("venue", event.target.value)} /></label><label>Ville<input value={form.city} maxLength={120} onChange={event => update("city", event.target.value)} /></label><label>Capacité<input type="number" min="1" value={form.capacity} onChange={event => update("capacity", event.target.value)} /></label><label>Prix d’entrée (€)<input type="number" min="0" step="0.01" value={form.price} onChange={event => update("price", event.target.value)} /></label><label className="is-wide">Couverture (URL)<input type="url" value={form.coverUrl} onChange={event => update("coverUrl", event.target.value)} placeholder="https://…" /></label><label className="is-wide">Description<textarea value={form.description} maxLength={10000} onChange={event => update("description", event.target.value)} /></label><label className="is-wide">Co-organisateurs<input value={form.coOrganizers} onChange={event => update("coOrganizers", event.target.value)} placeholder="Cercle A, Comité B" /><small>Séparés par des virgules. Le rattachement formel multi-structure reste à implémenter.</small></label><label>Visibilité<select value={form.visibility} onChange={event => update("visibility", event.target.value as EventForm["visibility"])}><option value="PRIVATE">Privé</option><option value="PUBLIC">Public</option></select></label></div><div className="forum-events-v341__modules"><strong>Modules de l’event</strong><div>{moduleOptions.map(name => <label key={name}><input type="checkbox" checked={form.modules.includes(name)} onChange={() => toggleModule(name)} />{moduleLabels[name]}</label>)}</div></div><label className="forum-events-v341__recap">Récap post-event<textarea value={form.recap} maxLength={20000} onChange={event => update("recap", event.target.value)} placeholder="Résumé, faits marquants, informations à conserver…" /></label>{validation ? <p className="forum-events-v341__validation" role="alert">{validation}</p> : null}{!hideSubmit ? <button className="forum-button forum-button--primary" type="submit">{busy ? "Enregistrement…" : submitLabel}</button> : null}</fieldset></form></section>;
}
