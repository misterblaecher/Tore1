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
  border: "1px solid #2A2631",
  borderRadius: 6,
  padding: "5px 9px",
  color: "#fff",
  fontSize: 12,
  fontWeight: 800,
  textDecoration: "none",
};

const embuscadeMap = "https://maps.app.goo.gl/5tsL5yu1XdKA25js6";

export default function ForumPublicPage() {
  const events = [
    ["TD Outremeuse", "Ce soir · 22:30 · L’Embuscade · QR join actif"],
    ["Afond Night", "244 entrées · recap post-event publié"],
    ["Saint-Torè warmup", "Vendredi · staff en préparation"],
  ];
  const bars = [
    ["L’Embuscade", "450 m · ouvert · 2 soirées cette semaine", embuscadeMap],
    ["TORÈ Test Bar", "700 m · live · menu TORÈ actif", "https://www.google.com/maps/search/?api=1&query=Li%C3%A8ge%20bar"],
    ["Bar B", "900 m · happy hour · 1 event", "https://www.google.com/maps/search/?api=1&query=Li%C3%A8ge%20bar%20B"],
  ];

  return (
    <main style={{ minHeight: "100vh", background: "#050506", color: "#fff", padding: "88px 24px 32px" }}>
      <section style={{ maxWidth: 1080, margin: "0 auto", display: "grid", gap: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <p style={{ margin: 0, color: "#F4C430", fontWeight: 900 }}>Forum public TORÈ</p>
            <h1 style={{ margin: "6px 0", fontSize: 40 }}>Comité Saint-Torè</h1>
            <p style={{ color: "#bbb", maxWidth: 680 }}>
              Page publique du comité : soirées, bars partenaires, liens utiles, membres visibles et stats TORÈ.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Link to="/studio" style={{ ...pill, borderColor: "#F4C430", color: "#F4C430" }}>Créer un comité/event</Link>
            <Link to="/forum" style={{ ...pill, borderColor: "#BA1733", background: "#BA1733" }}>Gérer le forum</Link>
          </div>
        </div>

        <section style={{ ...card, background: "linear-gradient(135deg,#261018,#121217)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: 10 }}>
            {[["3", "events publics"], ["244", "entrées dernier event"], ["18", "membres visibles"], ["4", "salons privés"]].map(([value, label]) => (
              <div key={label} style={{ ...card, background: "#050506", padding: 12 }}>
                <strong style={{ fontSize: 26 }}>{value}</strong>
                <div style={{ color: "#999", fontSize: 12 }}>{label}</div>
              </div>
            ))}
          </div>
        </section>

        <div style={{ display: "grid", gridTemplateColumns: "1.35fr .95fr", gap: 14 }}>
          <section style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <h2 style={{ marginTop: 0 }}>Soirées près de toi</h2>
              <span style={{ ...pill, color: "#F4C430" }}>Liège</span>
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              {events.map(([title, body]) => (
                <article key={title} style={{ ...card, background: "#050506", padding: 14 }}>
                  <strong>{title}</strong>
                  <p style={{ color: "#aaa", marginBottom: 0 }}>{body}</p>
                </article>
              ))}
            </div>
          </section>

          <section style={card}>
            <h2 style={{ marginTop: 0 }}>Bars partenaires</h2>
            {bars.map(([name, meta, url]) => (
              <div key={name} style={{ borderTop: "1px solid #2A2631", padding: "12px 0", display: "grid", gap: 6 }}>
                <strong>{name}</strong>
                <span style={{ color: "#999", fontSize: 13 }}>{meta}</span>
                <a href={url} target="_blank" rel="noreferrer" style={{ ...pill, width: "fit-content", borderColor: "#F4C430", color: "#F4C430" }}>
                  Google Maps
                </a>
              </div>
            ))}
          </section>
        </div>

        <section style={card}>
          <h2 style={{ marginTop: 0 }}>Forum lié à TORÈ</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(210px,1fr))", gap: 10 }}>
            {[
              ["Fil public", "Annonces, events, souvenirs et liens utiles."],
              ["Gestion event", "QR join, menu, staff, tickets, bets et recap."],
              ["Salons privés", "Espaces type Discord selon rôles et permissions."],
              ["Stats", "Entrées, activité, modules activés et historique."],
            ].map(([title, body]) => (
              <article key={title} style={{ ...card, background: "#050506" }}>
                <strong>{title}</strong>
                <p style={{ color: "#aaa", marginBottom: 0 }}>{body}</p>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}
