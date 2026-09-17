import { useEffect, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Building2, CalendarDays, ChevronLeft, ChevronRight, MapPin, RotateCcw, Search, ShieldCheck, Users } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import "@/styles/forum.css";
import "@/styles/forum-directory.css";

type PublicEvent = {
  id: number;
  name: string;
  startsAt: string;
  endsAt?: string | null;
  venue?: string | null;
  city?: string | null;
};

type Structure = {
  id: number;
  slug: string;
  name: string;
  type: string;
  description?: string | null;
  city?: string | null;
  logoUrl?: string | null;
  bannerUrl?: string | null;
  primaryColor?: string | null;
  secondaryColor?: string | null;
  memberCount?: number | null;
  nextPublicEvent?: PublicEvent | null;
};

type StructuresResponse = {
  items: Structure[];
  page?: number;
  pageSize?: number;
  total?: number;
  totalPages?: number;
};

type DirectoryMeta = { page: number; pageSize: number; total: number; totalPages: number };

const PAGE_SIZE = 12;

const typeLabels: Record<string, string> = {
  COMMITTEE: "Comité",
  CIRCLE: "Cercle",
  ORDER: "Ordre",
  BAR: "Bar partenaire",
  ASSOCIATION: "Association",
  PARTNER: "Structure partenaire",
  OTHER: "Autre structure",
};

const quickTypes = [
  ["COMMITTEE", "Comité"],
  ["CIRCLE", "Cercle"],
  ["ORDER", "Ordre"],
  ["ASSOCIATION", "Association"],
  ["BAR", "Bar"],
  ["PARTNER", "Partenaire"],
] as const;

function formatEventDate(value: string) {
  return new Intl.DateTimeFormat("fr-BE", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function visualStyle(structure: Structure): CSSProperties {
  return {
    "--structure-primary": structure.primaryColor || "#ba1733",
    "--structure-secondary": structure.secondaryColor || "#f4c430",
    backgroundImage: structure.bannerUrl
      ? `linear-gradient(135deg, rgba(8,8,9,.28), rgba(8,8,9,.72)), url(${structure.bannerUrl})`
      : undefined,
  } as CSSProperties;
}

export default function ForumPage() {
  const navigate = useNavigate();
  const [structures, setStructures] = useState<Structure[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const typeFilter = searchParams.get("type") ?? "";
  const cityFilter = searchParams.get("city") ?? "";
  const page = Math.max(1, Number.parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const [meta, setMeta] = useState<DirectoryMeta>({ page, pageSize: PAGE_SIZE, total: 0, totalPages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryNonce, setRetryNonce] = useState(0);
  const createOpen = searchParams.get("creer") === "1";
  const hasFilters = Boolean(query.trim() || typeFilter || cityFilter.trim());

  function setFilter(key: "q" | "type" | "city", value: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      const normalized = value.trim();
      if (normalized) next.set(key, normalized);
      else next.delete(key);
      next.delete("page");
      return next;
    }, { replace: true });
  }

  function setPage(nextPage: number) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (nextPage <= 1) next.delete("page");
      else next.set("page", String(nextPage));
      return next;
    });
  }

  function resetFilters() {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("q");
      next.delete("type");
      next.delete("city");
      next.delete("page");
      return next;
    }, { replace: true });
  }

  function toggleCreation() {
    if (!getToken()) { navigate("/forum/login", { state: { from: "/forum/structures?creer=1#create-structure" } }); return; }
    setSearchParams((current) => { const next = new URLSearchParams(current); if (createOpen) next.delete("creer"); else next.set("creer", "1"); return next; });
    setCreateError(null);
  }

  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newStructure, setNewStructure] = useState({ name: "", type: "COMMITTEE", city: "", description: "" });
  const accountHref = getToken() ? "/compte" : "/forum/login";

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (typeFilter) params.set("type", typeFilter);
    if (cityFilter.trim()) params.set("city", cityFilter.trim());
    params.set("page", String(page));
    params.set("page_size", String(PAGE_SIZE));

    setLoading(true);
    setError(null);
    setStructures([]);
    void apiFetch<StructuresResponse>(`/forum/structures?${params.toString()}`)
      .then((data) => {
        if (!active) return;
        const items = data.items ?? [];
        setStructures(items);
        setMeta({
          page: data.page ?? page,
          pageSize: data.pageSize ?? PAGE_SIZE,
          total: data.total ?? items.length,
          totalPages: data.totalPages ?? (items.length ? 1 : 0),
        });
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? reason.message : "Impossible de charger les structures.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [query, typeFilter, cityFilter, page, retryNonce]);

  async function createStructure(event: FormEvent) {
    event.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const created = await apiFetch<{ orga: { slug: string } }>("/orgas", {
        method: "POST",
        headers: { "Idempotency-Key": `forum-orga-${Date.now()}-${Math.random().toString(36).slice(2, 8)}` },
        body: JSON.stringify({ name: newStructure.name, org_type: newStructure.type, city: newStructure.city, description: newStructure.description, visibility: "PUBLIC", join_mode: "REQUEST_TO_JOIN" }),
      });
      navigate(`/forum/structures/${encodeURIComponent(created.orga.slug)}/dashboard`);
    } catch (reason: unknown) {
      setCreateError(reason instanceof ApiError ? reason.message : "Impossible de créer la structure.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <main className="forum-page">
        <div className="forum-container">
          <header className="forum-landing-head">
            <div>
              <span className="forum-eyebrow">TORÈ / Forum</span>
              <h1>Les structures qui font vivre la guindaille.</h1>
              <p>Une page officielle, un espace de travail et une mémoire partagée pour chaque structure TORÈ.</p>
            </div>
            <Link className="forum-button forum-button--ghost" to={accountHref}>Mon compte <ArrowRight size={16} /></Link>
          </header>

          <section className="forum-intro-grid">
            <div className="forum-panel forum-panel--hero">
              <div className="forum-panel-kicker"><ShieldCheck size={16} /> Espaces officiels</div>
              <h2>Le Forum sert à faire vivre la structure.</h2>
              <p>Retrouvez les informations publiques, les membres, les événements et l’espace interne — avec une visibilité maîtrisée par le bureau.</p>
              <div className="forum-hero-tags"><span>Public</span><span>Privé</span><span>Traçable</span></div>
            </div>
            <div className="forum-panel forum-principles">
              <div><Building2 size={20} /><strong>Une identité</strong><span>Page publique personnalisée</span></div>
              <div><Users size={20} /><strong>Un collectif</strong><span>Membres et mandats actifs</span></div>
              <div><ShieldCheck size={20} /><strong>Un cadre</strong><span>Permissions et visibilité backend</span></div>
            </div>
          </section>

          <section className="forum-create-panel" id="create-structure">
            <div className="forum-section-head forum-create-panel__head"><div><span className="forum-eyebrow">Nouveau projet</span><h2>Créer une structure TORÈ</h2></div><button className="forum-button forum-button--primary" type="button" onClick={toggleCreation}>{createOpen && getToken() ? "Fermer" : "Commencer"}</button></div>
            {createOpen && getToken() ? <form className="forum-panel forum-form forum-create-form" onSubmit={createStructure}><p>Créez votre structure pour ouvrir son tableau de bord. Vous pourrez ensuite configurer sa page publique.</p>{createError ? <div className="forum-alert">{createError}</div> : null}<label>Nom de la structure<input required value={newStructure.name} onChange={(event) => setNewStructure({ ...newStructure, name: event.target.value })} placeholder="Comité, cercle, ordre…" /></label><div className="forum-create-form__grid"><label>Type<select value={newStructure.type} onChange={(event) => setNewStructure({ ...newStructure, type: event.target.value })}><option value="COMMITTEE">Comité</option><option value="CIRCLE">Cercle</option><option value="ORDER">Ordre</option><option value="ASSOCIATION">Association</option><option value="BAR">Bar partenaire</option><option value="PARTNER">Partenaire</option><option value="OTHER">Autre</option></select></label><label>Ville<input value={newStructure.city} onChange={(event) => setNewStructure({ ...newStructure, city: event.target.value })} placeholder="Liège" /></label></div><label>Description<textarea value={newStructure.description} onChange={(event) => setNewStructure({ ...newStructure, description: event.target.value })} placeholder="Présentez la structure et sa place dans la communauté." /></label><button className="forum-button forum-button--primary" type="submit" disabled={creating}>{creating ? "Création…" : "Créer la structure"}</button></form> : null}
          </section>

          <section className="forum-directory" aria-labelledby="structure-directory-title">
            <div className="forum-section-head forum-directory__head">
              <div><span className="forum-eyebrow">Structures publiques</span><h2 id="structure-directory-title">Explorer les espaces</h2></div>
              {!loading && !error ? <span className="forum-directory__count">{meta.total} structure{meta.total === 1 ? "" : "s"}</span> : null}
            </div>

            <div className="forum-directory-filters">
              <label className="forum-directory-field">
                <span>Nom</span>
                <div className="forum-search"><Search size={17} /><input aria-label="Nom de la structure" value={query} onChange={(event) => setFilter("q", event.target.value)} placeholder="Rechercher une structure" /></div>
              </label>
              <label className="forum-directory-field">
                <span>Ville</span>
                <div className="forum-search"><MapPin size={17} /><input aria-label="Ville" value={cityFilter} onChange={(event) => setFilter("city", event.target.value)} placeholder="Liège" /></div>
              </label>
              <label className="forum-directory-field forum-directory-field--type">
                <span>Type</span>
                <select aria-label="Type de structure" value={typeFilter} onChange={(event) => setFilter("type", event.target.value)}>
                  <option value="">Tous les types</option>
                  <option value="COMMITTEE">Comité</option>
                  <option value="CIRCLE">Cercle</option>
                  <option value="ORDER">Ordre</option>
                  <option value="ASSOCIATION">Association</option>
                  <option value="BAR">Bar partenaire</option>
                  <option value="PARTNER">Partenaire</option>
                  <option value="OTHER">Autre</option>
                </select>
              </label>
              {hasFilters ? <button className="forum-button forum-button--ghost forum-directory-reset" type="button" onClick={resetFilters}><RotateCcw size={15} /> Réinitialiser</button> : null}
            </div>

            <div className="forum-directory-types" aria-label="Filtres rapides par type">
              {quickTypes.map(([value, label]) => <button key={value} type="button" className={`forum-directory-chip ${typeFilter === value ? "is-active" : ""}`} aria-pressed={typeFilter === value} onClick={() => setFilter("type", typeFilter === value ? "" : value)}>{label}</button>)}
            </div>

            <div className="forum-directory-results" aria-live="polite">
              {error ? <div className="forum-alert forum-directory-state"><strong>Le répertoire n’a pas pu être chargé.</strong><span>{error}</span><button className="forum-button forum-button--ghost" type="button" onClick={() => setRetryNonce((value) => value + 1)}>Réessayer</button></div> : null}

              {loading ? <div className="forum-structure-grid" aria-label="Chargement des structures">{Array.from({ length: 6 }, (_, index) => <div className="forum-structure-card forum-structure-card--skeleton" key={index}><div className="forum-directory-skeleton forum-directory-skeleton--visual" /><div className="forum-structure-card__body"><div className="forum-directory-skeleton forum-directory-skeleton--meta" /><div className="forum-directory-skeleton forum-directory-skeleton--title" /><div className="forum-directory-skeleton forum-directory-skeleton--text" /></div></div>)}</div> : null}

              {!loading && !error && structures.length === 0 ? <div className="forum-empty forum-directory-state"><strong>Aucune structure publique ne correspond à votre recherche.</strong>{hasFilters ? <button className="forum-button forum-button--ghost" type="button" onClick={resetFilters}>Effacer les filtres</button> : null}</div> : null}

              {!loading && !error && structures.length > 0 ? <div className="forum-structure-grid">
                {structures.map((structure) => (
                  <Link className="forum-structure-card forum-structure-card--directory" to={`/forum/structures/${structure.slug}`} key={structure.id}>
                    <div className="forum-structure-visual" style={visualStyle(structure)}>
                      <div className="forum-structure-logo">
                        {structure.logoUrl ? <img src={structure.logoUrl} alt={`Logo de ${structure.name}`} loading="lazy" /> : <Building2 size={26} aria-hidden="true" />}
                      </div>
                    </div>
                    <div className="forum-structure-card__body">
                      <div className="forum-card-meta"><span>{typeLabels[structure.type] ?? structure.type}</span>{structure.city ? <span>{structure.city}</span> : null}</div>
                      <h3>{structure.name}</h3>
                      <p>{structure.description || "La page officielle de cette structure TORÈ."}</p>
                      {structure.nextPublicEvent ? <div className="forum-next-event"><CalendarDays size={17} /><div><small>Prochain événement public</small><strong>{structure.nextPublicEvent.name}</strong><span>{formatEventDate(structure.nextPublicEvent.startsAt)}{structure.nextPublicEvent.venue || structure.nextPublicEvent.city ? ` · ${structure.nextPublicEvent.venue || structure.nextPublicEvent.city}` : ""}</span></div></div> : <div className="forum-next-event forum-next-event--empty"><CalendarDays size={17} /><span>Aucun événement public à venir</span></div>}
                      <div className="forum-card-footer"><span>{structure.memberCount == null ? "Collectif sur invitation" : `${structure.memberCount} membre${structure.memberCount === 1 ? "" : "s"}`}</span><ArrowRight size={17} /></div>
                    </div>
                  </Link>
                ))}
              </div> : null}
            </div>

            {!loading && !error && meta.totalPages > 1 ? <nav className="forum-directory-pagination" aria-label="Pagination des structures"><button className="forum-button forum-button--ghost" type="button" aria-label="Page précédente" disabled={meta.page <= 1} onClick={() => setPage(meta.page - 1)}><ChevronLeft size={16} /> Précédent</button><span>Page <strong>{meta.page}</strong> sur {meta.totalPages}</span><button className="forum-button forum-button--ghost" type="button" aria-label="Page suivante" disabled={meta.page >= meta.totalPages} onClick={() => setPage(meta.page + 1)}>Suivant <ChevronRight size={16} /></button></nav> : null}
          </section>
        </div>
      </main>
    </div>
  );
}
