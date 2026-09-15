import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, BookOpen, Building2, CalendarDays, Clock3, Globe2, Handshake, Images, Info, Mail, MapPin, Megaphone, Phone, Smartphone, Sparkles, Users } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StructureClaimAction } from "@/components/forum/StructureClaimAction";
import { forumRoleLabels, structurePath } from "@/lib/forum-navigation";
import { portalVariant, publicImageUrl, publicWebUrl, type PortalAlbum, type PortalBlock, type PublicPortal } from "@/lib/structure-portal";
import "@/styles/structure-portal.css";

function dateLabel(value?: string | null) {
  if (!value || Number.isNaN(Date.parse(value))) return "Date à confirmer";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
function PortalImage({ src, name, className = "", fallback }: { src?: string | null; name: string; className?: string; fallback?: ReactNode }) {
  const [failed, setFailed] = useState(false);
  const url = publicImageUrl(src);
  useEffect(() => { setFailed(false); }, [src]);
  return <span className={`portal-image ${className}`}>{url && !failed ? <img src={url} alt={name} loading="lazy" onError={() => setFailed(true)} /> : fallback ?? <Images size={24} aria-label={name} />}</span>;
}
function Block({ id, title, icon, children, aside = false }: { id?: string; title: string; icon: ReactNode; children: ReactNode; aside?: boolean }) {
  return <section id={id} className={`portal-block${aside ? " portal-block--aside" : ""}`}><header className="portal-block__heading">{icon}<h2>{title}</h2></header>{children}</section>;
}
function Empty({ children }: { children: ReactNode }) { return <p className="portal-empty">{children}</p>; }

export default function ForumPublicPage() {
  const { slug = "" } = useParams();
  return <PublicStructure key={slug} slug={slug} />;
}
function PublicStructure({ slug }: { slug: string }) {
  const { hash } = useLocation();
  const [data, setData] = useState<PublicPortal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setError(null);
    void apiFetch<PublicPortal>(`/forum/structures/${encodeURIComponent(slug)}`)
      .then((payload) => { if (active) setData(payload); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof ApiError && reason.status === 404 ? "Cette structure n’est plus disponible." : "La page n’a pas pu être chargée."); });
    return () => { active = false; };
  }, [slug, retry]);
  // A bookmarked section may become available only after the public payload loads.
  useEffect(() => { if (data && hash) document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "auto" }); }, [data, hash]);

  if (error) return <main className="forum-page"><div className="forum-alert" role="alert">{error}</div><button className="forum-button forum-button--ghost" onClick={() => setRetry((value) => value + 1)}>Réessayer</button><Link className="forum-button forum-button--ghost" to="/forum/structures">Retour aux structures</Link></main>;
  if (!data) return <main className="forum-page"><p className="forum-empty" role="status">Chargement de la structure…</p></main>;

  const { structure, events, members, albums, pages, visibility } = data;
  const variant = portalVariant(structure.type);
  const portal = structure.portal ?? {};
  const hidden = portal.hidden_blocks ?? [];
  const isPublic = (key: string) => visibility?.[key] === "PUBLIC";
  const show = (block: PortalBlock) => !hidden.includes(block) && isPublic(({ about: "description", services: "description", team: "members", gallery: "albums", memory: "folklore", partners: "description", events: "events" })[block]);
  const contactVisible = isPublic("contact");
  const address = [structure.address, structure.city].filter(Boolean).join(", ");
  const maps = address ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}` : undefined;
  const website = publicWebUrl(structure.websiteUrl);
  const instagram = structure.instagramHandle ? `https://www.instagram.com/${encodeURIComponent(structure.instagramHandle.replace(/^@/, ""))}/` : undefined;
  const socials = Object.entries(structure.socialLinks ?? {}).map(([label, url]) => ({ label, url: publicWebUrl(url) })).filter((item) => item.url);
  const blocks: Partial<Record<PortalBlock, ReactNode>> = {
    about: <Block id="about" title="À propos" icon={<Info size={19} />}><p className="portal-copy">{portal.about || structure.description || "Cette structure n’a pas encore publié sa présentation."}</p></Block>,
    events: <Block id="events" title="Événements à venir" icon={<CalendarDays size={19} />}>{events.length ? <div className="portal-events">{events.map((event) => <Dialog key={event.id}><DialogTrigger asChild><button className="portal-event"><PortalImage src={event.bannerUrl} name="" fallback={<CalendarDays size={25} />} /><span><time>{dateLabel(event.startsAt)}</time><strong>{event.name}</strong><small>{event.venue || event.city || "Lieu à confirmer"}</small></span><ArrowUpRight size={16} /></button></DialogTrigger><DialogContent className="portal-dialog"><DialogTitle>{event.name}</DialogTitle><DialogDescription>{dateLabel(event.startsAt)} · {event.venue || event.city || "Lieu à confirmer"}</DialogDescription><p className="portal-copy">{event.description || "Retrouvez les informations et les actions de cette soirée dans TORÈ."}</p><a className="forum-button forum-button--primary" href={`tore://event/${event.id}`}><Smartphone size={16} /> Ouvrir la soirée dans TORÈ</a><Link className="portal-text-link" to="/rejoindre#beta">Installer l’application</Link></DialogContent></Dialog>)}</div> : <Empty>Aucun événement public annoncé pour le moment.</Empty>}</Block>,
    services: <Block id="services" title={structure.type === "ASSOCIATION" ? "Missions & activités" : "Activités & services"} icon={<Sparkles size={19} />}>{portal.services?.length ? <ul className="portal-services">{portal.services.map((service, index) => <li key={index}><Sparkles size={16} /><span>{service}</span></li>)}</ul> : <Empty>Les activités de la structure seront présentées ici.</Empty>}</Block>,
    team: <Block id="team" title={variant.team} icon={<Users size={19} />}>{members.length ? <div className="portal-team">{members.map((member) => <article key={member.id}><PortalImage src={member.avatarUrl} name={member.displayName} fallback={<span>{member.displayName.slice(0, 1).toUpperCase()}</span>} /><strong>{member.displayName}</strong><small>{member.mandateLabel || forumRoleLabels[member.role] || member.role}</small></article>)}</div> : <Empty>Aucun membre du collectif n’est affiché publiquement.</Empty>}</Block>,
    gallery: <Block id="gallery" title="Galerie" icon={<Images size={19} />}>{albums.length ? <div className="portal-gallery">{albums.map((album) => <AlbumCard key={album.id} album={album} />)}</div> : <Empty>Les albums publiés par la structure apparaîtront ici.</Empty>}</Block>,
    memory: <Block id="memory" title="Histoire & folklore" icon={<BookOpen size={19} />}>{structure.history ? <p className="portal-copy">{structure.history}</p> : null}{pages.map((page) => <details className="portal-memory" key={page.id}><summary>{page.title}</summary><p className="portal-copy">{page.content || "Le contenu de cette page sera bientôt disponible."}</p></details>)}{!structure.history && !pages.length ? <Empty>Une mémoire à écrire et à transmettre, génération après génération.</Empty> : null}</Block>,
  };
  const nav = [
    { id: "about", label: "Accueil", visible: show("about") },
    { id: "events", label: "Événements", visible: show("events") },
    { id: "gallery", label: "Galerie", visible: show("gallery") },
    { id: "team", label: structure.type === "COMMITTEE" || structure.type === "CIRCLE" ? "Comité" : "Équipe", visible: show("team") },
    { id: "memory", label: "Histoire / Folklore", visible: show("memory") },
    { id: "contact", label: "Contact", visible: contactVisible },
  ].filter((item) => item.visible);

  return <main className="forum-page structure-portal">
    <div className="portal-breadcrumb"><Link to="/forum/structures"><ArrowLeft size={14} /> Structures</Link><span>/</span><span>{structure.name}</span><Link to={structurePath(slug)} className="portal-member-access">Espace membre <ArrowUpRight size={13} /></Link></div>
    <div className="portal-localbar"><nav aria-label="Rubriques de la structure">{nav.map((item) => <Link key={item.id} to={`#${item.id}`} aria-current={hash === `#${item.id}` || (!hash && item.id === "about") ? "location" : undefined}>{item.label}</Link>)}</nav><Dialog><DialogTrigger className="portal-app-button"><Smartphone size={15} /> Dans l’app TORÈ</DialogTrigger><DialogContent className="portal-dialog"><DialogTitle>Retrouvez TORÈ dans l’application</DialogTitle><DialogDescription>Le Forum présente la structure et sa mémoire. L’application accompagne vos soirées et leurs actions en direct.</DialogDescription><Link className="forum-button forum-button--primary" to="/rejoindre#beta">Installer l’application <ArrowUpRight size={16} /></Link></DialogContent></Dialog></div>
    <section className="portal-hero" aria-labelledby="structure-name">
      {publicImageUrl(structure.bannerUrl) ? <img className="portal-hero__banner" src={publicImageUrl(structure.bannerUrl)} alt="" onError={(event) => { event.currentTarget.hidden = true; }} /> : <div className="portal-hero__motif" aria-hidden="true"><Building2 /></div>}
      <div className="portal-hero__identity"><PortalImage className="portal-logo" src={structure.logoUrl} name={`Logo de ${structure.name}`} fallback={<span>{structure.name.slice(0, 1).toUpperCase()}</span>} /><div><p className="portal-kicker">Une structure de la communauté</p><h1 id="structure-name">{structure.name}</h1><div className="portal-badges"><span><Building2 size={13} />{variant.label}</span>{structure.city ? <span><MapPin size={13} />{structure.city}</span> : null}</div><p>{structure.description || variant.intro}</p><div className="portal-hero__actions">{show("events") ? <Link className="forum-button forum-button--primary" to="#events"><CalendarDays size={16} /> Voir les événements</Link> : null}{contactVisible ? <Link className="forum-button forum-button--ghost" to="#contact"><Mail size={16} /> Contacter</Link> : null}<StructureClaimAction structureId={structure.id} structureName={structure.name} /></div></div></div>
    </section>
    <div className="portal-columns"><div className="portal-main">{variant.order.filter(show).map((block) => <div key={block}>{blocks[block]}</div>)}</div><aside className="portal-aside" aria-label="Informations de la structure">
      {contactVisible ? <Block aside id="contact" title="Informations pratiques" icon={<MapPin size={19} />}><div className="portal-contact">{address ? <p><MapPin size={15} /><span>{address}</span></p> : null}{portal.opening_hours ? <p><Clock3 size={15} /><span className="portal-copy">{portal.opening_hours}</span></p> : null}{structure.contactPhone ? <a href={`tel:${structure.contactPhone.replace(/[^+0-9]/g, "")}`}><Phone size={15} />{structure.contactPhone}</a> : null}{structure.contactEmail ? <a href={`mailto:${structure.contactEmail}`}><Mail size={15} />{structure.contactEmail}</a> : null}{website ? <a href={website} target="_blank" rel="noreferrer"><Globe2 size={15} />Site web<ArrowUpRight size={13} /></a> : null}{instagram ? <a href={instagram} target="_blank" rel="noreferrer"><Images size={15} />Instagram<ArrowUpRight size={13} /></a> : null}{socials.map(({ label, url }) => <a key={label} href={url} target="_blank" rel="noreferrer"><Globe2 size={15} />{label}<ArrowUpRight size={13} /></a>)}{maps ? <a className="portal-map-link" href={maps} target="_blank" rel="noreferrer">Voir sur Google Maps<ArrowUpRight size={13} /></a> : null}{!address && !portal.opening_hours && !structure.contactPhone && !structure.contactEmail && !website && !instagram && !socials.length ? <Empty>Aucune coordonnée publique renseignée.</Empty> : null}</div></Block> : null}
      <Block aside title="Cette structure sur TORÈ" icon={<Globe2 size={19} />}><ul className="portal-platform"><li><Globe2 size={15} /> Page publique du collectif</li><li><Users size={15} /> Un compte partagé avec l’application</li><li><Smartphone size={15} /> Vos soirées dans l’app TORÈ</li></ul>{structure.type === "BAR" ? <p className="portal-bar-note">Les commandes, le QR et les actions de soirée restent dans l’application TORÈ.</p> : null}</Block>
      {show("partners") && structure.sponsors?.length ? <Block aside id="partners" title="Partenaires / Sponsors" icon={<Handshake size={19} />}><div className="portal-sponsors">{structure.sponsors.map((name, index) => <span key={index}>{name}</span>)}</div></Block> : null}
      {isPublic("description") && portal.announcement ? <Block aside title="À la une" icon={<Megaphone size={19} />}><p className="portal-copy">{portal.announcement}</p></Block> : null}
      <p className="portal-signature">Plus qu’un forum,<br />une communauté.</p>
    </aside></div>
  </main>;
}
function AlbumCard({ album }: { album: PortalAlbum }) {
  const images = (album.media ?? []).filter((item) => !item.type || ["IMAGE", "PHOTO"].includes(item.type.toUpperCase()));
  return <Dialog><DialogTrigger asChild><button className="portal-album"><PortalImage src={album.coverUrl || images[0]?.url} name={album.title} /><strong>{album.title}</strong><small>{images.length} photo{images.length === 1 ? "" : "s"}</small></button></DialogTrigger><DialogContent className="portal-dialog portal-album-dialog"><DialogTitle>{album.title}</DialogTitle><DialogDescription>{album.description || "Souvenirs publiés par la structure."}</DialogDescription><div className="portal-album-photos">{images.length ? images.map((photo) => <figure key={photo.id}><PortalImage src={photo.url} name={photo.caption || album.title} />{photo.caption ? <figcaption>{photo.caption}</figcaption> : null}</figure>) : album.coverUrl ? <PortalImage src={album.coverUrl} name={album.title} /> : <Empty>Cet album ne contient pas encore de photo publique.</Empty>}</div></DialogContent></Dialog>;
}
