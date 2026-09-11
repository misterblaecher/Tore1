import { useState, type FormEvent } from "react";
import { BookOpen } from "lucide-react";
import { useStructureResource, useStructureWrite } from "@/hooks/use-structure-resource";
import { ApiError } from "@/lib/api";

type Page = { id: number; title: string; content: string; category: string; visibility: string; publishedAt?: string; version: number };
const categories: Record<string, string> = { HISTORY: "Histoire", TRADITION: "Tradition", GLOSSARY: "Glossaire", GUIDE: "Guide", RULE: "Règlement", OTHER: "Autre" };
const initial = { title: "", content: "", category: "HISTORY", visibility: "STRUCTURE_MEMBERS" };
export default function StructurePages({ slug, canManage }: { slug: string; canManage: boolean }) {
  const base = `/forum/structures/${encodeURIComponent(slug)}/pages`;
  const { data, loading, error, reload } = useStructureResource<{ items: Page[] }>(base);
  const mutation = useStructureWrite();
  const [draft, setDraft] = useState(initial);
  const [editing, setEditing] = useState<Page | null>(null);
  const [saved, setSaved] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault(); setSaved("");
    const result = await mutation.write<Page>(editing ? `${base}/${editing.id}` : base, editing ? "PATCH" : "POST", { ...draft, title: draft.title.trim(), published: false });
    if (result) { setDraft(initial); setEditing(null); setSaved("Brouillon enregistré. La publication reste une action distincte."); reload(); }
  }
  async function publish(page: Page) {
    const result = await mutation.write<Page>(`${base}/${page.id}`, "PATCH", { published: !page.publishedAt });
    if (result) { setSaved(page.publishedAt ? "Page replacée en brouillon." : "Page publiée selon sa visibilité et celle du bloc Folklore."); reload(); }
  }
  const failure = error || mutation.error;
  return <div className="forum-grid-2"><section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Mémoire & transmission</span><h2>Histoire et folklore</h2></div><BookOpen size={20} /></div>
    {failure ? <p className="forum-alert" role="alert">{failure instanceof ApiError ? failure.message : "Impossible de charger ou enregistrer les pages."}<button onClick={reload}>Réessayer</button></p> : null}{saved ? <p role="status">{saved}</p> : null}
    {loading ? <p role="status">Chargement des pages…</p> : data?.items.length ? data.items.map(page => <article className="forum-card" key={page.id}><h3>{page.title}</h3><p className="forum-muted">{categories[page.category] || page.category} · {page.publishedAt ? "Publié" : "Brouillon"} · {page.visibility} · Version {page.version}</p><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{page.content}</p>{canManage ? <div className="forum-inline"><button disabled={mutation.busy} className="forum-button forum-button--ghost" onClick={() => { setEditing(page); setDraft({ title: page.title, content: page.content, category: page.category, visibility: page.visibility }); }}>Modifier</button><button disabled={mutation.busy} className="forum-button forum-button--ghost" onClick={() => void publish(page)}>{page.publishedAt ? "Repasser en brouillon" : "Publier"}</button></div> : null}</article>) : !error ? <p className="forum-empty">Aucune page accessible. Les récits et documents de transmission apparaîtront ici.</p> : null}
  </section>{canManage ? <section className="forum-card"><h2>{editing ? "Modifier la page" : "Nouvelle page"}</h2><form className="forum-form" onSubmit={save}><fieldset className="forum-form" disabled={mutation.busy}><label>Titre<input required minLength={2} maxLength={180} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} /></label><label>Catégorie<select value={draft.category} onChange={e => setDraft({ ...draft, category: e.target.value })}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Contenu<textarea required rows={10} maxLength={100000} value={draft.content} onChange={e => setDraft({ ...draft, content: e.target.value })} /></label><label>Visibilité<select value={draft.visibility} onChange={e => setDraft({ ...draft, visibility: e.target.value })}><option value="STRUCTURE_MEMBERS">Membres actifs</option><option value="OFFICE">Bureau</option><option value="ADMINS">Administrateurs</option><option value="PUBLIC">Public après publication</option></select></label><button className="forum-button forum-button--primary" type="submit">Enregistrer le brouillon</button>{editing ? <button type="button" className="forum-button forum-button--ghost" onClick={() => { setEditing(null); setDraft(initial); }}>Annuler</button> : null}</fieldset></form></section> : null}</div>;
}
