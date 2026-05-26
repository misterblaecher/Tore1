import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "@/lib/api";

type OrgaCreateOut = {
  orga: { id: number; name: string; city?: string | null; org_type?: string | null };
  role: string;
  status: string;
};

type EventCreateOut = {
  event_id: number;
  name: string;
  event_code?: string;
  modulesOn?: Record<string, boolean>;
  share?: { deeplink?: string; webUrl?: string; qr_payload_join?: string };
};

const modules = [
  ["entry", "Entrées", "Scan QR, jauge, refus, staff entrée"],
  ["menu", "Menu", "Carte bar, commandes, ruptures"],
  ["wallet", "Wallet", "Cashless, top-up, remboursements"],
  ["dj", "DJ", "Votes musique, file de morceaux, annonce live"],
  ["battles", "Battles", "Défis, scores, classement"],
  ["hunt", "Hunts", "Indices, validation, progression"],
  ["safety", "Safe Kit", "Buddy, départ, contacts urgence"],
] as const;

const card = {
  background: "#121217",
  border: "1px solid #2A2631",
  borderRadius: 8,
  padding: 18,
};

const field = {
  background: "#050506",
  color: "#fff",
  border: "1px solid #2A2631",
  borderRadius: 8,
  padding: "11px 12px",
};

const primaryButton = {
  background: "#BA1733",
  color: "#fff",
  border: 0,
  borderRadius: 8,
  padding: "12px 14px",
  fontWeight: 900,
};

export default function CommitteeStudioPage() {
  const [orgaName, setOrgaName] = useState("Comité Saint-Torè");
  const [orgaType, setOrgaType] = useState("comité");
  const [city, setCity] = useState("Liège");
  const [description, setDescription] = useState("Espace officiel du comité pour organiser les soirées TORÈ.");
  const [orga, setOrga] = useState<OrgaCreateOut | null>(null);
  const [eventName, setEventName] = useState("TD Outremeuse");
  const [venue, setVenue] = useState("L’Embuscade");
  const [event, setEvent] = useState<EventCreateOut | null>(null);
  const [activeModules, setActiveModules] = useState<Record<string, boolean>>({
    entry: true,
    menu: true,
    wallet: true,
    dj: true,
    battles: false,
    hunt: false,
    safety: true,
  });
  const [ops, setOps] = useState({ entries: 244, orders: 31, djVotes: 86, staff: 12, alerts: 1 });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitCommittee(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const created = await apiFetch<OrgaCreateOut>("/orgas", {
        method: "POST",
        headers: { "Idempotency-Key": `studio-orga-${orgaName}-${city}` },
        body: JSON.stringify({
          name: orgaName,
          description,
          city,
          org_type: orgaType,
          visibility: "PUBLIC",
          join_mode: "REQUEST_TO_JOIN",
        }),
      });
      setOrga(created);
      setMessage("Demande acceptée : l’espace comité est créé et lié à ton compte.");
    } catch {
      setMessage("Mode démo : comité prêt localement. Connecte-toi au backend pour persister la demande.");
      setOrga({ orga: { id: 1, name: orgaName, city, org_type: orgaType }, role: "OWNER", status: "ACTIVE" });
    } finally {
      setLoading(false);
    }
  }

  async function createEvent(e: FormEvent) {
    e.preventDefault();
    if (!orga) {
      setMessage("Crée d’abord l’espace comité.");
      return;
    }
    setLoading(true);
    setMessage("");
    const start = new Date(Date.now() + 2 * 60 * 60 * 1000);
    const end = new Date(Date.now() + 7 * 60 * 60 * 1000);
    try {
      const created = await apiFetch<EventCreateOut>("/events", {
        method: "POST",
        headers: { "Idempotency-Key": `studio-event-${orga.orga.id}-${eventName}` },
        body: JSON.stringify({
          name: eventName,
          starts_at: start.toISOString(),
          ends_at: end.toISOString(),
          city,
          venue: { name: venue, address: city },
          visibility: "PUBLIC",
          host_type: "orga",
          host_id: String(orga.orga.id),
          modulesOn: activeModules,
          rulesFlags: { consent_required: true, safe_kit_visible: true },
        }),
      });
      setEvent(created);
      setMessage("Event créé : tu peux maintenant gérer la soirée TORÈ.");
    } catch {
      setEvent({ event_id: 1001, name: eventName, event_code: "DEMO42", modulesOn: activeModules });
      setMessage("Mode démo : event créé localement pour le showcase.");
    } finally {
      setLoading(false);
    }
  }

  async function toggleModule(key: string) {
    const next = { ...activeModules, [key]: !activeModules[key] };
    setActiveModules(next);
    if (!event) return;
    try {
      await apiFetch(`/events/${event.event_id}/config`, {
        method: "PATCH",
        body: JSON.stringify({
          entry_enabled: next.entry,
          menu_enabled: next.menu,
          wallet_enabled: next.wallet,
          battles_enabled: next.battles,
          hunt_enabled: next.hunt,
          report_enabled: true,
        }),
      });
    } catch {
      setMessage("Module mis à jour en local pour la démo.");
    }
  }

  return (
    <main style={{ minHeight: "100vh", background: "#050506", color: "#fff", padding: "88px 24px 32px" }}>
      <section style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <p style={{ color: "#F4C430", margin: 0, fontWeight: 900 }}>Studio Comité TORÈ</p>
            <h1 style={{ margin: "6px 0", fontSize: 38 }}>Créer, publier et piloter une soirée</h1>
            <p style={{ color: "#bbb", maxWidth: 760 }}>
              Le parcours compte connecté : demande de comité, event lié, modules TORÈ, entrée, DJ, bar, safe kit et recap.
            </p>
          </div>
          <Link to="/forum/public" style={{ color: "#F4C430", textDecoration: "none", fontWeight: 800 }}>Voir la page publique</Link>
        </div>

        {message ? <div style={{ ...card, borderColor: "#F4C430", color: "#F4C430" }}>{message}</div> : null}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(310px,1fr))", gap: 14 }}>
          <form onSubmit={submitCommittee} style={card}>
            <h2 style={{ marginTop: 0 }}>1. Demande de comité</h2>
            <div style={{ display: "grid", gap: 10 }}>
              <input style={field} value={orgaName} onChange={(e) => setOrgaName(e.target.value)} placeholder="Nom du comité" />
              <select style={field} value={orgaType} onChange={(e) => setOrgaType(e.target.value)}>
                <option value="comité">Comité</option>
                <option value="cercle">Cercle</option>
                <option value="ordre">Ordre</option>
                <option value="régionale">Régionale</option>
                <option value="rivageoise">Rivageoise</option>
              </select>
              <input style={field} value={city} onChange={(e) => setCity(e.target.value)} placeholder="Ville" />
              <textarea style={{ ...field, minHeight: 84 }} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description publique" />
              <button style={primaryButton} disabled={loading}>{orga ? "Espace créé" : "Soumettre la demande"}</button>
            </div>
          </form>

          <form onSubmit={createEvent} style={{ ...card, opacity: orga ? 1 : 0.58 }}>
            <h2 style={{ marginTop: 0 }}>2. Créer l’event</h2>
            <div style={{ display: "grid", gap: 10 }}>
              <input style={field} value={eventName} onChange={(e) => setEventName(e.target.value)} placeholder="Nom de la soirée" />
              <input style={field} value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="Lieu" />
              <button style={primaryButton} disabled={loading || !orga}>{event ? "Event créé" : "Créer avec ce comité"}</button>
            </div>
          </form>
        </div>

        <section style={card}>
          <h2 style={{ marginTop: 0 }}>3. Modules de soirée</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
            {modules.map(([key, label, body]) => (
              <button
                key={key}
                onClick={() => void toggleModule(key)}
                style={{
                  textAlign: "left",
                  background: activeModules[key] ? "#241808" : "#050506",
                  color: "#fff",
                  border: `1px solid ${activeModules[key] ? "#F4C430" : "#2A2631"}`,
                  borderRadius: 8,
                  padding: 14,
                }}
              >
                <strong>{activeModules[key] ? "ON · " : "OFF · "}{label}</strong>
                <p style={{ color: "#aaa", marginBottom: 0 }}>{body}</p>
              </button>
            ))}
          </div>
        </section>

        <section style={card}>
          <h2 style={{ marginTop: 0 }}>4. Régie live TORÈ</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10 }}>
            {[
              ["Entrées", ops.entries, () => setOps({ ...ops, entries: ops.entries + 1 })],
              ["Commandes bar", ops.orders, () => setOps({ ...ops, orders: ops.orders + 1 })],
              ["Votes DJ", ops.djVotes, () => setOps({ ...ops, djVotes: ops.djVotes + 5 })],
              ["Staff actif", ops.staff, () => setOps({ ...ops, staff: ops.staff + 1 })],
              ["Alertes safe", ops.alerts, () => setOps({ ...ops, alerts: Math.max(0, ops.alerts - 1) })],
            ].map(([label, value, action]) => (
              <button key={String(label)} onClick={action as () => void} style={{ ...card, background: "#050506", color: "#fff", textAlign: "left" }}>
                <strong style={{ fontSize: 28 }}>{String(value)}</strong>
                <div style={{ color: "#999" }}>{String(label)}</div>
              </button>
            ))}
          </div>
          <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
            <article style={{ ...card, background: "#050506" }}>
              <strong>Entrée staff</strong>
              <p style={{ color: "#aaa" }}>Scan QR, validation, refus motivé, jauge live.</p>
              <button style={primaryButton} onClick={() => setOps({ ...ops, entries: ops.entries + 1 })}>Valider une entrée</button>
            </article>
            <article style={{ ...card, background: "#050506" }}>
              <strong>DJ booth</strong>
              <p style={{ color: "#aaa" }}>Votes musique, file de morceaux, annonce au ticker.</p>
              <button style={primaryButton} onClick={() => setOps({ ...ops, djVotes: ops.djVotes + 5 })}>Ajouter 5 votes</button>
            </article>
            <article style={{ ...card, background: "#050506" }}>
              <strong>Bar & commandes</strong>
              <p style={{ color: "#aaa" }}>Commandes live, ruptures, wallet et tickets utilisés.</p>
              <button style={primaryButton} onClick={() => setOps({ ...ops, orders: ops.orders + 1 })}>Nouvelle commande</button>
            </article>
            <article style={{ ...card, background: "#050506" }}>
              <strong>Safe kit</strong>
              <p style={{ color: "#aaa" }}>Buddy system, départ accompagné, alerte discrète.</p>
              <button style={primaryButton} onClick={() => setOps({ ...ops, alerts: ops.alerts + 1 })}>Créer une alerte</button>
            </article>
          </div>
          {event ? (
            <div style={{ marginTop: 14, display: "grid", gap: 6, color: "#bbb" }}>
              <strong style={{ color: "#fff" }}>{event.name} · event #{event.event_id}</strong>
              <span>Code event : {event.event_code || "généré après publication"}</span>
              <span>QR join : {event.share?.qr_payload_join || `tore://join?event_id=${event.event_id}`}</span>
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
