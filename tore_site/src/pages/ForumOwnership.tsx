import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, KeyRound, RefreshCw, ShieldCheck, UserRoundCheck } from "lucide-react";

import { ApiError, apiFetch } from "@/lib/api";
import "@/styles/forum.css";

type PendingTransfer = {
  id: number;
  status: string;
  fromUserId: string;
  toUserId: string;
  requestedAt: string;
  expiresAt: string;
  canConfirm: boolean;
  canCancel: boolean;
};

type PendingRecovery = {
  id: number;
  status: string;
  requestedByUserId: string;
  reason: string;
  requestedAt: string;
  canApprove: boolean;
};

type OwnershipState = {
  structureId: number;
  slug: string;
  viewerUserId: string;
  primaryOwnerUserId: string;
  recoveryOwnerUserId?: string | null;
  capabilities: string[];
  frozen: boolean;
  keepPublicVisible: boolean;
  frozenReason?: string | null;
  pendingTransfer?: PendingTransfer | null;
  pendingRecovery?: PendingRecovery | null;
};

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    try {
      const detail = JSON.parse(error.message) as { message?: string; reason?: string };
      return detail.message || detail.reason || error.message;
    } catch {
      return error.message;
    }
  }
  return "Une erreur inattendue est survenue.";
}

export default function ForumOwnershipPage() {
  const { slug = "" } = useParams();
  const [state, setState] = useState<OwnershipState | null>(null);
  const [recoveryOwnerId, setRecoveryOwnerId] = useState("");
  const [transferTargetId, setTransferTargetId] = useState("");
  const [recoveryReason, setRecoveryReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const payload = await apiFetch<OwnershipState>(`/forum/structures/${encodeURIComponent(slug)}/ownership`);
      setState(payload);
      setRecoveryOwnerId(payload.recoveryOwnerUserId ?? "");
    } catch (reason) {
      setError(errorMessage(reason));
    }
  }, [slug]);

  useEffect(() => { void load(); }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true); setError(null); setNotice(null);
    try {
      await action();
      setNotice(message);
      await load();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function saveRecoveryOwner(event: FormEvent) {
    event.preventDefault();
    await run(
      () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/recovery-owner`, {
        method: "PUT",
        body: JSON.stringify({ user_id: recoveryOwnerId.trim() || null }),
      }),
      "Owner secondaire mis à jour.",
    );
  }

  async function requestTransfer(event: FormEvent) {
    event.preventDefault();
    await run(
      () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/transfers`, {
        method: "POST",
        body: JSON.stringify({ to_user_id: transferTargetId.trim() }),
      }),
      "Transfert demandé. Le destinataire doit l’accepter avant changement de propriétaire.",
    );
    setTransferTargetId("");
  }

  async function requestRecovery(event: FormEvent) {
    event.preventDefault();
    await run(
      () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/recovery`, {
        method: "POST",
        body: JSON.stringify({ reason: recoveryReason.trim() }),
      }),
      "Demande de récupération enregistrée. Aucun droit OWNER n’est accordé avant validation.",
    );
    setRecoveryReason("");
  }

  if (!state && !error) return <main className="forum-main"><div className="forum-empty">Chargement de la propriété…</div></main>;

  return <main className="forum-main">
    <div className="forum-main__head">
      <div>
        <span className="forum-eyebrow">Sécurité de la structure</span>
        <h1>Ownership & recovery</h1>
        <p>La propriété est validée par le backend. Une demande de recovery seule ne donne jamais le rôle OWNER.</p>
      </div>
      <Link className="forum-button forum-button--ghost" to={`/forum/structures/${encodeURIComponent(slug)}/settings`}>Retour aux paramètres</Link>
    </div>

    {error ? <div className="forum-alert"><AlertTriangle size={17} /> {error}</div> : null}
    {notice ? <div className="forum-alert"><CheckCircle2 size={17} /> {notice}</div> : null}
    {!state ? null : <>
      {state.frozen ? <div className="forum-alert">
        <AlertTriangle size={18} />
        <div><strong>Structure temporairement gelée</strong><p>{state.frozenReason || "Litige ou contrôle de sécurité en cours."} Les opérations administratives critiques sont bloquées.</p></div>
      </div> : null}

      <div className="forum-grid-2">
        <section className="forum-card">
          <div className="forum-section-title"><div><span className="forum-eyebrow">Propriété</span><h2>Owners</h2></div><ShieldCheck size={20} /></div>
          <div className="forum-list">
            <div className="forum-row"><div><strong>Owner principal</strong><p>{state.primaryOwnerUserId}</p></div><span className="forum-badge">OWNER</span></div>
            <div className="forum-row"><div><strong>Owner secondaire / recovery</strong><p>{state.recoveryOwnerUserId || "Non défini"}</p></div><span className="forum-badge">RECOVERY</span></div>
          </div>
          {state.capabilities.includes("ownership.transfer") ? <form className="forum-form" onSubmit={saveRecoveryOwner} style={{ marginTop: 16 }}>
            <label>ID utilisateur de l’owner secondaire
              <input value={recoveryOwnerId} onChange={(event) => setRecoveryOwnerId(event.target.value)} placeholder="UUID d’un membre actif" />
            </label>
            <button disabled={busy || state.frozen} className="forum-button forum-button--primary" type="submit">Définir l’owner secondaire</button>
          </form> : null}
        </section>

        <section className="forum-card">
          <div className="forum-section-title"><div><span className="forum-eyebrow">Capability</span><h2>Droits ownership</h2></div><KeyRound size={20} /></div>
          <div className="forum-list">
            <div className="forum-row"><span>ownership.transfer</span><span className="forum-badge">{state.capabilities.includes("ownership.transfer") ? "Autorisé" : "Refusé"}</span></div>
            <div className="forum-row"><span>ownership.recover</span><span className="forum-badge">{state.capabilities.includes("ownership.recover") ? "Autorisé" : "Refusé"}</span></div>
          </div>
          <button className="forum-button forum-button--ghost" disabled={busy} onClick={() => void load()}><RefreshCw size={14} /> Actualiser</button>
        </section>
      </div>

      <div className="forum-grid-2">
        <section className="forum-card">
          <div className="forum-section-title"><div><span className="forum-eyebrow">Transfert sécurisé</span><h2>Transférer l’ownership</h2></div><UserRoundCheck size={20} /></div>
          {state.pendingTransfer ? <div className="forum-list">
            <div className="forum-row"><div><strong>{state.pendingTransfer.status}</strong><p>{state.pendingTransfer.fromUserId} → {state.pendingTransfer.toUserId}</p><small>Expire le {new Date(state.pendingTransfer.expiresAt).toLocaleString("fr-BE")}</small></div></div>
            <div className="forum-inline">
              {state.pendingTransfer.canConfirm ? <button disabled={busy || state.frozen} className="forum-button forum-button--primary" onClick={() => void run(
                () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/transfers/${state.pendingTransfer!.id}/confirm`, { method: "POST" }),
                "Transfert accepté et finalisé.",
              )}>Accepter le transfert</button> : null}
              {state.pendingTransfer.canCancel ? <button disabled={busy} className="forum-button forum-button--ghost" onClick={() => void run(
                () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/transfers/${state.pendingTransfer!.id}/cancel`, { method: "POST" }),
                "Transfert annulé.",
              )}>Annuler</button> : null}
            </div>
          </div> : state.capabilities.includes("ownership.transfer") ? <form className="forum-form" onSubmit={requestTransfer}>
            <label>ID du futur owner<input required value={transferTargetId} onChange={(event) => setTransferTargetId(event.target.value)} placeholder="UUID d’un membre actif" /></label>
            <button disabled={busy || state.frozen} className="forum-button forum-button--primary" type="submit">Demander le transfert</button>
          </form> : <div className="forum-empty">Aucun transfert en attente.</div>}
        </section>

        <section className="forum-card">
          <div className="forum-section-title"><div><span className="forum-eyebrow">Recovery</span><h2>Récupérer l’accès</h2></div><ShieldCheck size={20} /></div>
          {state.pendingRecovery ? <div className="forum-list">
            <div className="forum-row"><div><strong>{state.pendingRecovery.status}</strong><p>{state.pendingRecovery.reason}</p><small>Demandé par {state.pendingRecovery.requestedByUserId}</small></div></div>
            {state.pendingRecovery.canApprove ? <button disabled={busy} className="forum-button forum-button--primary" onClick={() => void run(
              () => apiFetch(`/forum/structures/${encodeURIComponent(slug)}/ownership/recoveries/${state.pendingRecovery!.id}/approve`, { method: "POST" }),
              "Recovery validé. La propriété a été transférée avec audit.",
            )}>Valider le recovery</button> : null}
          </div> : state.viewerUserId === state.recoveryOwnerUserId && state.capabilities.includes("ownership.recover") ? <form className="forum-form" onSubmit={requestRecovery}>
            <label>Motif de récupération<textarea required minLength={8} value={recoveryReason} onChange={(event) => setRecoveryReason(event.target.value)} placeholder="Expliquez la perte d’accès ou le conflit…" /></label>
            <button disabled={busy} className="forum-button forum-button--primary" type="submit">Demander le recovery</button>
          </form> : <div className="forum-empty">Seul l’owner secondaire configuré peut ouvrir une demande de recovery.</div>}
        </section>
      </div>
    </>}
  </main>;
}
