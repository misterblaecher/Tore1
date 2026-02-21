

# 🏴 Site TORÈ — Plan d'implémentation

## Vision du projet
Un site vitrine moderne, conversion-first, pour l'application TORÈ — la solution QR universelle pour bars et comités étudiants. Le site sera en français (priorité), dark mode natif avec accents rouges néon, et optimisé mobile-first.

---

## 🎨 Design & Identité

### Style visuel
- **Palette** : Noir profond (#0A0A0A) / Blanc pur / Rouge néon intense (#DC2626)
- **Typographie** : Sans-serif bold (Inter ou Montserrat) pour les titres, lisibilité maximale
- **Ambiance** : Contraste fort, vibes nocturnes, éléments "scan/speed/QR"
- **Assets** : Logo complet + icône app fournis → favicon + OpenGraph

### UX/UI
- Mobile-first responsive
- Dark mode natif
- Animations légères (fade-in, hover glow)
- CTA sticky sur mobile ("Demander une démo")
- Performance Lighthouse élevée

---

## 📄 Pages à créer (9 pages)

### 1. Accueil (Landing) — Page principale
- **Hero** : "Le QR universel des soirées." + sous-titre + CTAs
- **3 cartes valeur** : Setup <10min, Soirée-proof, Modules ON/OFF
- **Pour qui ?** : Bars vs Comités (2 colonnes)
- **Features clés** avec icônes : QR routing, création event 60s, entrée/comptage, rentabilité live, menu QR, rôles staff
- **Sécurité & confiance** : QR signés, ledger audit, RGPD
- **Teaser Roadmap + Pricing**
- **Formulaire démo** : nom, email, rôle, ville, type
- **Footer** : liens légaux, réseaux sociaux

### 2. Produit
- Scanner QR universel (schéma 3 étapes)
- Modules ON/OFF + permissions (Owner/Manager/Staff…)
- Mode réseau faible
- Portail web (menu, zones, exports)
- CTAs : "Onboard un bar" / "Créer un event"

### 3. Bars
- Menu QR riche mais léger
- Zones (tables/terrasse) + packs QR
- Tracking (scans, vues, add-to-cart)
- Commandes optionnelles
- Checklist onboarding "10 minutes"
- CTA : "Tester sur mon bar"

### 4. Comités / Events
- Création event < 2 min (templates)
- Entrée & comptage (mode estimation)
- Rentabilité live vs coûts
- Boutons d'urgence
- Rapport fin de soirée exportable
- CTA : "Créer un event démo"

### 5. Roadmap
Timeline visuelle des phases :
- Phase 0 : Fondations
- Phase 1 : MVP Comités Console
- Phase 2 : Soirée complète
- Phase 3 : Bar Kit + IA optionnelle
- Phase 4 : Commandes
- Phase 5 : Tickets & paiement
- Phase 6-8 : Bets, Hunts, OS bar

### 6. Pricing
- **Free** : menu + tracking basique
- **Pro Bar** : zones + exports + commandes
- **Add-ons** : IA, modules money (plus tard)
- Mention offre comité

### 7. Trust / Sécurité / RGPD
- Principes : audit, logs, consentement, privacy toggles
- Philosophie "pas de police" : warnings, modules désactivables
- Money boundaries : ledger + anti-fraude

### 8. Contact / Démo
- Formulaire complet
- Calendrier (placeholder Calendly)
- FAQ courte (réseau faible, temps setup, paiements)

### 9. Legal
- Privacy Policy (template)
- Terms of Service (template)
- Cookie notice simple

---

## 🛠 Fonctionnalités techniques

### SEO & Meta
- Titles + meta descriptions par page
- OpenGraph images + social preview
- Sitemap.xml + robots.txt
- Structure sémantique HTML

### Formulaires
- Validation côté client (Zod)
- Toast de confirmation
- Stockage email (placeholder pour intégration future)

### Performance
- Lazy loading images
- Composants optimisés
- Animations CSS performantes

### Accessibilité
- Contrastes WCAG AA
- Alt text sur images
- Navigation clavier

---

## 📦 Livrables

1. **9 pages complètes** avec navigation fluide
2. **Composants réutilisables** : Header, Footer, CTAs, Cards, Timeline
3. **Assets intégrés** : Logo, favicon, OG image
4. **Formulaires fonctionnels** avec validation
5. **Design system** : couleurs, typographies, espacements cohérents
6. **Mobile-first** responsive parfait
7. **Boutons App Store/Play Store** en "coming soon"
8. **Waitlist** si app pas encore disponible

---

## 🎯 Approche de développement

Je vais construire le site de manière itérative :
1. **Phase 1** : Setup design system + composants de base + Header/Footer + page Accueil
2. **Phase 2** : Pages Produit, Bars, Comités
3. **Phase 3** : Pages Roadmap, Pricing, Trust
4. **Phase 4** : Pages Contact, Legal + finitions SEO

Chaque phase sera fonctionnelle et testable avant de passer à la suivante.

