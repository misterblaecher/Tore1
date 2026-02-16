# TORÈ terrain smoke E2E (Android, 10 minutes)

Objectif: faire un passage rapide et répétable avant une soirée pour réduire les risques terrain (offline queue, QR, orders, bar ops).

## Préparation rapide

- Appareil Android chargé, connecté au backend cible (DEV recommandé).
- Build/app installée avec les `--dart-define` attendus.
- 1 compte utilisateur + 1 compte staff entry + 1 compte bar/portal.
- Event de test prêt avec menu, modules activés, et QR valides.

## Checklist exécution (10 minutes)

1. **Boot: online/offline read-only**
   - Ouvrir l'app en ligne: vérifier écran d'accueil + event context.
   - Activer mode avion (ou couper Wi-Fi + data), rouvrir l'app: vérifier que la lecture basique fonctionne sans crash.

2. **Join event: QR + code**
   - Join via scan QR event.
   - Join via saisie code event.
   - Vérifier que l'utilisateur rejoint bien le bon event.

3. **QR universal: unknown/expired/revoked**
   - Scanner un QR inconnu: message d'erreur explicite.
   - Scanner un QR expiré: refus attendu.
   - Scanner un QR révoqué: refus attendu.

4. **Menu: add-to-cart, item OUT blocks, checkout -> QR order**
   - Ajouter plusieurs items au panier.
   - Passer un item en statut OUT, vérifier blocage add-to-cart.
   - Checkout: vérifier génération du QR de commande.

5. **Order status live: transitions**
   - Vérifier transitions live côté user: `PENDING -> ACCEPTED -> READY -> CLAIMED` (ou équivalent).

6. **Entry staff: 5 scans + offline capture + resync**
   - Staff entry scanne 5 QR valides en ligne.
   - Passer hors-ligne et scanner (capture offline/queue).
   - Repasser en ligne et vérifier resynchronisation sans doublon.

7. **Bar mode (portal): accept/ready/claim; menu admin quick stock change**
   - Depuis le portal, traiter 1 commande jusqu'à `CLAIMED`.
   - Modifier rapidement un stock menu (IN/OUT) et vérifier impact mobile.

8. **Broadcast: send + ticker shows**
   - Envoyer un broadcast depuis ORGA/portal.
   - Vérifier affichage ticker en temps réel côté app.

9. **Music round: start round + vote + winner**
   - Démarrer un round.
   - Voter depuis un compte user.
   - Clôturer et vérifier winner affiché.

10. **Safety: buddy + panic (verify ORGA sees)**
    - Déclencher buddy + panic côté user.
    - Vérifier visibilité immédiate côté ORGA.

11. **Wifi claim**
    - Réclamer accès Wi-Fi via flow prévu.
    - Vérifier état/retour utilisateur.

12. **Hunt checkpoint claim + leaderboard + steal**
    - Claim checkpoint valide.
    - Vérifier mise à jour leaderboard.
    - Tester action steal et recalcul score.

13. **Battles vote + leaderboard**
    - Soumettre un vote battle.
    - Vérifier leaderboard mise à jour.

## Commandes ADB utiles

### Ouvrir un deep link QR

```bash
adb shell am start -a android.intent.action.VIEW -d 'tore://qr?token=demo'
```

### Simuler offline sur Android

Option 1 (manuel, recommandé):
- Activer **mode avion** depuis le quick settings.
- Ou désactiver séparément Wi-Fi + données mobiles.

Option 2 (adb, selon device/permissions):

```bash
adb shell svc wifi disable
adb shell svc data disable
```

Réactiver:

```bash
adb shell svc wifi enable
adb shell svc data enable
```

### Logs ciblés TORE

Windows:

```powershell
adb logcat | findstr TORE
```

macOS / Linux:

```bash
adb logcat | grep TORE
```
