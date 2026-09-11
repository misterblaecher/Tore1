import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowUpRight, FileText, Hash, LockKeyhole, MessageSquare, Paperclip, Pencil, Pin, Plus, Search, Send, ShieldCheck, Users, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { forumRoleLabels } from "@/lib/forum-navigation";
import { publicImageUrl, publicWebUrl } from "@/lib/structure-portal";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import "@/styles/structure-discussions.css";

type Channel = { id: number; name: string; categoryId: number; visibility: string };
type Doc = { id: number; title: string; fileUrl: string; createdAt?: string };
type Post = { id: number; channelId: number; channelName: string; title: string; body: string; authorId: string; authorName: string; authorAvatar?: string; createdAt: string; parentId?: number; pinned: boolean; documents: Doc[]; reactions: { emoji: string; count: number; mine: boolean }[] };
type Member = { id: number; userId: string; displayName: string; avatarUrl?: string; role: string; status: string; startsAt?: string; endsAt?: string };
type Feed = { channels: Channel[]; categories: { id: number; name: string }[]; posts: Post[]; limited?: boolean };
const templates = ["Bureau", "Organisation events", "Communication", "Bar", "Sponsors", "Photos", "Comptabilité"];
const headers = () => ({ "Idempotency-Key": crypto.randomUUID() });
const stamp = (value: string, full = false) => new Intl.DateTimeFormat("fr-BE", full ? { dateStyle: "medium", timeStyle: "short" } : { hour: "2-digit", minute: "2-digit" }).format(new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`));
const emptyDraft = { title: "", body: "", docs: [] as number[] };

function Avatar({ name, src }: { name: string; src?: string }) {
  const [failed, setFailed] = useState(false);
  const url = publicImageUrl(src);
  return <span className="discussion-avatar">{url && !failed ? <img src={url} alt="" onError={() => setFailed(true)} /> : name.split(/\s+/).slice(0, 2).map(s => s[0]).join("").toUpperCase()}</span>;
}
function Attachment({ doc }: { doc: Doc }) {
  const url = publicWebUrl(doc.fileUrl);
  return url ? <a className="discussion-file" href={url} target="_blank" rel="noreferrer"><FileText size={21} /><span><strong>{doc.title}</strong><small>Document partagé</small></span><ArrowUpRight size={15} /></a> : <span className="discussion-file"><FileText size={21} />{doc.title} · lien indisponible</span>;
}

export default function StructureDiscussions({ slug, canManage }: { slug: string; canManage: boolean }) {
  const base = `/forum/structures/${encodeURIComponent(slug)}`;
  const [params, setParams] = useSearchParams();
  const [feed, setFeed] = useState<Feed>({ channels: [], categories: [], posts: [] });
  const [members, setMembers] = useState<Member[]>([]);
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, refresh] = useState(0);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState(params.get("recherche") || "");
  const [drafts, setDrafts] = useState<Record<number, typeof emptyDraft>>({});
  const [showTitle, setShowTitle] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [newChannel, setNewChannel] = useState(false);
  const [channelName, setChannelName] = useState("");
  const [visibility, setVisibility] = useState("STRUCTURE_MEMBERS");
  const [thread, setThread] = useState<Post | null>(null);
  const [reply, setReply] = useState("");
  const composer = useRef<HTMLTextAreaElement>(null);
  const current = feed.channels.find(c => c.id === Number(params.get("salon"))) ?? feed.channels.find(c => c.name === "Bureau") ?? feed.channels[0];
  const draft = drafts[current?.id] ?? emptyDraft;
  const updateDraft = (patch: Partial<typeof emptyDraft>) => { if (current) setDrafts(d => ({ ...d, [current.id]: { ...(d[current.id] ?? emptyDraft), ...patch } })); };

  useEffect(() => { setSearch(params.get("recherche") || ""); }, [params]);
  useEffect(() => {
    let active = true;
    Promise.all([apiFetch<Feed>(`${base}/discussions`), apiFetch<{ items: Member[] }>(`${base}/members`), apiFetch<{ items: Doc[] }>(`${base}/documents`)])
      .then(([data, people, files]) => { if (active) { setFeed(data); setMembers(people.items); setDocuments(files.items); setError(""); } })
      .catch(() => { if (active) setError("Impossible de charger les discussions. Vos brouillons sont conservés."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [base, revision]);
  // Refresh only while visible; don't discard drafts or announce invented presence.
  useEffect(() => { const timer = window.setInterval(() => { if (!document.hidden) refresh(n => n + 1); }, 30000); return () => clearInterval(timer); }, []);

  async function write(action: () => Promise<unknown>, success: () => void) {
    if (busy) return;
    setBusy(true); setError("");
    try { await action(); success(); refresh(n => n + 1); }
    catch { setError("L’action n’a pas pu être enregistrée. Vérifiez vos accès puis réessayez."); }
    finally { setBusy(false); }
  }
  function selectChannel(id: number) { const next = new URLSearchParams(params); next.set("salon", String(id)); next.delete("recherche"); setParams(next); setSearch(""); setShowTitle(false); setAttachOpen(false); }
  function startDiscussion() { setShowTitle(true); composer.current?.focus(); }
  function createChannel(event: FormEvent) {
    event.preventDefault();
    void write(async () => { const result = await apiFetch<{ id: number }>(`${base}/channels`, { method: "POST", headers: headers(), body: JSON.stringify({ name: channelName.trim(), visibility }) }); selectChannel(result.id); }, () => { setNewChannel(false); setChannelName(""); });
  }
  function send(event: FormEvent) {
    event.preventDefault(); if (!current || !draft.body.trim()) return;
    void write(() => apiFetch(`${base}/discussions`, { method: "POST", headers: headers(), body: JSON.stringify({ channel_id: current.id, title: draft.title.trim() || draft.body.trim().slice(0, 100).padEnd(2, "."), body: draft.body.trim(), document_ids: draft.docs }) }), () => { updateDraft(emptyDraft); setShowTitle(false); setAttachOpen(false); });
  }
  function act(post: Post, payload: object) { void write(() => apiFetch(`${base}/discussions/${post.id}`, { method: "PATCH", headers: headers(), body: JSON.stringify(payload) }), () => {}); }
  const activeMembers = members.filter(m => m.status === "ACTIVE" && (!m.startsAt || new Date(m.startsAt) <= new Date()) && (!m.endsAt || new Date(m.endsAt) > new Date()));
  const orderedPosts = [...feed.posts].sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id - b.id);
  const posts = orderedPosts.filter(p => search.trim() ? `${p.title} ${p.body} ${p.authorName}`.toLowerCase().includes(search.trim().toLowerCase()) : p.channelId === current?.id && !p.parentId);
  const pinned = orderedPosts.filter(p => p.channelId === current?.id && p.pinned && !p.parentId);
  const sharedDocs = [...new Map(orderedPosts.filter(p => p.channelId === current?.id).reverse().flatMap(p => p.documents ?? []).map(d => [d.id, d])).values()];
  const roleOf = (id: string) => { const member = activeMembers.find(m => m.userId === id); return member ? forumRoleLabels[member.role] || member.role : ""; };

  function message(post: Post, inThread = false) {
    const replies = orderedPosts.filter(p => p.parentId === post.id);
    return <article className="discussion-message" id={`message-${post.id}`} key={post.id}>
      <Avatar name={post.authorName} src={post.authorAvatar} />
      <div className="discussion-message__content"><header><strong>{post.authorName}</strong><span>{roleOf(post.authorId)}</span><time dateTime={post.createdAt} title={stamp(post.createdAt, true)}>{stamp(post.createdAt)}</time>{search && <button onClick={() => selectChannel(post.channelId)}>#{post.channelName}</button>}</header>
        <h3>{post.title}</h3><p>{post.body}</p>
        {!!post.documents?.length && <div className="discussion-attachments">{post.documents.map(doc => <Attachment doc={doc} key={doc.id} />)}</div>}
        <div className="discussion-message__actions">{["👍", "❤️", "✅"].map(emoji => { const reaction = post.reactions?.find(r => r.emoji === emoji); return <button key={emoji} disabled={busy} aria-label={`${emoji} : ${reaction?.count || 0} réaction(s)`} aria-pressed={reaction?.mine || false} onClick={() => act(post, { emoji, active: !reaction?.mine })}>{emoji}<span>{reaction?.count || ""}</span></button>; })}
          {!inThread && <button onClick={() => { setThread(post); setReply(""); }}><MessageSquare size={13} />{replies.length ? `${replies.length} réponse${replies.length > 1 ? "s" : ""}` : "Répondre"}</button>}
          {canManage && !post.parentId && <button disabled={busy} className="discussion-pin-action" aria-label={post.pinned ? "Désépingler" : "Épingler"} onClick={() => act(post, { pinned: !post.pinned })}><Pin size={13} />{post.pinned ? "Épinglé" : "Épingler"}</button>}
        </div>
      </div>
    </article>;
  }

  return <div className="discussion-workspace">
    <header className="discussion-toolbar"><form role="search" onSubmit={e => { e.preventDefault(); const next = new URLSearchParams(params); if (search.trim()) next.set("recherche", search.trim()); else next.delete("recherche"); setParams(next); }}><Search size={17} /><input maxLength={120} aria-label="Rechercher dans tous les salons" placeholder="Rechercher dans les discussions de la structure…" value={search} onChange={e => setSearch(e.target.value)} />{search && <button type="button" aria-label="Effacer la recherche" onClick={() => { setSearch(""); const next = new URLSearchParams(params); next.delete("recherche"); setParams(next); }}><X size={16} /></button>}</form><div>{canManage && <button className="forum-button forum-button--ghost" onClick={() => { setVisibility("STRUCTURE_MEMBERS"); setNewChannel(true); }}><Plus size={16} />Nouveau salon</button>}<button className="forum-button forum-button--primary" disabled={!current || loading} onClick={startDiscussion}><Pencil size={16} />Nouvelle discussion</button></div></header>
    {error && <div className="forum-alert" role="alert">{error} <button onClick={() => refresh(n => n + 1)}>Réessayer</button></div>}
    <div className="discussion-columns">
      <aside className="discussion-channels" aria-label="Salons de discussion"><div className="discussion-panel-heading"><h2>Salons</h2><span>{feed.channels.length}</span></div><label className="discussion-filter"><Search size={14} /><input aria-label="Filtrer les salons" placeholder="Filtrer les salons…" value={filter} onChange={e => setFilter(e.target.value)} /></label>
        {feed.categories.map(category => <section key={category.id}><h3>{category.name}</h3>{feed.channels.filter(c => c.categoryId === category.id && c.name.toLowerCase().includes(filter.toLowerCase())).sort((a, b) => { const x = templates.indexOf(a.name), y = templates.indexOf(b.name); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y); }).map(channel => <button className={`discussion-channel ${current?.id === channel.id ? "is-active" : ""}`} aria-current={current?.id === channel.id ? "page" : undefined} key={channel.id} onClick={() => selectChannel(channel.id)}>{channel.visibility === "STRUCTURE_MEMBERS" ? <Hash size={17} /> : <LockKeyhole size={16} />}<span>{channel.name}</span></button>)}</section>)}
        {!loading && !feed.channels.length && <p className="discussion-subtle">Aucun salon créé pour le moment.</p>}
        {canManage && <section className="discussion-suggestions"><h3>Salons suggérés</h3>{templates.filter(name => !feed.channels.some(c => c.name === name) && name.toLowerCase().includes(filter.toLowerCase())).map(name => <button key={name} onClick={() => { setChannelName(name); setVisibility(name === "Bureau" ? "OFFICE" : name === "Comptabilité" ? "TREASURY" : "STRUCTURE_MEMBERS"); setNewChannel(true); }}><Plus size={14} />{name}</button>)}</section>}
        <div className="discussion-channel-note"><ShieldCheck size={18} /><span>Espace interne<br /><small>Des échanges conservés pour la transmission.</small></span></div>
      </aside>
      <section className="discussion-conversation" aria-label="Fil de discussion"><header className="discussion-conversation__head"><Hash size={23} /><div><h1>{search.trim() ? "Résultats de recherche" : current?.name || "Discussions"}</h1><p>{search.trim() ? "Dans les salons auxquels vous avez accès" : current?.visibility === "OFFICE" ? "Coordination du bureau · Accès restreint" : current?.visibility === "TREASURY" ? "Suivi comptable · Accès restreint" : "Coordination et mémoire de votre structure"}</p></div><LockKeyhole size={16} aria-label="Espace interne" /></header>
        {!!pinned.length && !search && <div className="discussion-pinned">{pinned.map(post => <div key={post.id}><Pin size={17} /><div><strong>Message épinglé</strong><p>{post.title}</p><small>Par {post.authorName} · {stamp(post.createdAt, true)}</small></div><button onClick={() => document.getElementById(`message-${post.id}`)?.scrollIntoView({ block: "center", behavior: "auto" })}>Voir le message</button></div>)}</div>}
        <div className="discussion-feed" aria-busy={loading}>{loading ? <div className="discussion-empty">Chargement des échanges…</div> : posts.length ? posts.map((post, index) => <div key={post.id}>{(!index || posts[index - 1].createdAt.slice(0, 10) !== post.createdAt.slice(0, 10)) && <div className="discussion-date"><span>{new Date(post.createdAt).toLocaleDateString("fr-BE", { day: "numeric", month: "long", year: "numeric" })}</span></div>}{message(post, !!post.parentId)}</div>) : <div className="discussion-empty"><MessageSquare size={36} /><h2>{search ? "Aucun résultat" : current ? `Bienvenue dans #${current.name}` : "Un lieu pour faire avancer votre structure"}</h2><p>{search ? "Essayez un autre mot ou le nom d’un membre." : current ? "Partagez un ordre du jour, une décision ou une question. Les réponses resteront rattachées à chaque discussion." : "Créez votre premier salon depuis la colonne de gauche, puis lancez les échanges."}</p>{current && !search && <button className="forum-button forum-button--ghost" onClick={startDiscussion}><Plus size={15} />Lancer la première discussion</button>}</div>}{feed.limited && <p className="discussion-subtle">Les 300 derniers messages accessibles sont affichés.</p>}</div>
        {current && <form className="discussion-composer" onSubmit={send}>{showTitle && <input aria-label="Titre de la discussion" maxLength={180} placeholder="Titre de la discussion (ordre du jour, décision…)" value={draft.title} onChange={e => updateDraft({ title: e.target.value })} />}<textarea ref={composer} aria-label={`Message dans ${current.name}`} maxLength={10000} placeholder={`Écrire un message dans #${current.name}…`} value={draft.body} onChange={e => updateDraft({ body: e.target.value })} />{!!draft.docs.length && <div className="discussion-selected-docs">{draft.docs.map(id => <button type="button" key={id} onClick={() => updateDraft({ docs: draft.docs.filter(x => x !== id) })}>{documents.find(d => d.id === id)?.title}<X size={13} /></button>)}</div>}{attachOpen && <fieldset className="discussion-document-picker"><legend>Joindre depuis la bibliothèque</legend>{documents.length ? documents.map(doc => <label key={doc.id}><input type="checkbox" checked={draft.docs.includes(doc.id)} disabled={!draft.docs.includes(doc.id) && draft.docs.length >= 8} onChange={e => updateDraft({ docs: e.target.checked ? [...draft.docs, doc.id] : draft.docs.filter(id => id !== doc.id) })} />{doc.title}</label>) : <p>Aucun document accessible. <Link to={`${base}/documents`}>Ouvrir la bibliothèque</Link></p>}</fieldset>}<footer><button type="button" aria-label="Joindre un document" aria-expanded={attachOpen} onClick={() => setAttachOpen(!attachOpen)}><Paperclip size={18} /></button><span>Un sujet, un fil de réponses.</span><button className="discussion-send" type="submit" disabled={busy || !draft.body.trim() || loading} aria-label="Envoyer le message"><Send size={18} /></button></footer></form>}
      </section>
      <aside className="discussion-context"><section><div className="discussion-panel-heading"><h2><Users size={16} />Membres actifs</h2><Link to={`${base}/members`}>Voir tous <ArrowUpRight size={13} /></Link></div><p className="discussion-subtle">Mandats en cours · {activeMembers.length} membre{activeMembers.length > 1 ? "s" : ""}</p>{activeMembers.slice(0, 6).map(member => <div className="discussion-member" key={member.id}><Avatar name={member.displayName} src={member.avatarUrl} /><div><strong>{member.displayName}</strong><small>{forumRoleLabels[member.role] || member.role}</small></div></div>)}{!activeMembers.length && <p className="discussion-subtle">Aucun mandat actif affiché.</p>}</section>
        <section><div className="discussion-panel-heading"><h2>Documents partagés</h2><Link to={`${base}/documents`}>Bibliothèque <ArrowUpRight size={13} /></Link></div>{sharedDocs.length ? sharedDocs.slice(0, 5).map(doc => <Attachment key={doc.id} doc={doc} />) : <div className="discussion-doc-empty"><FileText size={27} /><p>Les documents joints aux messages de ce salon apparaîtront ici.</p></div>}</section><blockquote>« Plus qu’une organisation,<br />une tradition qui nous rassemble. »<cite>TORÈ <span /></cite></blockquote>
      </aside>
    </div>
    <Dialog open={newChannel} onOpenChange={setNewChannel}><DialogContent className="discussion-dialog"><DialogHeader><DialogTitle>Nouveau salon</DialogTitle><DialogDescription>Un espace durable pour un sujet ou une équipe de votre structure.</DialogDescription></DialogHeader><form className="forum-form" onSubmit={createChannel}><label>Nom du salon<input required minLength={2} maxLength={80} value={channelName} onChange={e => setChannelName(e.target.value)} placeholder="Ex. Bureau" /></label><label>Qui peut y accéder ?<select value={visibility} onChange={e => setVisibility(e.target.value)}><option value="STRUCTURE_MEMBERS">Tous les membres actifs</option><option value="OFFICE">Bureau et gestionnaires</option><option value="TREASURY">Trésorerie, secrétariat et gestionnaires</option></select></label>{error && <p role="alert">{error}</p>}<button className="forum-button forum-button--primary" disabled={busy || channelName.trim().length < 2}>Créer le salon</button></form></DialogContent></Dialog>
    <Dialog open={!!thread} onOpenChange={open => { if (!open) setThread(null); }}><DialogContent className="discussion-dialog discussion-thread"><DialogHeader><DialogTitle>Fil de réponses</DialogTitle><DialogDescription>{thread?.title}</DialogDescription></DialogHeader><div className="discussion-thread__messages">{thread && message(feed.posts.find(p => p.id === thread.id) || thread, true)}{orderedPosts.filter(p => p.parentId === thread?.id).map(p => message(p, true))}</div><form className="forum-form" onSubmit={e => { e.preventDefault(); if (!thread || !reply.trim()) return; void write(() => apiFetch(`${base}/discussions`, { method: "POST", headers: headers(), body: JSON.stringify({ channel_id: thread.channelId, parent_id: thread.id, title: `Re: ${thread.title}`.slice(0, 180), body: reply.trim() }) }), () => setReply("")); }}><label>Votre réponse<textarea required maxLength={10000} value={reply} onChange={e => setReply(e.target.value)} placeholder="Répondre à cette discussion…" /></label>{error && <p role="alert">{error}</p>}<button className="forum-button forum-button--primary" disabled={busy || !reply.trim()}><Send size={15} />Répondre</button></form></DialogContent></Dialog>
  </div>;
}
