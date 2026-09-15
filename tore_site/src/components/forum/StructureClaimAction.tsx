import { useState } from "react";
import type { FormEvent } from "react";
import { Flag, ShieldCheck } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { apiFetch, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";

type ClaimResponse = {
  claim: {
    id: number;
    status: "PENDING" | "NEEDS_INFO" | "APPROVED" | "REJECTED" | "CANCELLED";
  };
};

export function StructureClaimAction({
  structureId,
  structureName,
  className = "forum-button forum-button--ghost",
}: {
  structureId?: number;
  structureName: string;
  className?: string;
}) {
  const location = useLocation();
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [claim, setClaim] = useState<ClaimResponse["claim"] | null>(null);

  if (!getToken()) {
    return (
      <Link
        className={className}
        to="/forum/login"
        state={{ from: `${location.pathname}${location.search}${location.hash}` }}
      >
        <Flag size={16} /> Revendiquer cette structure
      </Link>
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!structureId) {
      setError("Cette structure ne peut pas encore être revendiquée.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await apiFetch<ClaimResponse>("/forum/structure-claims", {
        method: "POST",
        body: JSON.stringify({
          structure_id: structureId,
          reason,
          evidence: evidence
            .split("\n")
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      });
      setClaim(response.claim);
    } catch (reasonThrown: unknown) {
      setError(
        reasonThrown instanceof ApiError
          ? reasonThrown.message
          : "La revendication n’a pas pu être envoyée.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog>
      <DialogTrigger className={className}>
        <Flag size={16} /> Revendiquer cette structure
      </DialogTrigger>
      <DialogContent className="portal-dialog">
        <DialogTitle>Revendiquer {structureName}</DialogTitle>
        <DialogDescription>
          Une revendication ouvre une demande de review. Elle ne donne aucun
          droit de gestion automatiquement. Le rôle OWNER n’est attribué qu’après
          approbation.
        </DialogDescription>
        {claim ? (
          <div className="forum-alert" role="status">
            <ShieldCheck size={17} />
            Demande #{claim.id} envoyée. Statut : <strong>{claim.status}</strong>.
          </div>
        ) : (
          <form className="forum-form" onSubmit={submit}>
            {error ? (
              <div className="forum-alert" role="alert">
                {error}
              </div>
            ) : null}
            <label>
              Pourquoi êtes-vous habilité à revendiquer cette structure ?
              <textarea
                required
                minLength={12}
                maxLength={5000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Mandat actuel, rôle dans le comité, contexte de reprise…"
              />
            </label>
            <label>
              Preuves / éléments de vérification
              <textarea
                value={evidence}
                onChange={(event) => setEvidence(event.target.value)}
                placeholder={"Une référence par ligne : site officiel, PV, contact, document…"}
              />
            </label>
            <p className="portal-empty">
              TORÈ examinera la demande. Aucun accès admin n’est accordé pendant
              la review.
            </p>
            <button
              className="forum-button forum-button--primary"
              type="submit"
              disabled={busy}
            >
              {busy ? "Envoi…" : "Envoyer la revendication"}
            </button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
