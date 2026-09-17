import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Archive, CalendarDays, Clock3, FileText, Image, RotateCcw, Search, Users } from "lucide-react";
import { ApiError, apiFetch } from "@/lib/api";
import "@/styles/forum.css";
import "@/styles/forum-archives.css";

type ArchiveEvent = { id: number; name: string; startsAt?: string | null; endsAt?: string | null; venue?: string | null; city?: string | null };
type Mandate = { id: number; label: string; role: string; status: string; startsAt?: string | null; endsAt?: string | null; isAlumni: boolean; member?: { displayName?: string | null; avatarUrl?: string | null } | null };
type ArchiveItem = { key: string; category: string; objectId: number; title: string; subtitle?: string | null; archivedAt?: string | null; year?: number | null; event?: ArchiveEvent | null; mandate?: Mandate | null; target: string; restorePath?: string | null };
type ArchiveData = {
  structure: { id: number; slug: string; name: string };
  filters: { years: number[]; mandates: Mandate[]; events: { id: number; name: string; startsAt?: string | null }[]; categories: string[] };
  summary: { total: number; filtered: number; pastEvents: number; officeTerms: number };
  items: ArchiveItem[];
  officeHistory: Mandate[];
  pastEvents: ArchiveEvent[];
  links: { members: string; alumni: string };
};

type Filters = { search: string; year: string; mandate: string; eventId: string; category: string };
const initialFilters: Filters = { search: "", year: "", mandate: "", eventId: "", category: "" };
const categoryLabels: Record<string, string> = { DOCUMENT: "Documents", ALBUM: "Albums", PAGE: "Pages", DISCUSSION: "Discussions", EVENT: "Events passés" };

function headers() { return { "Idempotency-Key": `archives-${Date.now()}-${Math.random().toString(36).slice(2, 9)}` }; }
function dateLabel(value?: string | null) { return value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium" }).format(new Date(value)) : "Date inconnue"; }
function periodLabel(item: Mandate) { return `${dateLabel(item.startsAt)} → ${item.endsAt ? dateLabel(item.endsAt) : "aujourd’hui"}`; }
function categoryIcon(category: string) { if (category === "ALBUM") return <Image size={16} />; if (category === "EVENT") return <CalendarDays size={16} />; if (category === "DOCUMENT" || category === "PAGE") return <FileText size={16} />; return <Archive size={16} />; }

export default function ForumArchivesPage() {
  const { slug = "" } = useParams();
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [data, setData] = useState<ArchiveData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [restoring, setRestoring] = useState<string | null>(null);

  const load = useCallback(async (next = filters) => {
    setLoading(true); setError(null);
    const params = new URLSearchParams();
    if (next.search.trim()) params.set("search", next.search.trim());
    if (next.year) params.set("year", next.year);
    if (next.mandate) params.set("mandate", next.mandate);
    if (next.eventId) params.set("event_id", next.eventId);
    if (next.category) params.set("category", next.category);
    try { setData(await apiFetch<ArchiveData>(`/forum/structures/${encodeURIComponent(slug)}/archives/structured${params.size ? `?${params}` : ""}`)); }
    catch (reason) { setError(reason); }
    finally { setLoading(false); }
  }, [filters, slug]);

  useEffect(() => { void load(initialFilters); }, [slug]);

  const grouped = useMemo(() => {
    const groups = new Map<string, ArchiveItem[]>();
    for (const item of data?.items ?? []) {
      const key = item.year ? String(item.year) : "Sans date";
      groups.set(key, [...(groups.get(key) ?? []), item]);
    }
    return [...groups.entries()];
  }, [data?.items]);

  function submit(event: FormEvent) { event.preventDefault(); void load(filters); }
  function reset() { setFilters(initialFilters); void load(initialFilters); }
  async function restore(item: ArchiveItem) {
    if (!item.restorePath) return;
    setRestoring(item.key); setError(null);
    try { await apiFetch(item.restorePath, { method: "POST", headers: headers() }); await load(filters); }
    catch (reason) { setError(reason); }
    finally { setRestoring(null); }
  }

  return <main className="forum-main forum-archives" key={slug}>
    <header className="forum-archives__hero">
      <div><span className="forum-eyebrow">Mémoire patrimoniale</span><h1>Archives de {data?.structure.name || "la structure"}</h1><p>Une vue historique des objets réels de la structure : mandats, bureaux, events, pages, documents et albums. Aucune copie d’archive n’est créée.</p></div>
      <div className="forum-archives__seal"><Archive size={28} /><span>Patrimoine TORÈ</span></div>
    </header>

    {error ? <div className="forum-alert" role="alert">{error instanceof ApiError ? error.message : "Impossible de charger les archives."}</div> : null}

    <section className="forum-archives__metrics" aria-label="Résumé des archives">
      <Metric label="Éléments patrimoniaux" value={data?.summary.total ?? 0} />
      <Metric label="Résultats affichés" value={data?.summary.filtered ?? 0} />
      <Metric label="Events passés" value={data?.summary.pastEvents ?? 0} />
      <Metric label="Mandats de bureau" value={data?.summary.officeTerms ?? 0} />
    </section>

    <section className="forum-card forum-archives__filters">
      <div className="forum-section-title"><div><span className="forum-eyebrow">Explorer la mémoire</span><h2>Recherche et filtres</h2></div><Search size={20} /></div>
      <form onSubmit={submit} className="forum-archives__filter-grid">
        <label className="forum-archives__search">Recherche<input value={filters.search} onChange={(event) => setFilters((value) => ({ ...value, search: event.target.value }))} placeholder="Titre, event, mandat, catégorie…" /></label>
        <label>Année<select value={filters.year} onChange={(event) => setFilters((value) => ({ ...value, year: event.target.value }))}><option value="">Toutes</option>{data?.filters.years.map((year) => <option key={year} value={year}>{year}</option>)}</select></label>
        <label>Mandat<select value={filters.mandate} onChange={(event) => setFilters((value) => ({ ...value, mandate: event.target.value }))}><option value="">Tous</option>{data?.filters.mandates.map((item) => <option key={item.id} value={item.label}>{item.label}</option>)}</select></label>
        <label>Event<select value={filters.eventId} onChange={(event) => setFilters((value) => ({ ...value, eventId: event.target.value }))}><option value="">Tous</option>{data?.filters.events.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Catégorie<select value={filters.category} onChange={(event) => setFilters((value) => ({ ...value, category: event.target.value }))}><option value="">Toutes</option>{data?.filters.categories.map((item) => <option key={item} value={item}>{categoryLabels[item] || item}</option>)}</select></label>
        <div className="forum-inline forum-archives__filter-actions"><button className="forum-button forum-button--primary" type="submit">Filtrer</button><button className="forum-button forum-button--ghost" type="button" onClick={reset}>Réinitialiser</button></div>
      </form>
    </section>

    <div className="forum-archives__layout">
      <section className="forum-card forum-archives__timeline">
        <div className="forum-section-title"><div><span className="forum-eyebrow">Timeline</span><h2>Chronologie patrimoniale</h2></div><Clock3 size={20} /></div>
        {loading ? <div className="forum-empty">Chargement des archives…</div> : grouped.length ? grouped.map(([year, items]) => <div className="forum-archives__year" key={year}><h3>{year}</h3><div className="forum-archives__year-items">{items.map((item) => <article className="forum-archives__entry" key={item.key}><span className="forum-archives__entry-icon">{categoryIcon(item.category)}</span><div className="forum-archives__entry-main"><div className="forum-inline"><span className="forum-badge">{categoryLabels[item.category] || item.category}</span><time>{dateLabel(item.archivedAt)}</time></div><h4>{item.title}</h4>{item.subtitle ? <p>{item.subtitle}</p> : null}<div className="forum-archives__meta">{item.mandate ? <span>Mandat · {item.mandate.label}</span> : null}{item.event ? <span>Event · {item.event.name}</span> : null}</div><div className="forum-inline"><Link className="forum-button forum-button--ghost" to={item.target}>Ouvrir la source</Link>{item.restorePath ? <button className="forum-button forum-button--ghost" type="button" disabled={restoring === item.key} onClick={() => void restore(item)}><RotateCcw size={14} /> {restoring === item.key ? "Restauration…" : "Restaurer"}</button> : null}</div></div></article>)}</div></div>) : <div className="forum-empty">Aucun élément ne correspond à ces filtres.</div>}
      </section>

      <aside className="forum-archives__aside">
        <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Transmission</span><h2>Historique des bureaux</h2></div><Users size={20} /></div><div className="forum-list">{data?.officeHistory.length ? data.officeHistory.slice(0, 12).map((item) => <div className="forum-archives__mandate" key={item.id}><div><strong>{item.label}</strong><p>{item.member?.displayName || "Membre TORÈ"} · {item.role.replaceAll("_", " ")}</p><small>{periodLabel(item)}</small></div>{item.isAlumni ? <span className="forum-badge">Alumni</span> : <span className="forum-badge">Bureau</span>}</div>) : <div className="forum-empty">Aucun mandat de bureau historisé.</div>}</div><div className="forum-inline forum-archives__links">{data ? <><Link className="forum-button forum-button--ghost" to={data.links.members}>Voir les mandats</Link><Link className="forum-button forum-button--ghost" to={data.links.alumni}>Voir les alumni</Link></> : null}</div></section>
        <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Événementiel</span><h2>Events passés</h2></div><CalendarDays size={20} /></div><div className="forum-list">{data?.pastEvents.length ? data.pastEvents.slice(0, 8).map((event) => <Link className="forum-archives__past-event" to={`/forum/structures/${encodeURIComponent(slug)}/events/${event.id}`} key={event.id}><strong>{event.name}</strong><span>{dateLabel(event.startsAt)}{event.venue || event.city ? ` · ${event.venue || event.city}` : ""}</span></Link>) : <div className="forum-empty">Aucun event passé.</div>}</div></section>
      </aside>
    </div>
  </main>;
}

function Metric({ label, value }: { label: string; value: number }) { return <div className="forum-archives__metric"><span>{label}</span><strong>{value}</strong></div>; }
