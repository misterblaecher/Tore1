import { useEffect, useState } from "react";
import { CheckCircle2, Clock3, LogIn, ShieldCheck, XCircle } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { apiFetch, ApiError } from "@/lib/api";
import "@/styles/forum.css";


type InvitationPreview = {
  structure: { name: string; slug: string; logoUrl?: string | null };
  emailMasked: string;
  invitedRole: string;
  status: "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED" | "REVOKED";
  expiresAt: string;
};

type AcceptResponse = { ok: boolean; status: "ACCEPTED"; structure: { slug: string; name: string }; role: string };

const STATUS_COPY: Record<InvitationPreview["status"], string> = {
  PENDING: "Cette invitation est prête à être utilisée.",
  ACCEPTED: "Cette invitation a déjà été acceptée.",
  DECLINED: "Cette invitation a été refusée.",
  EXPIRED: "Cette invitation a expiré. Demandez une relance à la structure.",
  REVOKED: "Cette invitation a été annulée par la structure.",
};

export default function ForumInvitationPage() {
  const { token = "" } = useParams();
  const [preview, setPreview] = useState<InvitationPreview | null>(null);
  const [accepted, setAccepted] = useState<AcceptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<"accept" | "decline" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [needsLogin, setNeedsLogin] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void apiFetch<InvitationPreview>(`/forum/invitations/${encodeURIComponent(token)}`)
      .then((data) => { if (active) setPreview(data); })
      .catch(() => { if (active) setMessage("Ce lien d’invitation n’est plus disponible."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);

  async function accept() {
    setAction("accept"); setMessage(null); setNeedsLogin(false);
    try {
      const result = await apiFetch<AcceptResponse>(`/forum/invitations/${encodeURIComponent(token)}/accept`, { method: "POST" });
      setAccepted(result);
      setPreview((current) => current ? { ...current, status: "ACCEPTED" } : current);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        setNeedsLogin(true);
        setMessage("Connectez-vous avec l’adresse e-mail invitée, puis revenez sur ce lien.");
      } else if (reason instanceof ApiError && reason.status === 403) {
        setMessage("Le compte connecté n’utilise pas l’adresse e-mail ciblée par cette invitation.");
      } else {
        setMessage("Cette invitation ne peut plus être acceptée.");
      }
    } finally { setAction(null); }
  }

  async function decline() {
    setAction("decline"); setMessage(null);
    try {
      await apiFetch(`/forum/invitations/${encodeURIComponent(token)}/decline`, { method: "POST" });
      setPreview((current) => current ? { ...current, status: "DECLINED" } : current);
      setMessage("Invitation refusée.");
    } catch {
      setMessage("Cette invitation ne peut plus être refusée.");
    } finally { setAction(null); }
  }

  if (loading) return <main className="forum-main"><div className="forum-empty">Chargement de l’invitation…</div></main>;

  return <main className="forum-main" style={{ maxWidth: 760, marginInline: "auto" }}>
    <section className="forum-card">
      <div className="forum-section-title"><div><span className="forum-eyebrow">Invitation membre</span><h1>{preview?.structure.name || "Invitation TORÈ"}</h1></div><ShieldCheck size={24} /></div>
      {preview ? <>
        <p>Invitation pour <strong>{preview.emailMasked}</strong> avec le rôle <strong>{preview.invitedRole}</strong>.</p>
        <div className="forum-inline"><span className="forum-badge">{preview.status}</span><span className="forum-muted"><Clock3 size={14} /> expire le {new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(preview.expiresAt))}</span></div>
        <p className="forum-muted" style={{ marginTop: 14 }}>{STATUS_COPY[preview.status]}</p>
      </> : null}

      {message ? <div className="forum-alert" style={{ marginTop: 16 }}>{message}</div> : null}

      {accepted ? <div style={{ marginTop: 18 }}><div className="forum-inline"><CheckCircle2 size={19} /><strong>Vous avez rejoint {accepted.structure.name}.</strong></div><Link className="forum-button forum-button--primary" style={{ marginTop: 12 }} to={`/forum/structures/${accepted.structure.slug}/dashboard`}>Ouvrir l’espace structure</Link></div> : null}

      {preview?.status === "PENDING" && !accepted ? <div className="forum-inline" style={{ marginTop: 18 }}>
        <button className="forum-button forum-button--primary" disabled={action !== null} onClick={() => void accept()}><CheckCircle2 size={15} /> {action === "accept" ? "Acceptation…" : "Accepter"}</button>
        <button className="forum-button forum-button--ghost forum-danger" disabled={action !== null} onClick={() => void decline()}><XCircle size={15} /> {action === "decline" ? "Refus…" : "Refuser"}</button>
      </div> : null}

      {needsLogin ? <Link className="forum-button forum-button--ghost" style={{ marginTop: 12 }} to="/forum/login" state={{ from: `/forum/invite/${token}` }}><LogIn size={15} /> Se connecter</Link> : null}
    </section>
  </main>;
}
