import { FormEvent, useEffect, useState } from "react";
import { Link, matchPath, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowUpRight, Bell, Building2, Check, ChevronDown, CircleUserRound, ExternalLink, Home, LockKeyhole, LogOut, Menu, Plus, Search, Settings } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { apiFetch } from "@/lib/api";
import { clearToken, getToken, MeResponse } from "@/lib/auth";
import { getMe } from "@/lib/session";
import { forumNavGroups, forumNavItems, forumRoleLabels, ForumWorkspace, structurePath, structureTypeLabels } from "@/lib/forum-navigation";
import logo from "@/assets/logo-full.png";
import "@/styles/forum.css";
import "@/styles/forum-layout.css";

type Session = { token: string; me: MeResponse; items: ForumWorkspace[] };

function decodeSlug(slug?: string) {
  try { return slug ? decodeURIComponent(slug) : null; } catch { return slug ?? null; }
}

function savedStructure(userId: string) {
  try { return localStorage.getItem(`tore.forum.structure.${userId}`); } catch { return null; }
}
function rememberStructure(userId: string, slug: string | null) {
  try {
    const key = `tore.forum.structure.${userId}`;
    if (slug) localStorage.setItem(key, slug); else localStorage.removeItem(key);
  } catch { /* Navigation still works when browser storage is unavailable. */ }
}

export default function ForumLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = getToken();
  const [session, setSession] = useState<Session | null>(null);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState(""); const [searchOpen, setSearchOpen] = useState(false); const [searchResults, setSearchResults] = useState<{category:string;id:number;title:string;snippet:string;target:string}[]>([]); const [notifications, setNotifications] = useState<{id:number;title:string;body?:string|null;targetPath?:string|null;readAt?:string|null}[]>([]); const [notificationsOpen, setNotificationsOpen] = useState(false);
  const route = matchPath("/forum/structures/:slug/:section?", location.pathname);
  const routeSlug = decodeSlug(route?.params.slug);

  useEffect(() => {
    let active = true;
    setError(false);
    if (!token) { setSession(null); setSelectedSlug(null); setLoading(false); return; }
    setLoading(true);
    void Promise.all([getMe(true), apiFetch<{ items: ForumWorkspace[] }>("/forum/me/structures")])
      .then(([me, data]) => {
        if (!active || getToken() !== token) return;
        setSession({ token, me, items: data.items });
        setSelectedSlug((current) => data.items.some((item) => item.slug === current) ? current : savedStructure(me.id));
      })
      .catch(() => { if (active) { setSession(null); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, location.pathname, revision]);

  useEffect(() => {
    const refresh = () => setRevision((value) => value + 1);
    window.addEventListener("focus", refresh);
    window.addEventListener("storage", refresh);
    window.addEventListener("tore:structure-updated", refresh);
    return () => { window.removeEventListener("focus", refresh); window.removeEventListener("storage", refresh); window.removeEventListener("tore:structure-updated", refresh); };
  }, []);

  const currentSession = session?.token === token ? session : null;
  const items = currentSession?.items ?? [];
  const me = currentSession?.me;
  const workspace = items.find((item) => item.slug === routeSlug) ?? items.find((item) => item.slug === selectedSlug) ?? items.find((item) => item.canManage) ?? items[0];
  const accountHref = token ? "/compte" : "/forum/login";

  useEffect(() => {
    if (!me) return;
    setSelectedSlug(workspace?.slug ?? null);
    rememberStructure(me.id, workspace?.slug ?? null);
  }, [me, workspace?.slug]);
  useEffect(() => { setMobileOpen(false); setSearch(""); }, [location.pathname]);
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); window.setTimeout(() => document.querySelector<HTMLInputElement>('[aria-label="Recherche globale"]')?.focus(), 0); } if (event.key === "Escape") setSearchOpen(false); }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, []);
  useEffect(() => { if (!searchOpen || !workspace || search.trim().length < 2) { setSearchResults([]); return; } const timer = window.setTimeout(() => { void apiFetch<{ results?: typeof searchResults }>(`/forum/structures/${workspace.slug}/search?q=${encodeURIComponent(search.trim())}`).then((data) => setSearchResults(data.results ?? [])).catch(() => setSearchResults([])); }, 250); return () => window.clearTimeout(timer); }, [search, searchOpen, workspace?.slug]);
  useEffect(() => { if (!workspace) { setNotifications([]); return; } void apiFetch<{items?: typeof notifications}>(`/forum/structures/${workspace.slug}/notifications`).then((data) => setNotifications(data.items ?? [])).catch(() => setNotifications([])); }, [workspace?.slug]);

  function selectWorkspace(item: ForumWorkspace) {
    if (me) rememberStructure(me.id, item.slug);
    setSelectedSlug(item.slug);
    navigate(structurePath(item.slug));
  }
  function logout() {
    if (me) rememberStructure(me.id, null);
    clearToken(); setSession(null); setSelectedSlug(null);
    navigate("/forum/login");
  }
  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const term = search.trim();
    if (term) navigate(`/forum/structures?q=${encodeURIComponent(term)}`);
  }
  const title = location.pathname === "/compte" ? "Mon profil" : location.pathname === "/forum/login" ? "Connexion" : route ? (route.params.section === "settings" ? "Paramètres" : forumNavItems.find(([key]) => key === route.params.section)?.[1] ?? "Page publique") : location.pathname === "/forum/structures" ? "Structures" : "Accueil";

  const sidebar = <>
    <Link className="forum-rail__brand" to="/forum" aria-label="Accueil Forum TORÈ"><img src={logo} alt="" /><strong>Forum TORÈ</strong></Link>
    <DropdownMenu>
      <DropdownMenuTrigger className="forum-rail__selector" aria-label="Changer de structure">
        <ForumIdentityImage src={workspace?.logoUrl} name={workspace?.name ?? "TORÈ"} />
        <span><strong>{workspace?.name ?? (loading ? "Chargement…" : "Choisir une structure")}</strong><small>{workspace ? `${structureTypeLabels[workspace.type] ?? workspace.type}${workspace.city ? ` · ${workspace.city}` : ""}` : token ? "Vos espaces TORÈ" : "Comités · Cercles · Ordres"}</small></span><ChevronDown size={15} />
      </DropdownMenuTrigger>
      <DropdownMenuContent className="forum-structure-menu" sideOffset={6} align="start">
        <DropdownMenuLabel>Mes structures</DropdownMenuLabel>
        {items.map((item) => <DropdownMenuItem key={item.id} onSelect={() => selectWorkspace(item)}><ForumIdentityImage src={item.logoUrl} name={item.name} /><span><strong>{item.name}</strong><small>{forumRoleLabels[item.role] ?? item.role}{item.canManage ? " · Gestion" : ""}</small></span>{item.slug === workspace?.slug ? <Check size={16} aria-label="Structure sélectionnée" /> : null}</DropdownMenuItem>)}
        {!items.length ? <p className="forum-structure-menu__empty">{loading ? "Chargement des accès…" : error ? "Impossible de charger vos structures." : token ? "Aucune structure active pour ce compte." : "Connectez-vous pour retrouver vos comités."}</p> : null}
        {error ? <DropdownMenuItem onSelect={() => setRevision((value) => value + 1)}>Réessayer</DropdownMenuItem> : null}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><Link to="/forum/structures"><Building2 size={16} /> Explorer les structures</Link></DropdownMenuItem>
        {!token ? <DropdownMenuItem asChild><Link to="/forum/login"><CircleUserRound size={16} /> Se connecter</Link></DropdownMenuItem> : null}
      </DropdownMenuContent>
    </DropdownMenu>
    {!workspace && !loading ? <p className="forum-rail__hint">{error ? "Vos accès n’ont pas pu être chargés. Réessayez depuis le sélecteur." : token ? "Aucun accès actif à un comité. Vos rubriques apparaîtront ici dès votre rattachement." : "Connectez-vous pour retrouver les rubriques de votre comité."}</p> : null}
    <nav className="forum-rail__nav" aria-label="Navigation du Forum">
      {forumNavGroups.map((group) => <section className="forum-rail__group" key={group.label}><h2>{group.label}</h2>
        {group.label === "Général" && !workspace ? <><NavLink to="/forum" end className="forum-rail__link"><Home size={18} /> Accueil du Forum</NavLink><NavLink to="/forum/structures" end className="forum-rail__link"><Building2 size={18} /> Toutes les structures</NavLink></> : null}
        {group.items.map(([key, label, Icon]) => {
          const restricted = workspace && ((["visibility", "audit"].includes(key) && !workspace.canManage) || (key === "accounting" && !workspace.canReadFinance));
          return workspace && !restricted ? <NavLink key={key} className="forum-rail__link" end to={structurePath(workspace.slug, key)}><Icon size={18} /><span>{label}</span></NavLink> : <span key={key} className="forum-rail__link is-unavailable" aria-disabled="true" title={restricted ? "Réservé aux rôles autorisés" : "Sélectionnez une structure pour ouvrir cette rubrique"}><Icon size={18} /><span>{label}</span>{restricted ? <LockKeyhole size={12} /> : null}</span>;
        })}
      </section>)}
    </nav>
    <div className="forum-rail__bottom">
      <div className="forum-rail__profile"><Link to={accountHref} className="forum-rail__user" aria-label={token ? "Ouvrir mon profil" : "Se connecter"}><ForumIdentityImage src={me?.avatar_url} name={me?.display_name ?? "Invité"} /><span><strong>{me?.display_name ?? (token ? "Mon compte" : "Se connecter")}</strong><small>{workspace ? forumRoleLabels[workspace.role] ?? workspace.role : "Compte TORÈ"}</small></span></Link><Link className="forum-rail__settings" to={workspace?.canManage ? structurePath(workspace.slug, "settings") : accountHref} aria-label={workspace?.canManage ? "Paramètres de la structure" : "Paramètres du compte"}><Settings size={20} /></Link></div>
      <div className="forum-rail__exit"><Link to="/">Présentation TORÈ <ArrowUpRight size={12} /></Link>{token ? <button onClick={logout} title="Se déconnecter" aria-label="Se déconnecter"><LogOut size={15} /></button> : null}</div>
    </div>
  </>;

  return <div className="forum-layout">
    <a href="#forum-content" className="forum-skip-link">Aller au contenu</a>
    <aside className="forum-rail">{sidebar}</aside>
    <div className="forum-layout__workspace">
      <header className="forum-topbar">
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}><SheetTrigger className="forum-topbar__menu" aria-label="Ouvrir la navigation du Forum"><Menu size={20} /></SheetTrigger><SheetContent side="left" className="forum-mobile-rail"><SheetTitle className="sr-only">Navigation du Forum</SheetTitle><SheetDescription className="sr-only">Choisissez une structure ou une rubrique du Forum.</SheetDescription>{sidebar}</SheetContent></Sheet>
        <button className="forum-topbar__notification" aria-label="Notifications" onClick={() => setNotificationsOpen((open) => !open)}><Bell size={18} />{notifications.some((item) => !item.readAt) ? <span>{notifications.filter((item) => !item.readAt).length}</span> : null}</button><div className="forum-topbar__breadcrumb"><Link to="/forum">{workspace && routeSlug === workspace.slug ? workspace.name : "Forum TORÈ"}</Link><span>/</span><strong>{title}</strong></div>
        <div className="forum-global-search"><form className="forum-topbar__search" role="search" onSubmit={(event) => { event.preventDefault(); setSearchOpen(true); }}><Search size={16} /><input aria-label="Recherche globale" placeholder="Rechercher… (⌘K)" value={search} onFocus={() => setSearchOpen(true)} onChange={(event) => { setSearch(event.target.value); setSearchOpen(true); }} /><button type="submit" aria-label="Lancer la recherche"><ArrowUpRight size={15} /></button></form>{searchOpen && workspace && search.trim().length >= 2 ? <div className="forum-global-search__results">{searchResults.length ? searchResults.map((result) => <Link key={`${result.category}-${result.id}`} to={result.target} onClick={() => setSearchOpen(false)}><span className="forum-badge">{result.category}</span><span><strong>{result.title}</strong><small>{result.snippet}</small></span></Link>) : <p className="forum-empty">Aucun résultat accessible.</p>}</div> : null}</div>
<div className="forum-topbar__actions">{workspace ? <Link className="forum-button forum-button--ghost forum-topbar__preview" to={structurePath(workspace.slug, "public")}><ExternalLink size={14} /> Aperçu public</Link> : null}<Link className="forum-topbar__account" to={accountHref} aria-label={token ? "Ouvrir mon profil" : "Se connecter"}>{token ? <ForumIdentityImage src={me?.avatar_url} name={me?.display_name ?? "TORÈ"} /> : <><CircleUserRound size={18} /><span>Se connecter</span></>}</Link>{workspace?.canManage ? <Link className="forum-button forum-button--primary" aria-label="Créer un événement" to={`${structurePath(workspace.slug, "events")}#create-event`}><Plus size={16} /><span>Créer un événement</span></Link> : null}</div>
      {notificationsOpen && workspace ? <div className="forum-notifications__menu">{notifications.length ? notifications.map((item) => <Link key={item.id} to={item.targetPath || structurePath(workspace.slug)} onClick={() => setNotificationsOpen(false)} className={item.readAt ? "is-read" : ""}><strong>{item.title}</strong><small>{item.body || "Notification de structure"}</small></Link>) : <p className="forum-empty">Aucune notification.</p>}<button className="forum-button forum-button--ghost" onClick={() => { void apiFetch(`/forum/structures/${workspace.slug}/notifications/read-all`, { method: "POST" }); setNotifications((items) => items.map((item) => ({ ...item, readAt: new Date().toISOString() }))); }}>Tout marquer comme lu</button></div> : null}</header>
      <div id="forum-content" tabIndex={-1} className="forum-layout__content"><Outlet context={{ workspace, loading, error }} /></div>
      <footer className="forum-layout__footer"><span><strong>Forum TORÈ</strong> · Au service des structures étudiantes.</span><div><Link to="/legal/privacy">Confidentialité</Link><Link to="/legal/terms">Conditions d’utilisation</Link></div></footer>
    </div>
  </div>;
}

function ForumIdentityImage({ src, name }: { src?: string | null; name: string }) {
  const [failed, setFailed] = useState<string | null>(null);
  const letters = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return <span className="forum-identity-image">{src && failed !== src ? <img src={src} alt={`Logo ou avatar de ${name}`} onError={() => setFailed(src)} /> : <span aria-hidden="true">{letters}</span>}</span>;
}
