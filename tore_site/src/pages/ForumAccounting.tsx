import { Download, LockKeyhole, WalletCards } from "lucide-react";
import { useParams } from "react-router-dom";
import { useStructureResource } from "@/hooks/use-structure-resource";
import { ApiError } from "@/lib/api";
import "@/styles/forum.css";

type AccountingRow = {
  event: { id: number; name: string; startsAt?: string | null; endsAt?: string | null; venue?: string | null };
  revenueCents: number;
  costsCents: number;
  resultCents: number;
};
type AccountingSummary = {
  role: string;
  currency: string;
  privateByDefault: boolean;
  latest?: AccountingRow | null;
  history: AccountingRow[];
  totals: { revenueCents: number; costsCents: number; resultCents: number };
};

function money(cents: number) { return `${(cents / 100).toLocaleString("fr-BE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`; }
function dateLabel(value?: string | null) { return value && !Number.isNaN(Date.parse(value)) ? new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium" }).format(new Date(value)) : "Date à confirmer"; }
function csvCell(value: string | number) { const text = String(value ?? ""); return `"${text.replace(/"/g, '""')}"`; }

export default function ForumAccountingPage() {
  const { slug = "" } = useParams();
  const { data, error, loading, reload } = useStructureResource<AccountingSummary>(`/forum/structures/${encodeURIComponent(slug)}/accounting-summary`);

  function exportCsv() {
    if (!data) return;
    const rows = [
      ["Événement", "Date", "Recettes (€)", "Coûts (€)", "Résultat (€)"],
      ...data.history.map(item => [item.event.name, dateLabel(item.event.startsAt), (item.revenueCents / 100).toFixed(2), (item.costsCents / 100).toFixed(2), (item.resultCents / 100).toFixed(2)]),
    ];
    const blob = new Blob([rows.map(row => row.map(csvCell).join(";")).join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `tore-${slug}-comptabilite.csv`; anchor.click(); URL.revokeObjectURL(url);
  }

  if (loading) return <main className="forum-main"><div className="forum-empty">Chargement de la comptabilité…</div></main>;
  if (error || !data) return <main className="forum-main"><div className="forum-alert" role="alert">{error instanceof ApiError && error.status === 403 ? "La comptabilité est réservée aux rôles Trésorerie, Bureau autorisé ou administrateurs de la structure." : "Impossible de charger la comptabilité."}</div><button className="forum-button forum-button--ghost" onClick={reload}>Réessayer</button></main>;

  return <main className="forum-main">
    <div className="forum-main__head"><div><span className="forum-eyebrow">Trésorerie · privé par défaut</span><h1>Comptabilité</h1><p>Lecture financière séparée des statistiques opérationnelles. Les montants sont autorisés côté serveur.</p></div><button className="forum-button forum-button--primary" onClick={exportCsv}><Download size={15} /> Exporter CSV</button></div>
    <div className="forum-grid-2">
      <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Dernier événement</span><h2>{data.latest?.event.name || "Aucun événement"}</h2></div><WalletCards size={20} /></div>{data.latest ? <div className="forum-metrics"><div className="forum-metric"><span>Recettes</span><strong>{money(data.latest.revenueCents)}</strong></div><div className="forum-metric"><span>Coûts</span><strong>{money(data.latest.costsCents)}</strong></div><div className="forum-metric"><span>Résultat</span><strong>{money(data.latest.resultCents)}</strong></div></div> : <div className="forum-empty">Aucune donnée financière liée à un événement.</div>}</section>
      <section className="forum-card"><div className="forum-section-title"><div><span className="forum-eyebrow">Périmètre chargé</span><h2>Total historique</h2></div><LockKeyhole size={20} /></div><div className="forum-metrics"><div className="forum-metric"><span>Recettes</span><strong>{money(data.totals.revenueCents)}</strong></div><div className="forum-metric"><span>Coûts</span><strong>{money(data.totals.costsCents)}</strong></div><div className="forum-metric"><span>Résultat</span><strong>{money(data.totals.resultCents)}</strong></div></div><p className="forum-muted">Ces chiffres ne sont pas exposés par la page publique du Forum.</p></section>
    </div>
    <section className="forum-card" style={{ marginTop: 18 }}><div className="forum-section-title"><div><span className="forum-eyebrow">Comparaison</span><h2>Événements récents</h2></div></div>{data.history.length ? <div className="forum-list">{data.history.map(item => <div className="forum-row" key={item.event.id}><div><strong>{item.event.name}</strong><p>{dateLabel(item.event.startsAt)}{item.event.venue ? ` · ${item.event.venue}` : ""}</p></div><div className="forum-inline"><span className="forum-badge">Recettes {money(item.revenueCents)}</span><span className="forum-badge">Coûts {money(item.costsCents)}</span><strong>{money(item.resultCents)}</strong></div></div>)}</div> : <div className="forum-empty">Aucun événement à comparer.</div>}</section>
    <section className="forum-card" style={{ marginTop: 18 }}><span className="forum-eyebrow">À compléter</span><h2>Pièces justificatives, validation et verrouillage</h2><p className="forum-muted">Les documents peuvent déjà être liés aux événements avec une visibilité Trésorerie, mais le workflow comptable de validation/verrouillage et l’export PDF signé ne sont pas encore implémentés. Cette page ne les présente donc pas comme opérationnels.</p></section>
  </main>;
}
