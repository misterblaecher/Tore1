# Plan technique : scission progressive de models.py

**Objectif** : découper `tore-backend/models.py` (~2150 lignes, ~95 classes) en plusieurs fichiers sans casser Alembic ni modifier le schéma de base de données.

**Contraintes strictes** (durant toute la migration) :
- Ne pas modifier le code applicatif (routers, services).
- Ne pas renommer de table, modifier aucun `__tablename__`, aucune colonne.
- Ne pas créer de nouvelle migration Alembic.
- Produire uniquement de la documentation pour l’instant — pas de patch ni de modification de code.

---

## 1. Analyse des domaines naturels

L’analyse de `models.py` permet d’identifier **15 domaines** cohérents métier/technique :

| Domaine | Classes | Lignes approx. | Description |
|---------|---------|----------------|-------------|
| **bars** | Bar, Zone, BarPrivacySetting | ~80 | Bars, zones, paramètres de confidentialité bar |
| **events** | Event, EventCreateIdempotency, EventConfig, EventConfigLog, EventRuntimeState, EventModuleConfig, EventCost, EventCostSimple, EventCostSimpleIdempotency, EventAuditLog, EventBroadcast | ~220 | Cœur événement, config, runtime, coûts |
| **event_staff** | EventStaff, EventStaffAssignment, EventStaffAssignmentIdempotency, EventJoin, EventCharterAcceptance, StaffInviteToken | ~100 | Staff, assignments, joins, charte |
| **event_qr** | EventQrToken, EventQrPackIdempotency, EventAppWriteIdempotency | ~60 | Tokens QR, idempotence app |
| **event_incidents** | EventIncident, EventIncidentLog, EventIncidentCreateIdempotency, EventIncidentActionIdempotency | ~75 | Incidents et logs |
| **event_wifi** | EventWifiSettings, EventWifiToken, EventWifiIdempotency, WifiConfig | ~70 | Paramètres Wi‑Fi et tokens |
| **event_map** | EventMapSettings, EventNavettesSettings, EventMapIdempotency | ~55 | Carte, navettes |
| **entry** | TicketBalance, Ban, Entry, EntryLog, EntryScanLog, EntryToken | ~120 | Entrées, billets, tokens, bans |
| **menu** | MenuCategory, MenuItem, MenuItemVariant, MenuTrackEvent, MenuAdminIdempotency | ~120 | Menu bar (catégories, items, variants) |
| **drinks** | Drink, EventDrink, PriceHistory, DrinkMarketConfig, DrinkMarketItem, DrinkPriceTick, DrinkPriceTickIdempotency | ~150 | Boissons, prix, marché |
| **orders** | Order, OrderItem, OrderStatusTransitionIdempotency, OrderClientQrScan | ~120 | Commandes |
| **hunt** | Hunt, HuntPoint, HuntScan, EventHunt, EventHuntCheckpoint, EventHuntClaim, EventHuntScore, EventHuntIdempotency, EventHuntSteal | ~160 | Hunts, checkpoints, scores |
| **polymarket** | Bet, BetPosition, BetResolutionLog, PolymarketEventIdempotency, BetDispute | ~90 | Paris Polymarket |
| **battles** | Battle, BattleParticipant, BattleTeam, BattleJoin, BattleAction, BattleSubmit, EventBattleRound, EventBattleVote, EventBattleScore, EventBattleIdempotency | ~150 | Battles Afond, rounds, votes |
| **music** | EventMusicSetting, EventMusicCandidate, EventMusicVote, EventMusicActionIdempotency, EventMusicAdminIdempotency | ~90 | Module musique, votes |
| **safety** | SafetyBuddySession, EventSafetySettings, EventSafetyBuddy, EventSafetyCheckin, EventSafetyIdempotency | ~75 | Sécurité événement |
| **checkin** | Beer, Checkin, DrinkCheckin | ~55 | Checkins Untappd-like et drinks |
| **partners** | PartnerUser, PartnerBarAccess, PartnerMagicLinkToken, PartnerMembership, PartnerTokenRevocation, PartnerInvite | ~120 | Utilisateurs partenaires, accès bars |
| **users** | AppUser, AppToken, AuthMagicLink, RefreshToken, AppUserPrivacySetting, UserPrivacyDeleteRequest, UserSanction | ~130 | Utilisateurs app, auth, confidentialité |
| **wallet** | Wallet, WalletTx, WalletLedgerEntry, WalletGift, TicketTransfer, TicketTransferIdempotency, UserGiftCode | ~130 | Portefeuille, transfers, cadeaux |
| **committees** | Committee, CommitteeYear, CommitteeMembership, CommitteeInviteCode, CommitteeRolePermission, CommitteeAdminIdempotency, CommitteeForumCategory, CommitteeForumPost, CommitteeLedgerEntry, CommitteeLedgerIdempotency, CommitteeBudgetBucket, CommitteeBaptemeCampaign, CommitteeBaptemeInvite, CommitteeBaptemeSlot, CommitteeBaptemeAssignment, CommitteeBaptemeIncident, CommitteeBaptemeIdempotency, CommitteeGlossarySettings, CommitteeGlossaryTerm, CommitteeGlossaryIdempotency | ~380 | Comités, forum, finance, baptêmes |
| **organizations** | Organization, OrganizationMembership, OrganizationInviteCode, OrganizationWriteIdempotency, OrgaPost | ~90 | Organisations, posts |
| **audit** | AuditLog | ~30 | Journal d’audit global |
| **global** | GlobalFeatureFlag | ~15 | Flags feature globaux |

---

## 2. Structure cible proposée

```
tore-backend/
├── models.py                    # Façade (ré-exporte tout) — temporaire
└── app/
    └── models/
        ├── __init__.py          # Ré-exporte toutes les classes (point d’entrée)
        ├── base.py              # Optionnel : ré-exporte Base, now_utc depuis db
        ├── bars.py              # Bar, Zone, BarPrivacySetting
        ├── events.py            # Event, EventConfig, EventRuntimeState, etc.
        ├── event_staff.py       # EventStaff, EventStaffAssignment, EventJoin, etc.
        ├── event_qr.py          # EventQrToken, EventQrPackIdempotency, EventAppWriteIdempotency
        ├── event_incidents.py   # EventIncident, EventIncidentLog, etc.
        ├── event_wifi.py        # EventWifiSettings, EventWifiToken, etc.
        ├── event_map.py         # EventMapSettings, EventNavettesSettings, etc.
        ├── entry.py             # TicketBalance, Ban, Entry, EntryLog, EntryScanLog, EntryToken
        ├── menu.py              # MenuCategory, MenuItem, MenuItemVariant, MenuTrackEvent, MenuAdminIdempotency
        ├── drinks.py            # Drink, EventDrink, DrinkMarketConfig, etc.
        ├── orders.py            # Order, OrderItem, OrderStatusTransitionIdempotency, OrderClientQrScan
        ├── hunt.py              # Hunt, EventHunt, EventHuntClaim, etc.
        ├── polymarket.py        # Bet, BetPosition, BetResolutionLog, etc.
        ├── battles.py           # Battle, EventBattleRound, EventBattleVote, etc.
        ├── music.py             # EventMusicSetting, EventMusicCandidate, etc.
        ├── safety.py            # EventSafetySettings, EventSafetyBuddy, etc.
        ├── checkin.py           # Beer, Checkin, DrinkCheckin
        ├── partners.py          # PartnerUser, PartnerBarAccess, PartnerMembership, etc.
        ├── users.py             # AppUser, AppToken, AuthMagicLink, RefreshToken, etc.
        ├── wallet.py            # Wallet, WalletTx, WalletLedgerEntry, WalletGift, etc.
        ├── committees.py        # Committee, CommitteeYear, CommitteeMembership, etc.
        ├── organizations.py     # Organization, OrganizationMembership, OrgaPost, etc.
        ├── audit.py             # AuditLog
        └── global_flags.py      # GlobalFeatureFlag
```

**Alternative plus compacte** : fusionner certains domaines peu volumineux (ex. `event_wifi` + `event_map` → `event_extras`, `audit` + `global_flags` → `audit_flags`), mais la structure ci-dessus maximise la lisibilité et la maintenabilité.

---

## 3. Compatibilité Alembic

### Principe

Alembic utilise `target_metadata = Base.metadata`. Les tables sont enregistrées dans `Base.metadata` **lors de la définition de chaque classe** héritant de `Base`. Tant que toutes ces classes sont importées avant l’exécution des migrations, `Base.metadata` contient l’intégralité du schéma.

### Imports dans `alembic/env.py`

Actuellement :
```python
from db import Base, DATABASE_URL
import models  # noqa: F401
```

Le `import models` est indispensable : c’est un import de côté (side-effect) qui charge toutes les classes et les enregistre dans `Base.metadata`.

### Stratégies possibles après la scission

**Option A : Garder `import models`**
- `models.py` devient une façade qui importe et ré-exporte tout depuis `app.models`.
- `alembic/env.py` continue d’importer `models` (aucun changement).
- Avantage : zéro modification côté Alembic.

**Option B : Importer directement `app.models`**
- Remplacer `import models` par `from app.models import *` ou une liste d’imports explicites.
- Nécessite de s’assurer que `app.models.__init__.py` importe **tous** les sous-modules.
- Risque : un oubli d’import dans `__init__.py` → metadata incomplet.

**Recommandation** : Option A pendant toute la phase de migration. Une fois la scission stabilisée et validée, on peut envisager Option B.

### Ordre d’import et dépendances croisées

L’ordre d’import dans `app.models.__init__.py` doit respecter les dépendances :
- `bars` → base (Bar)
- `events` → Bar
- `partners` → Bar, PartnerUser
- `users` → (pas de FK vers models internes dans l’app)
- `menu` → Bar
- `drinks` → Event, Drink
- `wallet` → AppUser, Event
- etc.

Aucune circularité évidente n’a été identifiée si l’ordre est :
1. `users` (AppUser)
2. `bars` (Bar)
3. `partners` (PartnerUser, PartnerBarAccess → Bar)
4. `events` (Event → Bar)
5. Puis le reste selon les FK.

---

## 4. Transformation de models.py en façade temporaire

### Rôle de la façade

`models.py` reste le point d’entrée unique pour tout le reste du projet (`from models import Event, Bar, …`). Il devient un simple ré-exporteur :

```python
# tore-backend/models.py — façade (exemple conceptuel)
from __future__ import annotations

from app.models import (
    Bar,
    Event,
    Drink,
    # ... liste exhaustive de toutes les classes
)

__all__ = [
    "Bar",
    "Event",
    # ...
]
```

### Avantages

- **Zéro changement** dans `main.py`, routers, services, tests : tous gardent `from models import X`.
- **Alembic inchangé** : `import models` charge la façade qui, en important `app.models`, charge tous les modèles.
- **Déplacement progressif** : on peut migrer les classes une par une de `models.py` vers `app.models.xxx`, puis mettre à jour la façade pour importer depuis les nouveaux modules.

### Implémentation progressive

1. Créer `app/models/` et `app/models/__init__.py`.
2. Pour chaque domaine :
   - Créer `app/models/xxx.py` avec les classes du domaine.
   - Ajouter dans `__init__.py` les imports depuis `xxx`.
   - Retirer ces classes de `models.py` et les remplacer par des ré-exports depuis `app.models`.
3. À la fin : `models.py` ne contient plus que des imports depuis `app.models` et éventuellement `__all__`.

---

## 5. Checklist de migration progressive (6–8 étapes)

| Étape | Action | Vérification |
|-------|--------|--------------|
| **1** | Créer `app/models/` et `__init__.py` vide (ou avec un seul import de test). Créer `base.py` si on veut centraliser Base/now_utc. | `from app.models import Bar` échoue tant qu’on n’a rien importé — c’est attendu. |
| **2** | Migrer le premier bloc (ex. `bars`) : créer `bars.py`, y déplacer Bar, Zone, BarPrivacySetting. Mettre à jour `__init__.py`. Transformer `models.py` en façade qui importe Bar, Zone, BarPrivacySetting depuis `app.models`. | `pytest`, `alembic current`, `alembic check` passent. |
| **3** | Migrer `users` et `partners` (ordre : users puis partners). | Idem. |
| **4** | Migrer `events` et tous les sous-domaines événement (event_staff, event_qr, event_incidents, event_wifi, event_map). | Idem. |
| **5** | Migrer menu, drinks, orders, entry. | Idem. |
| **6** | Migrer hunt, polymarket, battles, music, safety, checkin. | Idem. |
| **7** | Migrer wallet, committees, organizations, audit, global_flags. | Idem. |
| **8** | Vérifier que `models.py` est uniquement une façade. Lancer la suite de tests complète. Lancer `alembic upgrade head` puis `alembic revision --autogenerate -m "check"` et vérifier qu’aucun changement n’est détecté. | Tests verts, autogenerate ne produit aucun diff. |

---

## 6. Risques courants et comment les éviter

### Metadata vide ou partielle

**Symptôme** : Alembic ne voit pas certaines tables, ou `Base.metadata.tables` est incomplet.

**Causes** :
- Un module contenant des modèles n’est jamais importé.
- La façade `models.py` ou `app.models.__init__.py` n’importe pas un sous-module.

**Prévention** :
- S’assurer que `__init__.py` importe explicitement chaque sous-module (pas seulement les classes) pour déclencher l’enregistrement dans Base.metadata.
- Ajouter un test qui vérifie le nombre de tables attendu :  
  `assert len(Base.metadata.tables) >= N` après `import models` ou `import app.models`.

### Autogenerate détecte des changements fantômes

**Symptôme** : `alembic revision --autogenerate` propose des `ALTER TABLE` ou `CREATE TABLE` alors qu’aucun modèle n’a été modifié.

**Causes** :
- Ordre différent des colonnes entre le modèle et la DB.
- Types légèrement différents (ex. `String` vs `String(255)`).
- Index ou contraintes définis différemment.

**Prévention** :
- Ne pas changer les définitions des colonnes lors du déplacement (contrainte déjà posée).
- Comparer les `Table` générés par SQLAlchemy avec `Base.metadata.tables` avant/après migration.
- En cas de diff, inspecter le modèle déplacé pour vérifier qu’il est identique à l’original (copier-coller, pas de réécriture).

### Imports circulaires

**Symptôme** : `ImportError` ou `AttributeError` au démarrage.

**Causes** :
- `users.py` importe quelque chose de `events.py`, et `events.py` importe `users.py`.
- Relations bidirectionnelles mal gérées (les noms de classe en string `"Event"` évitent en général le problème, mais l’import du module peut créer une boucle).

**Prévention** :
- Utiliser les références en string pour les relations (`back_populates="bar"`, `Mapped["Event"]`).
- Ne pas importer de modèles d’un autre domaine dans un fichier de modèle sauf si nécessaire pour une relation explicite (en pratique, SQLAlchemy gère bien les strings).
- Ordre d’import dans `__init__.py` : domaines sans FK vers d’autres domaines en premier (users, bars), puis le reste.

### Régression des imports applicatifs

**Symptôme** : `from models import Event` échoue après la migration.

**Cause** : La façade `models.py` n’exporte pas la classe, ou le chemin d’import a changé.

**Prévention** :
- Maintenir une liste exhaustive `__all__` dans `models.py` et dans `app.models.__init__.py`.
- Garder `from models import X` partout dans l’application ; ne pas modifier les routers/services pendant la migration.

### Différences de chemin (app/models vs models)

**Symptôme** : certains fichiers importent `from app.models import X` et d’autres `from models import X`. Incohérence, risque de double chargement.

**Prévention** :
- Pendant la migration, **tout** le code applicatif continue d’utiliser `from models import X`.
- La façade `models.py` est le seul endroit qui importe `app.models`.
- Après stabilisation, une refactorisation globale pour passer à `from app.models import X` peut être planifiée séparément.

---

## Références

- `tore-backend/models.py` — fichier source actuel
- `tore-backend/alembic/env.py` — `import models` + `target_metadata = Base.metadata`
- `tore-backend/db.py` — `Base = declarative_base()`
- `.cursor/rules.md` — règle : « Ne pas modifier models.py ou les migrations Alembic sans plan de migration clair validable par tests »
