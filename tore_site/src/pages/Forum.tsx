import { Link } from "react-router-dom";
import type { CSSProperties } from "react";
import { useState } from "react";

const card: CSSProperties = {
  background: "#121217",
  border: "1px solid #2A2631",
  borderRadius: 8,
  padding: 18,
};

const pill: CSSProperties = {
  display: "inline-flex",
  border: "1px solid #BA1733",
  borderRadius: 6,
  padding: "4px 8px",
  color: "#fff",
  fontSize: 12,
  fontWeight: 700,
};

export default function ForumPage() {
  const [spaceType, setSpaceType] = useState("Comité");
  const [forumName, setForumName] = useState("Comité Saint-Torè");
  const [description, setDescription] = useState(
    "Page publique : description, bannière, prochaines soirées, liens utiles et membres visibles selon confidentialité.",
  );
  const [activePanel, setActivePanel] = useState("Créer");
  const [events, setEvents] = useState([
    ["Afond Night", "244 entrées · menu + bets + safe kit"],
    ["Saint-Torè warmup", "Vendredi 22:30 · QR join activé"],
  ]);
  const [eventName, setEventName] = useState("TD Outremeuse");
  const [eventMeta, setEventMeta] = useState("Vendredi 22:30 · Liège");

  const channels = [
    ["# annonces", "Page publique et annonces importantes"],
    ["# staff-event", "QR pack, rôles terrain, checklists"],
    ["# comité-privé", "Discussion interne et passation"],
    ["# modération", "Demandes, accès, signalements"],
  ];
  const createForum = () => {
    setForumName(forumName.trim() || `Nouveau ${spaceType} TORÈ`);
    setActivePanel("Gérer");
  };

  const createEvent = () => {
    const title = eventName.trim();
    if (!title) return;
    setEvents([[title, `${eventMeta || "Date à confirmer"} · brouillon TORÈ`], ...events]);
    setActivePanel("Events");
  };

  return (
    <main style={{ minHeight: "100vh", background: "#050506", color: "#fff", padding: 24 }}>
      <section style={{ maxWidth: 1040, margin: "0 auto", display: "grid", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <div>
            <p style={{ color: "#F4C430", margin: 0, fontWeight: 800 }}>TORÈ Forum</p>
            <h1 style={{ margin: "6px 0", fontSize: 38 }}>Espaces officiels des comités</h1>
            <p style={{ color: "#bbb", maxWidth: 680 }}>
              Créez, modérez et reliez les forums de comités, ordres, régionales et rivageoises aux événements TORÈ.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link to="/forum/public" style={{ ...pill, borderColor: "#F4C430", color: "#F4C430" }}>Page publique</Link>
            <Link to="/studio" style={{ ...pill, borderColor: "#F4C430", color: "#F4C430" }}>Studio event</Link>
            <Link to="/profile" style={{ ...pill, textDecoration: "none" }}>Profil</Link>
          </div>
        </div>

        <div style={{ ...card, background: "linear-gradient(135deg,#261018,#121217)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
            <div>
              <h2 style={{ marginTop: 0 }}>{forumName}</h2>
              <p style={{ color: "#ccc" }}>{description}</p>
            </div>
            <span style={{ ...pill, background: "#BA1733" }}>PUBLIC</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              [String(events.length), "events"],
              ["244", "entrées"],
              ["18", "membres"],
            ].map(([value, label]) => (
              <div key={label} style={{ ...card, background: "#050506", padding: 12 }}>
                <strong style={{ fontSize: 24 }}>{value}</strong>
                <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {["Créer", "Gérer", "Events", "Salons"].map((panel) => (
            <button
              key={panel}
              onClick={() => setActivePanel(panel)}
              style={{
                ...pill,
                borderColor: activePanel === panel ? "#F4C430" : "#2A2631",
                background: activePanel === panel ? "#241808" : "#121217",
              }}
            >
              {panel}
            </button>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.3fr .9fr", gap: 14 }}>
          <section style={card}>
            <h2>Fil public</h2>
            <p style={{ color: "#bbb" }}>Une page façon réseau social : événements, annonces, souvenirs et liens utiles.</p>
            <div style={{ display: "grid", gap: 10 }}>
              {[...events, ["Appel staff", "Besoin de 4 personnes entrée + 2 bar runners"]].map(([title, body]) => (
                <article key={title} style={{ ...card, background: "#050506", padding: 14 }}>
                  <strong>{title}</strong>
                  <p style={{ color: "#aaa", marginBottom: 0 }}>{body}</p>
                </article>
              ))}
            </div>
          </section>

          <section style={card}>
            {activePanel === "Créer" && (
              <>
                <h2>Demande de création</h2>
                <p style={{ color: "#bbb" }}>Comité, cercle, ordre, régionale, rivageoise ou autre espace officiel.</p>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                  {["Comité", "Cercle", "Ordre", "Régionale", "Rivageoise", "Autre"].map((type) => (
                    <button key={type} onClick={() => setSpaceType(type)} style={{ ...pill, borderColor: spaceType === type ? "#F4C430" : "#2A2631" }}>
                      {type}
                    </button>
                  ))}
                </div>
                <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
                  <input value={forumName} onChange={(event) => setForumName(event.target.value)} placeholder="Nom du comité / cercle / ordre" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff" }} />
                  <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description et justification" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff", minHeight: 90 }} />
                </div>
                <button onClick={createForum} style={{ background: "#BA1733", color: "#fff", border: 0, borderRadius: 8, padding: "12px 14px", fontWeight: 800 }}>
                  Créer l’espace
                </button>
              </>
            )}
            {activePanel === "Gérer" && (
              <>
                <h2>Gestion responsable</h2>
                {["Modifier infos et bannière", "Inviter ou retirer des membres", "Attribuer fonctions, rôles et grades", "Définir permissions et accès"].map((item) => (
                  <div key={item} style={{ borderTop: "1px solid #2A2631", padding: "12px 0" }}>{item}</div>
                ))}
              </>
            )}
            {activePanel === "Events" && (
              <>
                <h2>Créer un event</h2>
                <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
                  <input value={eventName} onChange={(event) => setEventName(event.target.value)} placeholder="Nom de l’event" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff" }} />
                  <input value={eventMeta} onChange={(event) => setEventMeta(event.target.value)} placeholder="Date · lieu" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff" }} />
                </div>
                <button onClick={createEvent} style={{ background: "#BA1733", color: "#fff", border: 0, borderRadius: 8, padding: "12px 14px", fontWeight: 800 }}>
                  Ajouter au forum
                </button>
              </>
            )}
            {activePanel === "Salons" && (
              <>
                <h2>Salons privés</h2>
                <p style={{ color: "#bbb" }}>Groupes type Discord, avec accès selon fonctions et grades.</p>
                {channels.map(([title, body]) => (
                  <div key={title} style={{ borderTop: "1px solid #2A2631", padding: "10px 0" }}>
                    <strong>{title}</strong>
                    <div style={{ color: "#999", fontSize: 13 }}>{body}</div>
                  </div>
                ))}
              </>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
