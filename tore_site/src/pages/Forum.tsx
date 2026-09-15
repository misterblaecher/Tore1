import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, Building2, Search, ShieldCheck, Users } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import "@/styles/forum.css";

type Structure = {
  id: number;
  slug: string;
  name: string;
  type: string;
  description?: string | null;
  city?: string | null;
  logoUrl?: string | null;
  memberCount?: number;
};

type SimilarStructure = {
  id: number;
  slug: string;
  name: string;
  type: string;
  city?: string | null;
  score: number;
  likelyDuplicate: boolean;
};

type StructuresResponse = { items: Structure[] };
type SimilarStructuresResponse = { items: SimilarStructure[] };

const typeLabels: Record<string, string> = {
  COMMITTEE: "Comité",
  CIRCLE: "Cercle",
  ORDER: "Ordre",
  BAR: "Bar partenaire",
  ASSOCIATION: "Association",
  PARTNER: "Structure partenaire",
  OTHER: "Autre structure",
};

export default function ForumPage() {
  const navigate = useNavigate();
  const [structures, setStructures] = useState<Structure[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const setQuery = (value: string) =>
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set("q", value);
        else next.delete("q");
        return next;
      },
      { replace: true },
    );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const createOpen = searchParams.get("creer") === "1";

  function toggleCreation() {
    if (!getToken()) {
      navigate("/forum/login", {
        state: { from: "/forum/structures?creer=1#create-structure" },
      });
      return;
    }
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (createOpen) next.delete("creer");
      else next.set("creer", "1");
      return next;
    });
    setCreateError(null);
  }

  const [createError, setCreateError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newStructure, setNewStructure] = useState({
    name: "",
    type: "COMMITTEE",
    city: "",
    description: "",
  });
  const [similarStructures, setSimilarStructures] = useState<SimilarStructure[]>([]);
  const [checkingDuplicates, setCheckingDuplicates] = useState(false);
  const [duplicateOverride, setDuplicateOverride] = useState(false);
  const accountHref = getToken() ? "/compte" : "/forum/login";

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void apiFetch<StructuresResponse>(
      `/forum/structures${query.trim() ? `?q=${encodeURIComponent(query.trim())}` : ""}`,
    )
      .then((data) => {
        if (active) setStructures(data.items ?? []);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof ApiError
            ? reason.message
            : "Impossible de charger les structures.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query]);

  useEffect(() => {
    const name = newStructure.name.trim();
    if (!createOpen || !getToken() || name.length < 2) {
      setSimilarStructures([]);
      setCheckingDuplicates(false);
      setDuplicateOverride(false);
      return;
    }

    let active = true;
    setCheckingDuplicates(true);
    setDuplicateOverride(false);
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ name });
      if (newStructure.city.trim()) params.set("city", newStructure.city.trim());
      void apiFetch<SimilarStructuresResponse>(
        `/forum/structure-claims/similar-structures?${params.toString()}`,
      )
        .then((payload) => {
          if (active) setSimilarStructures(payload.items ?? []);
        })
        .catch(() => {
          if (active) setSimilarStructures([]);
        })
        .finally(() => {
          if (active) setCheckingDuplicates(false);
        });
    }, 350);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [createOpen, newStructure.name, newStructure.city]);

  async function createStructure(event: FormEvent) {
    event.preventDefault();
    setCreateError(null);

    const likelyDuplicates = similarStructures.filter(
      (structure) => structure.likelyDuplicate,
    );
    if (likelyDuplicates.length > 0 && !duplicateOverride) {
      setCreateError(
        "Une structure très similaire existe déjà. Ouvrez-la pour la revendiquer, ou confirmez explicitement qu’il s’agit bien d’une nouvelle structure.",
      );
      return;
    }

    setCreating(true);
    try {
      const created = await apiFetch<{ orga: { slug: string } }>("/orgas", {
        method: "POST",
        headers: {
          "Idempotency-Key": `forum-orga-${Date.now()}-${Math.random()
            .toString(36)
            .slice(2, 8)}`,
        },
        body: JSON.stringify({
          name: newStructure.name,
          org_type: newStructure.type,
          city: newStructure.city,
          description: newStructure.description,
          visibility: "PUBLIC",
          join_mode: "REQUEST_TO_JOIN",
        }),
      });
      navigate(
        `/forum/structures/${encodeURIComponent(created.orga.slug)}/dashboard`,
      );
    } catch (reason: unknown) {
      setCreateError(
        reason instanceof ApiError
          ? reason.message
          : "Impossible de créer la structure.",
      );
    } finally {
      setCreating(false);
    }
  }

  const likelyDuplicates = similarStructures.filter(
    (structure) => structure.likelyDuplicate,
  );

  return (
    <div className="min-h-screen bg-background">
      <main className="forum-page">
        <div className="forum-container">
          <header className="forum-landing-head">
            <div>
              <span className="forum-eyebrow">TORÈ / Forum</span>
              <h1>Les structures qui font vivre la guindaille.</h1>
              <p>
                Une page officielle, un espace de travail et une mémoire partagée
                pour chaque structure TORÈ.
              </p>
            </div>
            <Link className="forum-button forum-button--ghost" to={accountHref}>
              Mon compte <ArrowRight size={16} />
            </Link>
          </header>

          <section className="forum-intro-grid">
            <div className="forum-panel forum-panel--hero">
              <div className="forum-panel-kicker">
                <ShieldCheck size={16} /> Espaces officiels
              </div>
              <h2>Le Forum sert à faire vivre la structure.</h2>
              <p>
                Retrouvez les informations publiques, les membres, les événements
                et l’espace interne — avec une visibilité maîtrisée par le bureau.
              </p>
              <div className="forum-hero-tags">
                <span>Public</span>
                <span>Privé</span>
                <span>Traçable</span>
              </div>
            </div>
            <div className="forum-panel forum-principles">
              <div>
                <Building2 size={20} />
                <strong>Une identité</strong>
                <span>Page publique personnalisée</span>
              </div>
              <div>
                <Users size={20} />
                <strong>Un collectif</strong>
                <span>Membres et mandats actifs</span>
              </div>
              <div>
                <ShieldCheck size={20} />
                <strong>Un cadre</strong>
                <span>Permissions et visibilité backend</span>
              </div>
            </div>
          </section>

          <section className="forum-create-panel" id="create-structure">
            <div className="forum-section-head forum-create-panel__head">
              <div>
                <span className="forum-eyebrow">Nouveau projet</span>
                <h2>Créer une nouvelle structure TORÈ</h2>
              </div>
              <button
                className="forum-button forum-button--primary"
                type="button"
                onClick={toggleCreation}
              >
                {createOpen && getToken() ? "Fermer" : "Commencer"}
              </button>
            </div>
            {createOpen && getToken() ? (
              <form
                className="forum-panel forum-form forum-create-form"
                onSubmit={createStructure}
              >
                <p>
                  Cette action crée une nouvelle structure. Si la structure existe
                  déjà dans TORÈ, ouvrez sa page publique et utilisez
                  « Revendiquer cette structure ».
                </p>
                {createError ? (
                  <div className="forum-alert" role="alert">
                    {createError}
                  </div>
                ) : null}
                <label>
                  Nom de la nouvelle structure
                  <input
                    required
                    value={newStructure.name}
                    onChange={(event) =>
                      setNewStructure({
                        ...newStructure,
                        name: event.target.value,
                      })
                    }
                    placeholder="Comité, cercle, ordre…"
                  />
                </label>
                <div className="forum-create-form__grid">
                  <label>
                    Type
                    <select
                      value={newStructure.type}
                      onChange={(event) =>
                        setNewStructure({
                          ...newStructure,
                          type: event.target.value,
                        })
                      }
                    >
                      <option value="COMMITTEE">Comité</option>
                      <option value="CIRCLE">Cercle</option>
                      <option value="ORDER">Ordre</option>
                      <option value="BAR">Bar partenaire</option>
                      <option value="OTHER">Autre</option>
                    </select>
                  </label>
                  <label>
                    Ville
                    <input
                      value={newStructure.city}
                      onChange={(event) =>
                        setNewStructure({
                          ...newStructure,
                          city: event.target.value,
                        })
                      }
                      placeholder="Liège"
                    />
                  </label>
                </div>

                {checkingDuplicates ? (
                  <p className="forum-empty" role="status">
                    Recherche des structures similaires…
                  </p>
                ) : null}

                {!checkingDuplicates && similarStructures.length > 0 ? (
                  <div className="forum-alert forum-duplicate-check">
                    <strong>Structures ressemblantes déjà présentes</strong>
                    <p>
                      Vérifiez ces résultats avant de créer un doublon. Une
                      revendication est toujours séparée de la création.
                    </p>
                    <ul>
                      {similarStructures.map((structure) => (
                        <li key={structure.id}>
                          <Link
                            to={`/forum/structures/${encodeURIComponent(
                              structure.slug,
                            )}`}
                          >
                            {structure.name}
                            {structure.city ? ` · ${structure.city}` : ""}
                          </Link>
                          {structure.likelyDuplicate ? (
                            <span> — correspondance forte</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                    {likelyDuplicates.length > 0 && !duplicateOverride ? (
                      <button
                        className="forum-button forum-button--ghost"
                        type="button"
                        onClick={() => setDuplicateOverride(true)}
                      >
                        Confirmer qu’il s’agit d’une nouvelle structure distincte
                      </button>
                    ) : null}
                    {likelyDuplicates.length > 0 && duplicateOverride ? (
                      <p>Création distincte confirmée.</p>
                    ) : null}
                  </div>
                ) : null}

                <label>
                  Description
                  <textarea
                    value={newStructure.description}
                    onChange={(event) =>
                      setNewStructure({
                        ...newStructure,
                        description: event.target.value,
                      })
                    }
                    placeholder="Présentez la structure et sa place dans la communauté."
                  />
                </label>
                <button
                  className="forum-button forum-button--primary"
                  type="submit"
                  disabled={
                    creating ||
                    checkingDuplicates ||
                    (likelyDuplicates.length > 0 && !duplicateOverride)
                  }
                >
                  {creating ? "Création…" : "Créer la nouvelle structure"}
                </button>
              </form>
            ) : null}
          </section>

          <section className="forum-section-head">
            <div>
              <span className="forum-eyebrow">Structures publiques</span>
              <h2>Explorer les espaces</h2>
            </div>
            <label className="forum-search">
              <Search size={17} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Rechercher par nom ou ville"
              />
            </label>
          </section>

          {error ? <div className="forum-alert">{error}</div> : null}
          {loading ? (
            <div className="forum-empty">Chargement des structures…</div>
          ) : null}
          {!loading && structures.length === 0 ? (
            <div className="forum-empty">
              Aucune structure publique ne correspond à votre recherche.
            </div>
          ) : null}
          <div className="forum-structure-grid">
            {structures.map((structure) => (
              <Link
                className="forum-structure-card"
                to={`/forum/structures/${structure.slug}`}
                key={structure.id}
              >
                <div
                  className="forum-structure-mark"
                  style={{
                    backgroundImage: structure.logoUrl
                      ? `url(${structure.logoUrl})`
                      : undefined,
                  }}
                >
                  {!structure.logoUrl ? <Building2 size={24} /> : null}
                </div>
                <div className="forum-structure-card__body">
                  <div className="forum-card-meta">
                    <span>
                      {typeLabels[structure.type] ?? structure.type}
                    </span>
                    {structure.city ? <span>{structure.city}</span> : null}
                  </div>
                  <h3>{structure.name}</h3>
                  <p>
                    {structure.description ||
                      "La page officielle de cette structure TORÈ."}
                  </p>
                  <div className="forum-card-footer">
                    <span>
                      {structure.memberCount == null
                        ? "Collectif sur invitation"
                        : `${structure.memberCount} membre${
                            structure.memberCount === 1 ? "" : "s"
                          }`}
                    </span>
                    <ArrowRight size={17} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
