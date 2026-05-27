import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Gauge,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  Trophy,
  Users,
} from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type LoadState = "idle" | "loading" | "ready" | "error";

type AccountRequest = {
  id: number;
  created_at: string;
  name: string;
  email: string;
  phone: string;
  is_whatsapp: boolean;
  source?: string | null;
  status: string;
};

type RoleRequest = {
  id: number;
  user_id: string;
  requested_mode: string;
  status: string;
  created_at?: string | null;
};

type EventRow = {
  id: number;
  name: string;
  starts_at?: string | null;
  ends_at?: string | null;
  bar_id?: number | null;
};

type BetRow = {
  id: number;
  title?: string;
  question?: string;
  status?: string;
  scope?: string;
  event_id?: number | null;
};

type AdminList<T> = {
  items: T[];
  next_cursor?: number | null;
};

const adminKeyStorage = "tore_admin_api_key";
const portalUrl = "http://localhost:5173";

function formatDate(value?: string | null) {
  if (!value) return "Date inconnue";
  return new Date(value).toLocaleString("fr-BE", { dateStyle: "short", timeStyle: "short" });
}

function shortDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("fr-BE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function isLive(event: EventRow) {
  const now = Date.now();
  const start = event.starts_at ? new Date(event.starts_at).getTime() : 0;
  const end = event.ends_at ? new Date(event.ends_at).getTime() : 0;
  return start <= now && (!end || end >= now);
}

async function adminFetch<T>(path: string, adminKey: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Api-Key": adminKey,
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export default function ControlCenterPage() {
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem(adminKeyStorage) || "");
  const [status, setStatus] = useState<LoadState>("idle");
  const [message, setMessage] = useState("");
  const [accountRequests, setAccountRequests] = useState<AccountRequest[]>([]);
  const [roleRequests, setRoleRequests] = useState<RoleRequest[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [bets, setBets] = useState<BetRow[]>([]);

  const liveEvents = useMemo(() => events.filter(isLive), [events]);
  const nextEvents = useMemo(() => events.filter((event) => !isLive(event)).slice(0, 6), [events]);
  const openBets = useMemo(() => bets.filter((bet) => (bet.status || "open").toLowerCase() !== "resolved"), [bets]);

  async function load() {
    setStatus("loading");
    setMessage("");
    try {
      const [eventRows, betRows] = await Promise.all([
        apiFetch<EventRow[]>("/events?limit=24").catch(() => []),
        apiFetch<BetRow[]>("/polymarket/bets?limit=24").catch(() => []),
      ]);
      setEvents(eventRows);
      setBets(betRows);

      if (adminKey.trim()) {
        localStorage.setItem(adminKeyStorage, adminKey.trim());
        const [accounts, roles] = await Promise.all([
          adminFetch<AdminList<AccountRequest>>("/admin/account-requests?status=pending&limit=20", adminKey.trim()).catch(() => ({ items: [] })),
          adminFetch<AdminList<RoleRequest>>("/admin/role-requests?status=pending&limit=20", adminKey.trim()).catch(() => ({ items: [] })),
        ]);
        setAccountRequests(accounts.items || []);
        setRoleRequests(roles.items || []);
      } else {
        setAccountRequests([]);
        setRoleRequests([]);
      }

      setStatus("ready");
    } catch {
      setStatus("error");
      setMessage("Impossible de charger le centre de pilotage.");
    }
  }

  async function markAccountProcessed(id: number) {
    if (!adminKey.trim()) return;
    await fetch(`${API_BASE}/admin/account-requests/${id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Api-Key": adminKey.trim(),
      },
      body: JSON.stringify({ status: "processed" }),
    });
    setAccountRequests((rows) => rows.filter((row) => row.id !== id));
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <main className="min-h-screen bg-background text-foreground">
      <section className="container pt-24 pb-10">
        <div className="flex flex-col gap-5">
          <header className="flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Poste de pilotage TORÈ</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">Gérer l’app depuis ce PC</h1>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                Demandes comité, soirées en cours, Polymarket, modules et raccourcis vers les consoles opérationnelles.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="control-btn control-btn-primary" onClick={() => void load()} disabled={status === "loading"}>
                <RefreshCw size={16} /> {status === "loading" ? "Actualisation" : "Actualiser"}
              </button>
              <a className="control-btn" href={`${portalUrl}/login`} target="_blank" rel="noreferrer">
                <ExternalLink size={16} /> Portail ops
              </a>
            </div>
          </header>

          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<Users size={18} />} label="Demandes comité" value={accountRequests.length} tone="gold" />
            <Metric icon={<CalendarClock size={18} />} label="Soirées live" value={liveEvents.length} tone="ruby" />
            <Metric icon={<Trophy size={18} />} label="Polymarket ouverts" value={openBets.length} tone="blue" />
            <Metric icon={<Gauge size={18} />} label="API" value={status === "error" ? "Erreur" : "OK"} tone={status === "error" ? "ruby" : "green"} />
          </section>

          <section className="control-panel">
            <div>
              <div className="control-panel-title">
                <KeyRound size={18} />
                <h2>Accès admin local</h2>
              </div>
              <p className="control-muted">Colle ici la clé `ADMIN_API_KEY` pour recevoir les demandes privées. Elle reste dans le stockage local de ton navigateur.</p>
            </div>
            <div className="grid gap-2 md:grid-cols-[1fr_auto]">
              <input
                className="control-input"
                value={adminKey}
                onChange={(event) => setAdminKey(event.target.value)}
                placeholder="ADMIN_API_KEY"
                type="password"
              />
              <button className="control-btn control-btn-primary" onClick={() => void load()}>Charger admin</button>
            </div>
            {message ? <p className="text-sm text-destructive">{message}</p> : null}
          </section>

          <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <section className="control-panel">
              <div className="control-panel-title">
                <ShieldCheck size={18} />
                <h2>Demandes de création comité</h2>
              </div>
              <div className="control-list">
                {accountRequests.length === 0 ? <EmptyLine text={adminKey ? "Aucune demande en attente." : "Ajoute la clé admin pour voir les demandes."} /> : null}
                {accountRequests.map((request) => (
                  <article className="control-row" key={request.id}>
                    <div>
                      <strong>{request.name}</strong>
                      <p>{request.email} · {request.phone || "pas de téléphone"}</p>
                      <small>{request.source || "site"} · {formatDate(request.created_at)}</small>
                    </div>
                    <button className="control-icon-btn" onClick={() => void markAccountProcessed(request.id)} title="Marquer traité">
                      <CheckCircle2 size={18} />
                    </button>
                  </article>
                ))}
              </div>
            </section>

            <section className="control-panel">
              <div className="control-panel-title">
                <Users size={18} />
                <h2>Demandes de rôle</h2>
              </div>
              <div className="control-list">
                {roleRequests.length === 0 ? <EmptyLine text={adminKey ? "Aucune demande de rôle." : "Clé admin requise."} /> : null}
                {roleRequests.map((request) => (
                  <article className="control-row" key={request.id}>
                    <div>
                      <strong>{request.requested_mode}</strong>
                      <p>Utilisateur {request.user_id}</p>
                      <small>{formatDate(request.created_at)}</small>
                    </div>
                    <a className="control-link" href={`${portalUrl}/admin/role-requests`} target="_blank" rel="noreferrer">Traiter</a>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <section className="control-panel">
              <div className="control-panel-title">
                <Activity size={18} />
                <h2>Soirées en cours et à venir</h2>
              </div>
              <div className="control-list">
                {[...liveEvents, ...nextEvents].slice(0, 10).map((event) => (
                  <article className="control-row" key={event.id}>
                    <div>
                      <strong>{event.name}</strong>
                      <p>{isLive(event) ? "LIVE maintenant" : `Début ${shortDate(event.starts_at)}`}</p>
                      <small>Event #{event.id} · Bar #{event.bar_id ?? "-"}</small>
                    </div>
                    <div className="control-row-actions">
                      <a className="control-link" href={`${portalUrl}/event-control/${event.id}`} target="_blank" rel="noreferrer">Régie</a>
                      <a className="control-link" href={`${portalUrl}/polymarket-admin/${event.id}`} target="_blank" rel="noreferrer">Polymarket</a>
                    </div>
                  </article>
                ))}
                {events.length === 0 ? <EmptyLine text="Aucune soirée chargée." /> : null}
              </div>
            </section>

            <section className="control-panel">
              <div className="control-panel-title">
                <Trophy size={18} />
                <h2>Polymarket</h2>
              </div>
              <div className="control-list">
                {bets.slice(0, 8).map((bet) => (
                  <article className="control-row" key={bet.id}>
                    <div>
                      <strong>{bet.title || bet.question || `Marché #${bet.id}`}</strong>
                      <p>{bet.status || "open"} · {bet.scope || "global"}</p>
                      <small>{bet.event_id ? `Event #${bet.event_id}` : "Global"}</small>
                    </div>
                    <a className="control-link" href={`${portalUrl}/polymarket/${bet.id}`} target="_blank" rel="noreferrer">Ouvrir</a>
                  </article>
                ))}
                {bets.length === 0 ? <EmptyLine text="Aucun marché chargé." /> : null}
              </div>
            </section>
          </div>

          <section className="control-panel">
            <div className="control-panel-title">
              <Gauge size={18} />
              <h2>Raccourcis modules</h2>
            </div>
            <div className="control-shortcuts">
              <Link to="/forum">Forum vitrine</Link>
              <Link to="/profile">Profil</Link>
              <a href={`${portalUrl}/create-orga`} target="_blank" rel="noreferrer">Créer orga</a>
              <a href={`${portalUrl}/orga/create-event`} target="_blank" rel="noreferrer">Créer soirée</a>
              <a href={`${portalUrl}/polymarket`} target="_blank" rel="noreferrer">Polymarket global</a>
              <a href={`${portalUrl}/staff/account-requests`} target="_blank" rel="noreferrer">Demandes staff</a>
              <a href={`${portalUrl}/admin/users`} target="_blank" rel="noreferrer">Utilisateurs</a>
              <a href={`${portalUrl}/dev/status`} target="_blank" rel="noreferrer">Santé technique</a>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function Metric({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: string | number; tone: "gold" | "ruby" | "blue" | "green" }) {
  return (
    <article className={`control-metric control-metric-${tone}`}>
      <div className="control-metric-icon">{icon}</div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <div className="control-empty">{text}</div>;
}
