import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Building2, CalendarClock, CircleUserRound, LogOut, ShieldCheck } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { MeResponse, clearToken, setCachedMe } from "@/lib/auth";
import { getMe } from "@/lib/session";
import "@/styles/forum.css";

type Visibility = "PUBLIC" | "TORE_USERS" | "PRIVATE";
type ProfilePrivacy = {
  profile: Visibility;
  bio: Visibility;
  affiliations: Visibility;
  event_history: Visibility;
  event_history_opt_in: boolean;
};
type Affiliation = {
  id: number;
  structure: { id: number; name: string; city?: string | null };
  role: string;
  status: string;
  starts_at?: string | null;
  ends_at?: string | null;
  mandate?: string | null;
};
type EventHistory = { id: number; name: string; starts_at?: string | null };
type OwnerProfile = {
  id: string;
  username?: string | null;
  display_name: string;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  avatar_url?: string | null;
  city?: string | null;
  bio?: string | null;
  phone?: string | null;
  instagram_handle?: string | null;
  oripeaux?: string | null;
  account_status?: string;
  privacy?: ProfilePrivacy;
  affiliations?: Affiliation[];
  event_history?: EventHistory[];
};
type Capabilities = {
  global_roles?: string[];
  structures?: Record<string, unknown>[];
  events?: Record<string, unknown>[];
};

function dateLabel(value?: string | null) {
  if (!value) return "Date non renseignée";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium" }).format(new Date(value));
}

function visibilityLabel(value?: Visibility) {
  if (value === "PUBLIC") return "Public";
  if (value === "TORE_USERS") return "Utilisateurs TORÈ";
  return "Privé";
}

function statusLabel(value: string) {
  const status = value.toUpperCase();
  if (status === "ACTIVE") return "Actuel";
  if (status === "ENDED") return "Ancien mandat";
  if (status === "REVOKED") return "Révoqué";
  if (status === "PENDING") return "En attente";
  return value;
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<OwnerProfile | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [privacySaving, setPrivacySaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [upgradeCode, setUpgradeCode] = useState("");

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [ownerProfile, snapshot, effectiveCapabilities] = await Promise.all([
        apiFetch<OwnerProfile>("/me/profile"),
        getMe(true),
        apiFetch<Capabilities>("/me/capabilities"),
      ]);
      setProfile(ownerProfile);
      setMe(snapshot);
      setCapabilities(effectiveCapabilities);
      setMsg("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Session expirée, reconnectez-vous.");
    } finally {
      setLoading(false);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    setSaving(true);
    setError("");
    try {
      const updated = await apiFetch<OwnerProfile>("/me/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: profile.username?.trim() || undefined,
          display_name: profile.display_name.trim(),
          avatar_url: profile.avatar_url?.trim() || undefined,
          bio: profile.bio?.trim() || "",
          city: profile.city?.trim() || "",
          oripeaux: profile.oripeaux?.trim() || "",
        }),
      });
      setProfile(updated);
      const snapshot = await getMe(true);
      setMe(snapshot);
      setCachedMe(snapshot);
      setMsg("Profil synchronisé avec l’application TORÈ.");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Impossible d’enregistrer le profil.");
    } finally {
      setSaving(false);
    }
  }

  async function updatePrivacy(fieldName: keyof ProfilePrivacy, value: Visibility | boolean) {
    setPrivacySaving(true);
    setError("");
    try {
      const updated = await apiFetch<OwnerProfile>("/me/privacy", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [fieldName]: value }),
      });
      setProfile(updated);
      setMsg("Réglage de visibilité enregistré.");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Impossible d’enregistrer ce réglage.");
    } finally {
      setPrivacySaving(false);
    }
  }

  async function setMode(mode: "user" | "organizer" | "team") {
    try {
      if (mode === "user") {
        await apiFetch("/auth/me", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_mode: "user" }) });
        setMsg("Mode utilisateur activé.");
      } else {
        await apiFetch("/auth/role/request-upgrade", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ requested_mode: mode, code: upgradeCode }) });
        setMsg("Demande envoyée, en attente de validation.");
      }
      await refresh();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Impossible de modifier le mode du compte.");
    }
  }

  function logout() {
    clearToken();
    setCachedMe(null);
    navigate("/forum/login");
  }

  const affiliations = profile?.affiliations ?? [];
  const eventHistory = profile?.event_history ?? [];
  const operationalRoles = [
    ...(capabilities?.global_roles ?? []),
    ...(capabilities?.structures ?? []).map((item) => `${String(item.role ?? "Rôle")} · structure`),
    ...(capabilities?.events ?? []).map((item) => `${String(item.role ?? "Rôle")} · event`),
  ].filter((item) => item !== "USER");

  return (
    <div className="forum-account-page">

      <main className="forum-account-main">
        <section className="forum-account-container">
          <div className="forum-account-head">
            <div className="forum-account-identity">
              <div className="forum-account-avatar">{profile?.avatar_url ? <img src={profile.avatar_url} alt="" /> : <CircleUserRound size={28} />}</div>
              <div><span className="forum-eyebrow">Compte unique TORÈ</span><h1>{profile?.display_name || "Mon profil"}</h1><p>{profile?.username ? `@${profile.username} · ` : ""}{profile?.email || me?.email || "Compte connecté"}</p></div>
            </div>
            <div className="forum-account-actions"><button className="forum-button forum-button--ghost" onClick={() => void refresh()}>Rafraîchir</button><button className="forum-button forum-button--ghost" onClick={logout}><LogOut size={15} /> Se déconnecter</button><Link className="forum-button forum-button--primary" to="/forum">Retour au Forum <ArrowRight size={15} /></Link></div>
          </div>

          {loading ? <div className="forum-account-notice">Chargement du profil partagé…</div> : null}
          {error ? <div className="forum-alert">{error}</div> : null}

          <div className="forum-account-metrics"><AccountMetric label="Compte" value={profile?.account_status || "ACTIF"} /><AccountMetric label="Mode" value={me?.account_mode || "user"} /><AccountMetric label="Appartenances" value={affiliations.length} /><AccountMetric label="Historique visible" value={eventHistory.length} /></div>

          <div className="profile-two-col forum-account-grid">
            <section className="forum-account-card"><AccountCardHeader icon={<CircleUserRound size={17} />} title="Informations du compte" /><p className="forum-account-muted">Ces données sont enregistrées dans le compte utilisé par l’application mobile et le Forum.</p><div className="forum-account-form"><label className="forum-account-field">Nom affiché<input value={profile?.display_name || ""} onChange={(event) => profile && setProfile({ ...profile, display_name: event.target.value })} /></label><label className="forum-account-field">Pseudo unique<input value={profile?.username || ""} onChange={(event) => profile && setProfile({ ...profile, username: event.target.value })} placeholder="ex. tore.membre" /></label><div className="profile-two-fields forum-account-fields"><label className="forum-account-field">Prénom<input value={profile?.first_name || ""} readOnly /></label><label className="forum-account-field">Nom<input value={profile?.last_name || ""} readOnly /></label></div><div className="profile-two-fields forum-account-fields"><label className="forum-account-field">Ville<input value={profile?.city || ""} onChange={(event) => profile && setProfile({ ...profile, city: event.target.value })} /></label><label className="forum-account-field">Téléphone<input value={profile?.phone || ""} readOnly /></label></div><label className="forum-account-field">Bio<textarea maxLength={280} value={profile?.bio || ""} onChange={(event) => profile && setProfile({ ...profile, bio: event.target.value })} /></label><label className="forum-account-field">Instagram<input value={profile?.instagram_handle || ""} readOnly /></label><button className="forum-button forum-button--primary" onClick={() => void saveProfile()} disabled={saving || !profile}>{saving ? "Synchronisation…" : "Enregistrer les modifications"}</button></div></section>

            <section className="forum-account-card"><AccountCardHeader icon={<ShieldCheck size={17} />} title="Identité folklorique" /><p className="forum-account-muted">Les oripeaux suivent désormais le même compte dans TORÈ.</p><label className="forum-account-field">Oripeaux associés<textarea maxLength={500} value={profile?.oripeaux || ""} onChange={(event) => profile && setProfile({ ...profile, oripeaux: event.target.value })} placeholder="Tablier, épitoge, penne…" /></label><div className="forum-account-info"><ShieldCheck size={17} /><p>Les rôles de comité et l’historique des événements sont récupérés automatiquement depuis l’application. Ils ne sont pas recréés manuellement ici.</p></div></section>
          </div>

          <section className="forum-account-card"><AccountCardHeader icon={<Building2 size={17} />} title="Rôles et appartenances" /><p className="forum-account-muted">Les mandats actuels et précédents sont synchronisés avec les structures TORÈ.</p><div className="forum-account-affiliations">{affiliations.length ? affiliations.map((item) => <div className="forum-account-affiliation" key={item.id}><div><strong>{item.structure.name}</strong><p>{item.role}{item.mandate ? ` · ${item.mandate}` : ""}{item.structure.city ? ` · ${item.structure.city}` : ""}</p><small>{item.starts_at ? `Depuis ${dateLabel(item.starts_at)}` : ""}{item.ends_at ? ` · fin ${dateLabel(item.ends_at)}` : ""}</small></div><span className="forum-badge">{statusLabel(item.status)}</span></div>) : <div className="forum-empty">Aucune affiliation enregistrée pour le moment.</div>}</div>{operationalRoles.length ? <p className="forum-account-muted">Accès opérationnels : {operationalRoles.join(" · ")}</p> : null}</section>

          <div className="profile-two-col forum-account-grid">
            <section className="forum-account-card"><AccountCardHeader icon={<ShieldCheck size={17} />} title="Visibilité du profil" /><p className="forum-account-muted">Les réglages sont partagés avec l’application et respectés par les profils publics du Forum.</p>{profile?.privacy ? <div className="forum-account-visibility">{(["profile", "bio", "affiliations", "event_history"] as const).map((key) => <label className="forum-account-visibility-row" key={key}><span>{key === "profile" ? "Profil" : key === "bio" ? "Bio" : key === "affiliations" ? "Appartenances" : "Historique des événements"}<small>{visibilityLabel(profile.privacy?.[key])}</small></span><select disabled={privacySaving} value={profile.privacy[key]} onChange={(event) => void updatePrivacy(key, event.target.value as Visibility)}><option value="PUBLIC">Public</option><option value="TORE_USERS">Utilisateurs TORÈ</option><option value="PRIVATE">Privé</option></select></label>)}<label className="forum-account-checkbox"><input type="checkbox" checked={profile.privacy.event_history_opt_in} disabled={privacySaving} onChange={(event) => void updatePrivacy("event_history_opt_in", event.target.checked)} /> Autoriser l’historique des événements</label></div> : <p className="forum-account-muted">Réglages indisponibles.</p>}</section>

            <section className="forum-account-card"><AccountCardHeader icon={<CircleUserRound size={17} />} title="Mode et accès" /><p className="forum-account-muted">Les demandes organisateur/équipe sont validées côté TORÈ.</p><input className="forum-account-input" value={upgradeCode} onChange={(event) => setUpgradeCode(event.target.value)} placeholder="Code organisateur / équipe" /><div className="forum-account-mode-actions"><button className="forum-button forum-button--ghost" onClick={() => void setMode("user")}>Utilisateur</button><button className="forum-button forum-button--ghost" onClick={() => void setMode("organizer")}>Organisateur</button><button className="forum-button forum-button--ghost" onClick={() => void setMode("team")}>Équipe</button></div>{me?.role_request_pending ? <p className="forum-account-pending">Demande en attente : {me.role_request_pending.requested_mode}</p> : null}</section>
          </div>

          <section className="forum-account-card"><AccountCardHeader icon={<CalendarClock size={17} />} title="Historique des événements" />{eventHistory.length ? <div className="forum-account-history">{eventHistory.map((event) => <div key={event.id}><span>{event.name}</span><small>{dateLabel(event.starts_at)}</small></div>)}</div> : <p className="forum-account-muted">{profile?.privacy?.event_history_opt_in ? "Aucun événement visible pour le moment." : "Active l’option de partage pour afficher ton historique d’événements."}</p>}</section>

          {msg ? <div className="forum-account-notice forum-account-notice--success">{msg}</div> : null}
        </section>
      </main>

    </div>
  );
}

function AccountMetric({ label, value }: { label: string; value: string | number }) { return <div className="forum-account-metric"><span>{label}</span><strong>{value}</strong></div>; }
function AccountCardHeader({ icon, title }: { icon: React.ReactNode; title: string }) { return <div className="forum-account-card__header"><div><span className="forum-eyebrow">Compte TORÈ</span><h2>{title}</h2></div><span className="forum-account-card__icon">{icon}</span></div>; }
