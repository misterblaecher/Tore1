# FINAL GAPS RC — TORÈ

Objectif: fermer uniquement les gaps 🟡 restants avant release candidate terrain-ready, sans ajout de feature.

## 1) Event state propagation mobile
- **Fichiers concernés**
  - `tore/app/lib/shared/utils/runtime_write_guard.dart`
  - `tore/app/lib/features/events/presentation/event_hub_screen.dart`
  - `tore/app/lib/features/navigation/presentation/home_hub_screen.dart`
- **Risque terrain**
  - Un état backoffice (`RUNNING`, `PAUSED`, `ENDED`) peut être mal interprété côté mobile, laisser des writes actifs ou afficher un message incohérent.
- **Fix minimal**
  - Harmoniser les aliases d’état (`LIVE/RUNNING`, `PAUSE/PAUSED`, `CLOSED/ENDED`) dans le guard runtime + messages UI.
- **Test manuel concret**
  - Forcer successivement les états `RUNNING`, `PAUSED`, `DEGRADED`, `FROZEN`, `ENDED` via l’admin; vérifier sur Menu/Wallet/Polymarket/Entry/Orders: bouton write désactivé + message clair + aucun crash.

## 2) Wallet write idempotence
- **Fichiers concernés**
  - `tore-backend/app/routers/wallet.py`
  - `tore-backend/tests/test_wallet_transfer.py`
- **Risque terrain**
  - Rejeu réseau (timeout/retry) pouvant provoquer un double débit en caisse/scan wallet.
- **Fix minimal**
  - Vérifier couverture des endpoints write sensibles via tests ciblés de replay idempotent et blocage hors état RUNNING.
- **Test manuel concret**
  - Rejouer deux fois le même write wallet (même `Idempotency-Key`) en réseau instable; vérifier second retour idempotent sans écriture ledger supplémentaire.

## 3) Polymarket idempotence / reason homogène
- **Fichiers concernés**
  - `tore-backend/app/routers/polymarket.py`
  - `tore-backend/tests/test_polymarket_event_router.py`
- **Risque terrain**
  - Réponses d’erreur hétérogènes (`MODULE_OFF` vs `module_off`, états legacy) compliquant les guards mobile/portal et la reprise opérateur.
- **Fix minimal**
  - Uniformiser les reason machine (`module_off`, `event_paused`) et couvrir les writes critiques par tests.
- **Test manuel concret**
  - Module polymarket OFF puis tentative create/buy/resolve: même code reason partout, action bloquée sans crash UI.

## 4) Module OFF invisibility mobile
- **Fichiers concernés**
  - `tore/app/lib/features/events/presentation/event_hub_screen.dart`
  - `tore/app/lib/features/navigation/presentation/home_hub_screen.dart`
- **Risque terrain**
  - Opérateurs/utilisateurs voient des entrées non exploitables (quick-links fantômes), perte de temps en rush.
- **Fix minimal**
  - Ne rendre que les modules explicitement ON; aucun placeholder ni CTA vers module OFF.
- **Test manuel concret**
  - Désactiver `wallet`, `menu`, `polymarket`; vérifier Home/Discovery/Event Hub sans cartes correspondantes.

## 5) Portal module flag guards
- **Fichiers concernés**
  - `tore-portal/src/App.tsx`
  - `tore-portal/src/pages/PolymarketAdmin.tsx` (et pages ops sensibles déjà flaggées)
- **Risque terrain**
  - Accès direct URL sur une page ops alors que module OFF, générant erreurs opérateur au lieu d’un blocage explicite.
- **Fix minimal**
  - Ajouter garde de navigation et/ou bannière explicite state/module avant action.
- **Test manuel concret**
  - Ouvrir URL directe d’un module OFF avec rôle autorisé; vérifier blocage immédiat et message exploitable.

## 6) Pack déploiement vérifié bout-en-bout
- **Fichiers concernés**
  - `scripts/ops_bootstrap_local.sh` (nouveau)
  - `docs/OPS_SMOKE_TEST_RC.md` (nouveau)
  - `docs/RELEASE_CHECKLIST.md`
- **Risque terrain**
  - Perte de temps au montage local/prod-like (ordre des commandes non clair), risque de départ soirée sans validation minimale.
- **Fix minimal**
  - Script bootstrap unique + smoke checklist condensée (12 points max) + liens runbook/release pipeline.
- **Test manuel concret**
  - Exécuter script sur environnement vierge local, puis dérouler la checklist RC complète et confirmer PASS/KO explicite.
