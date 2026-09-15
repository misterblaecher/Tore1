import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  ExternalLink,
  Images,
  MapPin,
  Ticket,
  Users,
} from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import "@/styles/forum.css";

type StructureSummary = {
  id?: number | null;
  name: string;
  slug?: string | null;
  logoUrl?: string | null;
  type?: string | null;
};

type Album = {
  id: number;
  title: string;
  description?: string | null;
  coverUrl?: string | null;
  media?: { id: number; url: string; caption?: string | null }[];
};

type EditionLink = {
  id: number;
  title: string;
  slug: string;
  path: string;
  startsAt?: string | null;
};

type PublicRecap = {
  status: "RECAP_PUBLISHED";
  summary?: string | null;
  album?: Album | null;
  stats: { label: string; value: string }[];
  publishedAt?: string | null;
  previousEdition?: EditionLink | null;
  nextEdition?: EditionLink | null;
};

type PublicEvent = {
  id: number;
  slug: string;
  canonicalPath: string;
  title: string;
  coverUrl?: string | null;
  startsAt?: string | null;
  endsAt?: string | null;
  venue?: string | null;
  address?: string | null;
  city?: string | null;
  description?: string | null;
  organizer: StructureSummary;
  cohosts: StructureSummary[];
  structures: StructureSummary[];
  capacity?: number | null;
  entryPriceCents: number;
  currency: string;
  appCtaPath: string;
  appDeepLink: string;
  lifecycleStatus: string;
  recap?: PublicRecap | null;
};

function formatDate(value?: string | null) {
  if (!value) return "Date à confirmer";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "full", timeStyle: "short" }).format(new Date(value));
}

function formatPrice(cents: number, currency: string) {
  if (!cents) return "Gratuit";
  return new Intl.NumberFormat("fr-BE", { style: "currency", currency: currency || "EUR" }).format(cents / 100);
}

function structureLink(structure: StructureSummary) {
  return structure.slug ? `/forum/structures/${structure.slug}` : null;
}

export default function ForumEventPage() {
  const { slug = "" } = useParams();
  const [data, setData] = useState<PublicEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    void apiFetch<PublicEvent>(`/forum/events/${encodeURIComponent(slug)}`)
      .then((payload) => { if (active) setData(payload); })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof ApiError ? reason.message : "Cette page événement est indisponible.");
      });
    return () => { active = false; };
  }, [slug]);

  if (error) {
    return (
      <main className="forum-page">
        <div className="forum-container">
          <div className="forum-alert">{error}</div>
          <Link className="forum-button forum-button--ghost" to="/forum/structures">
            <ArrowLeft size={16} /> Retour aux structures
          </Link>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="forum-page">
        <div className="forum-container"><div className="forum-empty">Chargement de l’événement…</div></div>
      </main>
    );
  }

  const recap = data.recap?.status === "RECAP_PUBLISHED" ? data.recap : null;
  const organizerHref = structureLink(data.organizer);
  const location = [data.venue, data.address, data.city].filter(Boolean).join(" · ");

  return (
    <main className="forum-page">
      <div className="forum-container">
        <Link className="forum-back-link" to={organizerHref || "/forum/structures"}>
          <ArrowLeft size={15} /> {data.organizer.name}
        </Link>

        <section
          className="forum-public-hero"
          style={{
            backgroundImage: data.coverUrl
              ? `linear-gradient(90deg, rgba(8,8,9,.96) 0%, rgba(8,8,9,.7) 55%, rgba(8,8,9,.4) 100%), url(${data.coverUrl})`
              : undefined,
          }}
        >
          <div className="forum-public-hero__identity">
            <div>
              <span className="forum-eyebrow">
                {recap ? "Souvenir officiel TORÈ" : "Événement officiel TORÈ"}
              </span>
              <h1>{data.title}</h1>
              <p>{data.description || "Retrouvez les informations publiques de cet événement TORÈ."}</p>
              <div className="forum-hero-tags">
                <span><CalendarDays size={14} /> {formatDate(data.startsAt)}</span>
                {location ? <span><MapPin size={14} /> {location}</span> : null}
                <span><Ticket size={14} /> {formatPrice(data.entryPriceCents, data.currency)}</span>
                {data.capacity != null ? <span><Users size={14} /> {data.capacity} places</span> : null}
              </div>
            </div>
          </div>
          <div className="forum-public-hero__actions">
            <Link className="forum-button forum-button--primary" to={data.appCtaPath}>
              Continuer dans TORÈ <ArrowRight size={16} />
            </Link>
            <a className="forum-button forum-button--ghost" href={data.appDeepLink}>
              Ouvrir l’app <ExternalLink size={15} />
            </a>
          </div>
        </section>

        <section className="forum-public-grid">
          <article className="forum-card">
            <div className="forum-section-title">
              <div><span className="forum-eyebrow">Organisation</span><h2>Organisateurs</h2></div>
              <Users size={20} />
            </div>
            <div className="forum-list">
              {organizerHref ? (
                <Link className="forum-row" to={organizerHref}>
                  <div><strong>{data.organizer.name}</strong><p>Organisateur principal</p></div>
                  <ArrowRight size={16} />
                </Link>
              ) : (
                <div className="forum-row"><div><strong>{data.organizer.name}</strong><p>Organisateur principal</p></div></div>
              )}
              {data.cohosts.map((cohost) => {
                const href = structureLink(cohost);
                return href ? (
                  <Link className="forum-row" to={href} key={cohost.id ?? cohost.name}>
                    <div><strong>{cohost.name}</strong><p>Co-organisateur</p></div>
                    <ArrowRight size={16} />
                  </Link>
                ) : (
                  <div className="forum-row" key={cohost.id ?? cohost.name}>
                    <div><strong>{cohost.name}</strong><p>Co-organisateur</p></div>
                  </div>
                );
              })}
            </div>
          </article>

          <article className="forum-card">
            <div className="forum-section-title">
              <div><span className="forum-eyebrow">Infos pratiques</span><h2>Dates & lieu</h2></div>
              <MapPin size={20} />
            </div>
            <div className="forum-list">
              <div className="forum-row"><div><strong>Début</strong><p>{formatDate(data.startsAt)}</p></div></div>
              <div className="forum-row"><div><strong>Fin</strong><p>{formatDate(data.endsAt)}</p></div></div>
              {location ? <div className="forum-row"><div><strong>Lieu</strong><p>{location}</p></div></div> : null}
              <div className="forum-row"><div><strong>Prix</strong><p>{formatPrice(data.entryPriceCents, data.currency)}</p></div></div>
            </div>
          </article>
        </section>

        {recap ? (
          <section className="forum-card forum-public-copy" data-testid="event-recap">
            <span className="forum-eyebrow">Après l’événement</span>
            <h2>Le recap</h2>
            {recap.summary ? <p>{recap.summary}</p> : <p className="forum-muted">Le résumé public sera complété par l’organisation.</p>}

            {recap.stats.length ? (
              <div className="forum-public-stats">
                {recap.stats.map((stat) => (
                  <div key={`${stat.label}-${stat.value}`}><strong>{stat.value}</strong><span>{stat.label}</span></div>
                ))}
              </div>
            ) : null}

            {recap.album ? (
              <div>
                <div className="forum-section-title">
                  <div><span className="forum-eyebrow">Album publié</span><h3>{recap.album.title}</h3></div>
                  <Images size={20} />
                </div>
                <div className="forum-album-grid">
                  {(recap.album.media ?? []).map((media) => (
                    <figure className="forum-album" key={media.id}>
                      <img src={media.url} alt={media.caption || `Photo de ${data.title}`} />
                      {media.caption ? <figcaption>{media.caption}</figcaption> : null}
                    </figure>
                  ))}
                </div>
              </div>
            ) : null}

            {recap.previousEdition || recap.nextEdition ? (
              <div className="forum-public-grid">
                {recap.previousEdition ? (
                  <Link className="forum-card" to={recap.previousEdition.path}>
                    <span className="forum-eyebrow">Édition précédente</span>
                    <strong>{recap.previousEdition.title}</strong>
                  </Link>
                ) : <div />}
                {recap.nextEdition ? (
                  <Link className="forum-card" to={recap.nextEdition.path}>
                    <span className="forum-eyebrow">Édition suivante</span>
                    <strong>{recap.nextEdition.title}</strong>
                  </Link>
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </main>
  );
}
