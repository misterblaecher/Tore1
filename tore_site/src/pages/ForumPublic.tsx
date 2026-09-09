import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CalendarDays, ExternalLink, Images, MapPin, Users } from "lucide-react";
import ForumPage from "./Forum";
import { apiFetch, ApiError } from "@/lib/api";
import "@/styles/forum.css";

type EventItem = { id: number; name: string; startsAt?: string | null; endsAt?: string | null; venue?: string | null; city?: string | null; description?: string | null };
type PublicPage = { id: number; title: string; slug: string; category: string; content?: string; publishedAt?: string | null };
type Album = { id: number; title: string; description?: string | null; coverUrl?: string | null; media?: { id: number; url: string; caption?: string | null }[] };
type PublicPayload = {
  structure: { name: string; slug: string; type: string; description?: string | null; city?: string | null; address?: string | null; contactEmail?: string | null; contactPhone?: string | null; websiteUrl?: string | null; instagramHandle?: string | null; logoUrl?: string | null; bannerUrl?: string | null; primaryColor?: string | null; secondaryColor?: string | null; history?: string | null; sponsors?: string[] };
  visibility: Record<string, string>;
  events: EventItem[];
  members: { id: number; displayName: string; avatarUrl?: string | null; role: string }[];
  albums: Album[];
  pages: PublicPage[];
  stats: { members: number; publicEvents: number; publicAlbums: number } | null;
};

function formatDate(value?: string | null) {
  if (!value) return "Date à confirmer";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function ForumPublicPage() {
  const { slug } = useParams();
  if (!slug) return <ForumPage />;
  return <PublicStructure slug={slug} />;
}

function PublicStructure({ slug }: { slug: string }) {
  const [data, setData] = useState<PublicPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void apiFetch<PublicPayload>(`/forum/structures/${encodeURIComponent(slug)}`)
      .then((payload) => { if (active) setData(payload); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError ? reason.message : "Cette page publique est indisponible."); });
    return () => { active = false; };
  }, [slug]);

  if (error) {
    return <div className="min-h-screen bg-background"><main className="forum-page"><div className="forum-container"><div className="forum-alert">{error}</div><Link className="forum-button forum-button--ghost" to="/forum/structures"><ArrowLeft size={16} /> Retour aux structures</Link></div></main></div>;
  }
  if (!data) return <div className="min-h-screen bg-background"><main className="forum-page"><div className="forum-container"><div className="forum-empty">Chargement de la page officielle…</div></div></main></div>;

  const { structure, events, members, albums, pages, stats } = data;
  return (
    <div className="min-h-screen bg-background">

      <main className="forum-page" style={{ "--structure-primary": structure.primaryColor ?? "#ba1733", "--structure-secondary": structure.secondaryColor ?? "#f4c430" } as CSSProperties}>
        <div className="forum-container">
        <Link className="forum-back-link" to="/forum/structures"><ArrowLeft size={15} /> Toutes les structures</Link>
        <section className="forum-public-hero" style={{ backgroundImage: structure.bannerUrl ? `linear-gradient(90deg, rgba(8,8,9,.95) 0%, rgba(8,8,9,.65) 55%, rgba(8,8,9,.35) 100%), url(${structure.bannerUrl})` : undefined }}>
          <div className="forum-public-hero__identity">
            <div className="forum-public-logo" style={{ backgroundImage: structure.logoUrl ? `url(${structure.logoUrl})` : undefined }}>{!structure.logoUrl ? structure.name.slice(0, 1).toUpperCase() : null}</div>
            <div><span className="forum-eyebrow">Page officielle TORÈ · {structure.type}</span><h1>{structure.name}</h1><p>{structure.description || "Structure officielle de la communauté TORÈ."}</p>{structure.city ? <span className="forum-location"><MapPin size={14} /> {structure.city}{structure.address ? ` · ${structure.address}` : ""}</span> : null}</div>
          </div>
          <div className="forum-public-hero__actions"><Link className="forum-button forum-button--primary" to={`/forum/structures/${structure.slug}/dashboard`}>Espace membre <ArrowRight size={16} /></Link></div>
        </section>

        <div className="forum-public-stats"><div><strong>{stats?.publicEvents ?? "Privé"}</strong><span>events publics</span></div><div><strong>{stats?.members ?? "Privé"}</strong><span>membres visibles selon réglages</span></div><div><strong>{stats?.publicAlbums ?? "Privé"}</strong><span>albums publiés</span></div></div>

        <section className="forum-public-grid">
          <div className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Agenda</span><h2>Prochains événements</h2></div><CalendarDays size={20} /></div><div className="forum-list">{events.length ? events.map((event) => <article className="forum-row" key={event.id}><div><strong>{event.name}</strong><p>{formatDate(event.startsAt)}{event.venue || event.city ? ` · ${event.venue || event.city}` : ""}</p>{event.description ? <small>{event.description}</small> : null}</div><ArrowRight size={16} /></article>) : <div className="forum-empty">Aucun événement public annoncé.</div>}</div></div>
          <div className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Contact</span><h2>Liens utiles</h2></div><ExternalLink size={20} /></div><div className="forum-public-links">{structure.websiteUrl ? <a href={structure.websiteUrl} target="_blank" rel="noreferrer">Site web <ExternalLink size={14} /></a> : null}{structure.instagramHandle ? <a href={`https://instagram.com/${structure.instagramHandle.replace(/^@/, "")}`} target="_blank" rel="noreferrer">Instagram <ExternalLink size={14} /></a> : null}{structure.contactEmail ? <a href={`mailto:${structure.contactEmail}`}>Email <ExternalLink size={14} /></a> : null}{structure.contactPhone ? <a href={`tel:${structure.contactPhone}`}>Téléphone <ExternalLink size={14} /></a> : null}{!structure.websiteUrl && !structure.instagramHandle && !structure.contactEmail && !structure.contactPhone ? <span className="forum-muted">Cette structure n’a pas encore renseigné de lien public.</span> : null}</div></div>
        </section>

        {structure.history ? <section className="forum-card forum-public-copy"><span className="forum-eyebrow">Histoire</span><h2>Une structure, une mémoire</h2><p>{structure.history}</p></section> : null}
        {members.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Collectif</span><h2>Membres visibles</h2></div><Users size={20} /></div><div className="forum-members-grid">{members.map((member) => <div className="forum-member" key={member.id}><div className="forum-avatar" style={{ backgroundImage: member.avatarUrl ? `url(${member.avatarUrl})` : undefined }}>{!member.avatarUrl ? member.displayName.slice(0, 1).toUpperCase() : null}</div><div><strong>{member.displayName}</strong><span>{member.role}</span></div></div>)}</div></section> : null}
        {albums.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Souvenirs</span><h2>Albums publiés</h2></div><Images size={20} /></div><div className="forum-album-grid">{albums.map((album) => <article className="forum-album" key={album.id}>{album.coverUrl ? <img src={album.coverUrl} alt="" /> : <div className="forum-album__placeholder"><Images size={22} /></div>}<div><strong>{album.title}</strong>{album.description ? <p>{album.description}</p> : null}<small>{album.media?.length ?? 0} média{album.media?.length === 1 ? "" : "s"}</small></div></article>)}</div></section> : null}
        {pages.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Folklore</span><h2>Pages de mémoire</h2></div></div><div className="forum-list">{pages.map((page) => <article className="forum-public-copy forum-page-preview" key={page.id}><span className="forum-badge">{page.category}</span><h3>{page.title}</h3><p>{page.content}</p></article>)}</div></section> : null}
        {structure.sponsors?.length ? <section className="forum-card"><span className="forum-eyebrow">Partenaires</span><h2>Sponsors & partenaires</h2><div className="forum-hero-tags">{structure.sponsors.map((sponsor) => <span key={sponsor}>{sponsor}</span>)}</div></section> : null}
        </div>
      </main>

    </div>
  );
}
