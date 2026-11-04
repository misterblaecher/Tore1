import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, CalendarDays, Download, ExternalLink, FileText, Images, MapPin, Users } from "lucide-react";
import ForumPage from "./Forum";
import { apiFetch, ApiError } from "@/lib/api";
import { resolveStructureBranding } from "@/lib/structure-branding";
import { StructureClaimAction } from "@/components/forum/StructureClaimAction";
import "@/styles/forum.css";
import "@/styles/structure-branding.css";

type EventItem = { id: number; name: string; startsAt?: string | null; endsAt?: string | null; venue?: string | null; city?: string | null; description?: string | null };
type PublicPage = { id: number; title: string; slug: string; category: string; content?: string; publishedAt?: string | null };
type Album = { id: number; title: string; description?: string | null; coverUrl?: string | null; media?: { id: number; url: string; caption?: string | null }[] };
type PublicDocument = { id: number; title: string; description?: string | null; folder?: string | null; fileUrl: string; previewUrl?: string | null; type?: string | null; createdAt?: string | null };
type PublicPayload = {
  structure: { id?: number; name: string; slug: string; type: string; description?: string | null; city?: string | null; address?: string | null; contactEmail?: string | null; contactPhone?: string | null; websiteUrl?: string | null; instagramHandle?: string | null; logoUrl?: string | null; bannerUrl?: string | null; primaryColor?: string | null; secondaryColor?: string | null; history?: string | null; sponsors?: string[]; portal?: { hidden_blocks?: string[] } };
  visibility: Record<string, string>;
  events: EventItem[];
  members: { id: number; displayName: string; avatarUrl?: string | null; role: string }[];
  albums: Album[];
  pages: PublicPage[];
  documents?: PublicDocument[];
  stats: { operational: { members: number; publicEvents: number; publicAlbums: number }; finance: null } | null;
};

function formatDate(value?: string | null) {
  if (!value) return "Date à confirmer";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function safeHttpUrl(value?: string | null) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch { return null; }
}

function eventPath(event: EventItem) {
  const slug = event.name.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `/forum/events/${slug}-${event.id}`;
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
    let pending = false;
    const refresh = async () => {
      if (pending || document.visibilityState === "hidden") return;
      pending = true;
      try {
        const payload = await apiFetch<PublicPayload>(`/forum/structures/${encodeURIComponent(slug)}`);
        if (active) { setData(payload); setError(null); }
      } catch (reason: unknown) {
        if (active) {
          setError(reason instanceof ApiError ? reason.message : "Cette page publique est indisponible.");
          setData(null);
        }
      } finally { pending = false; }
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 30_000);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [slug]);

  if (error) {
    return <div className="min-h-screen bg-background"><main className="forum-page"><div className="forum-container"><div className="forum-alert">{error}</div><Link className="forum-button forum-button--ghost" to="/forum/structures"><ArrowLeft size={16} /> Retour aux structures</Link></div></main></div>;
  }
  if (!data) return <div className="min-h-screen bg-background"><main className="forum-page"><div className="forum-container"><div className="forum-empty">Chargement de la page officielle…</div></div></main></div>;

  const { structure, events, members, albums, pages, documents = [], stats } = data;
  const hidden = new Set(structure.portal?.hidden_blocks ?? []);
  const websiteUrl = safeHttpUrl(structure.websiteUrl);
  const branding = resolveStructureBranding(structure.primaryColor, structure.secondaryColor);
  const brandStyle = {
    "--structure-primary": branding.primary,
    "--structure-primary-text": branding.primaryText,
    "--structure-secondary": branding.secondary,
    "--structure-secondary-text": branding.secondaryText,
    "--structure-accent": branding.accent,
  } as CSSProperties;

  return (
    <div className="min-h-screen bg-background">
      <main className="forum-page forum-public-branded" style={brandStyle}>
        <div className="forum-container">
        <Link className="forum-back-link" to="/forum/structures"><ArrowLeft size={15} /> Toutes les structures</Link>
        <section className="forum-public-hero" style={{ backgroundImage: structure.bannerUrl ? `linear-gradient(90deg, rgba(8,8,9,.95) 0%, rgba(8,8,9,.65) 55%, rgba(8,8,9,.35) 100%), url(${structure.bannerUrl})` : undefined }}>
          <div className="forum-public-hero__identity">
            <div className="forum-public-logo" style={{ backgroundImage: structure.logoUrl ? `url(${structure.logoUrl})` : undefined }}>{!structure.logoUrl ? structure.name.slice(0, 1).toUpperCase() : null}</div>
            <div><span className="forum-eyebrow">Page officielle TORÈ · {structure.type}</span><h1>{structure.name}</h1><p>{structure.description || "Structure officielle de la communauté TORÈ."}</p>{structure.city ? <span className="forum-location"><MapPin size={14} /> {structure.city}{structure.address ? ` · ${structure.address}` : ""}</span> : null}</div>
          </div>
          <div className="forum-public-hero__actions"><Link className="forum-button forum-button--primary" style={{ background: branding.primary, borderColor: branding.primary, color: branding.primaryText }} to={`/forum/structures/${structure.slug}/dashboard`}>Espace membre <ArrowRight size={16} /></Link><StructureClaimAction structureId={structure.id} structureName={structure.name} /></div>
        </section>

        <div className="forum-public-stats"><div><strong>{stats?.operational.publicEvents ?? "Privé"}</strong><span>events publics</span></div><div><strong>{stats?.operational.members ?? "Privé"}</strong><span>membres visibles selon réglages</span></div><div><strong>{stats?.operational.publicAlbums ?? "Privé"}</strong><span>albums publiés</span></div></div>

        <section className="forum-public-grid">
          <div className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Agenda</span><h2>Prochains événements</h2></div><CalendarDays size={20} /></div><div className="forum-list">{data.visibility.events === "PUBLIC" && events.length ? events.map((event) => <Link className="forum-row" key={event.id} to={eventPath(event)}><div><strong>{event.name}</strong><p>{formatDate(event.startsAt)}{event.venue || event.city ? ` · ${event.venue || event.city}` : ""}</p>{event.description ? <small>{event.description}</small> : null}</div><ArrowRight size={16} /></Link>) : <div className="forum-empty">Aucun événement public annoncé.</div>}</div></div>
          <div className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Contact</span><h2>Liens utiles</h2></div><ExternalLink size={20} /></div><div className="forum-public-links">{websiteUrl ? <a href={websiteUrl} target="_blank" rel="noreferrer">Site web <ExternalLink size={14} /></a> : null}{structure.instagramHandle ? <a href={`https://instagram.com/${structure.instagramHandle.replace(/^@/, "")}`} target="_blank" rel="noreferrer">Instagram <ExternalLink size={14} /></a> : null}{structure.contactEmail ? <a href={`mailto:${structure.contactEmail}`}>Email <ExternalLink size={14} /></a> : null}{structure.contactPhone ? <a href={`tel:${structure.contactPhone}`}>Téléphone <ExternalLink size={14} /></a> : null}{!websiteUrl && !structure.instagramHandle && !structure.contactEmail && !structure.contactPhone ? <span className="forum-muted">Cette structure n’a pas encore renseigné de lien public.</span> : null}</div></div>
        </section>

        {structure.history ? <section className="forum-card forum-public-copy"><span className="forum-eyebrow">Histoire</span><h2>Une structure, une mémoire</h2><p>{structure.history}</p></section> : null}
        {members.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Collectif</span><h2>Membres visibles</h2></div><Users size={20} /></div><div className="forum-members-grid">{members.map((member) => <div className="forum-member" key={member.id}><div className="forum-avatar" style={{ backgroundImage: member.avatarUrl ? `url(${member.avatarUrl})` : undefined }}>{!member.avatarUrl ? member.displayName.slice(0, 1).toUpperCase() : null}</div><div><strong>{member.displayName}</strong><span>{member.role}</span></div></div>)}</div></section> : null}
        {albums.length && !hidden.has("gallery") ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Souvenirs</span><h2>Albums publiés</h2></div><Images size={20} /></div><div className="forum-album-grid">{albums.map((album) => <article className="forum-album" key={album.id}>{album.coverUrl ? <img src={album.coverUrl} alt="" /> : <div className="forum-album__placeholder"><Images size={22} /></div>}<div><strong>{album.title}</strong>{album.description ? <p>{album.description}</p> : null}<small>{album.media?.length ?? 0} média{album.media?.length === 1 ? "" : "s"}</small></div></article>)}</div></section> : null}
        {documents.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Ressources publiques</span><h2>Documents</h2></div><FileText size={20} /></div><div className="forum-list">{documents.map((document) => <article className="forum-row" key={document.id}><div><strong>{document.title}</strong><p>{document.folder || "Document public"} · {(document.type || "fichier").toUpperCase()}{document.createdAt ? ` · ${formatDate(document.createdAt)}` : ""}</p>{document.description ? <small>{document.description}</small> : null}</div><a className="forum-button forum-button--ghost" href={document.fileUrl} target="_blank" rel="noreferrer" download><Download size={14} /> Télécharger</a></article>)}</div></section> : null}
        {pages.length ? <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Folklore</span><h2>Pages de mémoire</h2></div></div><div className="forum-list">{pages.map((page) => <article className="forum-public-copy forum-page-preview" key={page.id}><span className="forum-badge">{page.category}</span><h3>{page.title}</h3><p>{page.content}</p></article>)}</div></section> : null}
        {structure.sponsors?.length ? <section className="forum-card"><span className="forum-eyebrow">Partenaires</span><h2>Sponsors & partenaires</h2><div className="forum-hero-tags">{structure.sponsors.map((sponsor) => <span key={sponsor}>{sponsor}</span>)}</div></section> : null}
        </div>
      </main>
    </div>
  );
}
