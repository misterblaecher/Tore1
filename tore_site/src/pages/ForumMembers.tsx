import { FormEvent, useEffect, useMemo, useState } from "react";
import { Ban, Check, Clock3, Copy, Mail, QrCode, RefreshCw, Users } from "lucide-react";
import { useParams } from "react-router-dom";
import { apiFetch, ApiError } from "@/lib/api";
import "@/styles/forum.css";


type Member = {
  id: number;
  userId: string;
  displayName: string;
  email?: string | null;
  role: string;
  status: string;
  mandateLabel?: string | null;
  startsAt?: string | null;
  endsAt?: string | null;
};

type InvitationStatus = "PENDING" | "ACCEPTED" | "DECLINED" | "EXPIRED" | "REVOKED";
type Invitation = {
  id: number;
  email: string;
  invitedRole: string;
  status: InvitationStatus;
  expiresAt?: string | null;
  acceptedAt?: string | null;
  declinedAt?: string | null;
  revokedAt?: string | null;
  createdAt?: string | null;
  inviteUrl?: string;
  qrSvgDataUri?: string;
  deliveryStatus?: string;
};

type MembersResponse = { items: Member[]; canManage: boolean };
type InvitationsResponse = { items: Invitation[]; allowedRoles: string[] };

const DEFAULT_ROLES = ["MEMBER", "STAFF", "SECRETARY", "TREASURER", "BUREAU", "VICE_PRESIDENT", "PRESIDENT"];
const STATUS_LABELS: Record<InvitationStatus, string> = {
  PENDING: "En attente",
  ACCEPTED: "Acceptée",
  DECLINED: "Refusée",
  EXPIRED: "Expirée",
  REVOKED: "Annulée",
};

function dateLabel(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("fr-BE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function actionHeaders() {
  return { "Idempotency-Key": `forum-invite-${Date.now()}-${Math.random().toString(36).slice(2, 9)}` };
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 429) return "Trop d’invitations ont été envoyées récemment. Réessayez plus tard.";
  if (error instanceof ApiError && error.status === 403) return "Votre rôle ne permet pas cette action.";
  return error instanceof ApiError ? error.message : "Une erreur est survenue.";
}

export default function ForumMembersPage() {
  const { slug = "" } = useParams();
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [allowedRoles, setAllowedRoles] = useState<string[]>(DEFAULT_ROLES);
  const [canManage, setCanManage] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [search, setSearch] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");
  const [share, setShare] = useState<Invitation | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const memberData = await apiFetch<MembersResponse>(`/forum/structures/${encodeURIComponent(slug)}/members?include_archived=${includeArchived}`);
      setMembers(memberData.items ?? []);
      setCanManage(Boolean(memberData.canManage));
      if (memberData.canManage) {
        const invitationData = await apiFetch<InvitationsResponse>(`/forum/structures/${encodeURIComponent(slug)}/invitations`);
        setInvitations(invitationData.items ?? []);
        const roles = invitationData.allowedRoles?.length ? invitationData.allowedRoles : DEFAULT_ROLES;
        setAllowedRoles(roles);
        if (!roles.includes(role)) setRole(roles[0] ?? "MEMBER");
      } else {
        setInvitations([]);
      }
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [slug, includeArchived]);

  const filteredMembers = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return members;
    return members.filter((member) => [member.displayName, member.email, member.role, member.mandateLabel].some((value) => (value || "").toLowerCase().includes(needle)));
  }, [members, search]);

  async function sendInvitation(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setCopied(false);
    try {
      const invitation = await apiFetch<Invitation>(`/forum/structures/${encodeURIComponent(slug)}/invitations`, {
        method: "POST",
        headers: actionHeaders(),
        body: JSON.stringify({ email: email.trim().toLowerCase(), invited_role: role }),
      });
      setShare(invitation);
      setEmail("");
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  }

  async function resend(invitation: Invitation) {
    setError(null);
    setCopied(false);
    try {
      const updated = await apiFetch<Invitation>(`/forum/structures/${encodeURIComponent(slug)}/invitations/${invitation.id}/resend`, {
        method: "POST",
        headers: actionHeaders(),
      });
      setShare(updated);
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function revokeInvitation(invitation: Invitation) {
    setError(null);
    try {
      await apiFetch(`/forum/structures/${encodeURIComponent(slug)}/invitations/${invitation.id}/revoke`, {
        method: "POST",
        headers: actionHeaders(),
      });
      if (share?.id === invitation.id) setShare(null);
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function revokeMember(member: Member) {
    setError(null);
    try {
      await apiFetch(`/forum/structures/${encodeURIComponent(slug)}/members/${encodeURIComponent(member.userId)}`, {
        method: "DELETE",
        headers: actionHeaders(),
      });
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }

  async function copyInvite() {
    if (!share?.inviteUrl) return;
    await navigator.clipboard?.writeText(share.inviteUrl);
    setCopied(true);
  }

  return <main className="forum-main">
    <div className="forum-main__head">
      <div><span className="forum-eyebrow">Gouvernance</span><h1>Membres & invitations</h1><p>Invitez une personne par e-mail, lien ou QR. Aucun identifiant de compte n’est nécessaire.</p></div>
      <span className="forum-badge">{canManage ? "Accès gestion" : "Membre actif"}</span>
    </div>

    {error ? <div className="forum-alert">{error}</div> : null}

    <div className="forum-grid-2">
      <section className="forum-card">
        <div className="forum-section-title"><div><span className="forum-eyebrow">Comité</span><h2>Membres</h2></div><Users size={20} /></div>
        <input className="forum-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher par nom, e-mail ou rôle" aria-label="Rechercher un membre" />
        {canManage ? <label className="forum-inline forum-muted"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Afficher les anciens membres</label> : null}
        {loading ? <div className="forum-empty">Chargement…</div> : <div className="forum-list" style={{ marginTop: 14 }}>
          {filteredMembers.length ? filteredMembers.map((member) => <div className="forum-row" key={member.id}>
            <div><strong>{member.displayName}</strong>{member.email ? <small>{member.email}</small> : null}<p>{member.role} · {member.status}{member.mandateLabel ? ` · ${member.mandateLabel}` : ""}</p></div>
            {canManage && member.role !== "OWNER" && member.status === "ACTIVE" ? <button className="forum-button forum-button--ghost forum-danger" onClick={() => void revokeMember(member)}>Révoquer</button> : null}
          </div>) : <div className="forum-empty">Aucun membre à afficher.</div>}
        </div>}
      </section>

      {canManage ? <section className="forum-card">
        <div className="forum-section-title"><div><span className="forum-eyebrow">Invitation</span><h2>Inviter un membre</h2></div><Mail size={20} /></div>
        <p className="forum-muted">Saisissez simplement l’adresse e-mail de la personne. Le lien est temporaire, à usage unique, et peut aussi être partagé sous forme de QR.</p>
        <form className="forum-form" onSubmit={sendInvitation}>
          <label>Adresse e-mail<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="prenom.nom@example.com" /></label>
          <label>Rôle<select value={role} onChange={(event) => setRole(event.target.value)}>{allowedRoles.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
          <button className="forum-button forum-button--primary" type="submit" disabled={submitting}>{submitting ? "Envoi…" : "Envoyer l’invitation"}</button>
        </form>

        {share?.inviteUrl ? <div className="forum-card" style={{ marginTop: 18 }} data-testid="invitation-share">
          <div className="forum-section-title"><div><span className="forum-eyebrow">Lien prêt</span><h3>{share.email}</h3></div><QrCode size={20} /></div>
          <p className="forum-muted">Expire le {dateLabel(share.expiresAt)}. Une relance invalidera immédiatement ce lien.</p>
          {share.qrSvgDataUri ? <img src={share.qrSvgDataUri} alt="QR de l’invitation" style={{ width: 180, height: 180, background: "white", padding: 8, borderRadius: 12 }} /> : null}
          <div className="forum-inline" style={{ marginTop: 12 }}><button className="forum-button forum-button--ghost" type="button" onClick={() => void copyInvite()}>{copied ? <Check size={15} /> : <Copy size={15} />} {copied ? "Copié" : "Copier le lien"}</button><span className="forum-badge">E-mail {share.deliveryStatus || "envoyé"}</span></div>
        </div> : null}
      </section> : null}
    </div>

    {canManage ? <section className="forum-card" style={{ marginTop: 18 }}>
      <div className="forum-section-title"><div><span className="forum-eyebrow">Suivi</span><h2>Invitations</h2></div><Clock3 size={20} /></div>
      <div className="forum-list">{invitations.length ? invitations.map((invitation) => <div className="forum-row" key={invitation.id}>
        <div><strong>{invitation.email}</strong><p>{invitation.invitedRole} · {STATUS_LABELS[invitation.status]}</p><small>{invitation.status === "ACCEPTED" ? `Acceptée le ${dateLabel(invitation.acceptedAt)}` : `Expiration ${dateLabel(invitation.expiresAt)}`}</small></div>
        <div className="forum-inline"><span className={`forum-badge ${["EXPIRED", "REVOKED", "DECLINED"].includes(invitation.status) ? "forum-danger" : ""}`}>{STATUS_LABELS[invitation.status]}</span>{["PENDING", "EXPIRED"].includes(invitation.status) ? <button className="forum-button forum-button--ghost" onClick={() => void resend(invitation)}><RefreshCw size={14} /> Relancer</button> : null}{invitation.status === "PENDING" ? <button className="forum-button forum-button--ghost forum-danger" onClick={() => void revokeInvitation(invitation)}><Ban size={14} /> Annuler</button> : null}</div>
      </div>) : <div className="forum-empty">Aucune invitation envoyée.</div>}</div>
    </section> : null}
  </main>;
}
