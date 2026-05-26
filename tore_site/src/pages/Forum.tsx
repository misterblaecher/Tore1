import { Link } from "react-router-dom";
import type { CSSProperties } from "react";

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
  const channels = [
    ["# annonces", "Page publique et annonces importantes"],
    ["# staff-event", "QR pack, rôles terrain, checklists"],
    ["# comité-privé", "Discussion interne et passation"],
    ["# modération", "Demandes, accès, signalements"],
  ];
  const posts = [
    ["Prochaine guindaille", "TD Outremeuse · vendredi 22:30 · QR join activé"],
    ["Dernier event TORÈ", "Afond Night · 244 entrées · recap post-event publié"],
    ["Appel staff", "Besoin de 4 personnes entrée + 2 bar runners"],
  ];

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
          <Link to="/profile" style={{ ...pill, textDecoration: "none" }}>Profil</Link>
        </div>

        <div style={{ ...card, background: "linear-gradient(135deg,#261018,#121217)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
            <div>
              <h2 style={{ marginTop: 0 }}>Comité Saint-Torè</h2>
              <p style={{ color: "#ccc" }}>
                Page publique : description, bannière, prochaines soirées, liens utiles et membres visibles selon confidentialité.
              </p>
            </div>
            <span style={{ ...pill, background: "#BA1733" }}>PUBLIC</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
            {[
              ["12", "soirées"],
              ["244", "entrées"],
              ["68%", "participation bets"],
            ].map(([value, label]) => (
              <div key={label} style={{ ...card, background: "#050506", padding: 12 }}>
                <strong style={{ fontSize: 24 }}>{value}</strong>
                <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.4fr .9fr", gap: 14 }}>
          <section style={card}>
            <h2>Fil public</h2>
            <p style={{ color: "#bbb" }}>Une page façon réseau social : événements, annonces, souvenirs et liens utiles.</p>
            <div style={{ display: "grid", gap: 10 }}>
              {posts.map(([title, body]) => (
                <article key={title} style={{ ...card, background: "#050506", padding: 14 }}>
                  <strong>{title}</strong>
                  <p style={{ color: "#aaa", marginBottom: 0 }}>{body}</p>
                </article>
              ))}
            </div>
          </section>

          <section style={card}>
            <h2>Salons privés</h2>
            <p style={{ color: "#bbb" }}>Groupes de discussion type Discord, avec accès selon fonctions et grades.</p>
            {channels.map(([title, body]) => (
              <div key={title} style={{ borderTop: "1px solid #2A2631", padding: "10px 0" }}>
                <strong>{title}</strong>
                <div style={{ color: "#999", fontSize: 13 }}>{body}</div>
              </div>
            ))}
          </section>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 14 }}>
          <section style={card}>
            <h2>Demande de création</h2>
            <p style={{ color: "#bbb" }}>Comité, ordre, régionale ou rivageoise. Une demande acceptée crée l’espace officiel.</p>
            <div style={{ display: "grid", gap: 8, marginBottom: 12 }}>
              <input placeholder="Nom du comité / cercle / ordre" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff" }} />
              <textarea placeholder="Description et justification" style={{ padding: 12, borderRadius: 8, border: "1px solid #2A2631", background: "#050506", color: "#fff", minHeight: 90 }} />
            </div>
            <button style={{ background: "#BA1733", color: "#fff", border: 0, borderRadius: 8, padding: "12px 14px", fontWeight: 800 }}>
              Soumettre une demande
            </button>
          </section>

          <section style={card}>
            <h2>Gestion responsable</h2>
            <ul style={{ color: "#bbb", lineHeight: 1.8 }}>
              <li>Modifier les informations et la bannière</li>
              <li>Gérer les membres et accès</li>
              <li>Attribuer fonctions, rôles et grades</li>
              <li>Définir les permissions</li>
            </ul>
          </section>

          <section style={card}>
            <h2>Stats événement</h2>
            <ul style={{ color: "#bbb", lineHeight: 1.8 }}>
              <li>Entrées, activité et modules activés</li>
              <li>Tickets, ventes et commandes</li>
              <li>Bets, hunts, battles et recap post-event</li>
              <li>Historique des soirées organisées</li>
            </ul>
          </section>
        </div>
      </section>
    </main>
  );
}
