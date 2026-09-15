# Background TORÈ 2.5D

Ouvrir **index.html** par double-clic : tout fonctionne localement, sans
installation, connexion réseau, framework ou compilation.

Trois ambiances utilisent les **huit mêmes plans indépendants** :

| Page | Intensité | Parallaxe | Particules / fumée | Impulsion |
| --- | --- | --- | --- | --- |
| demo-hero.html | 1 | 1 | Complètes | Oui |
| index.html / demo-forum.html | 0,7 | 0,65 | Complètes | Oui |
| demo-dashboard.html | 0,4 | 0,3 | Réduites | Non |

Le bouton « Voir le décor seul » masque l’interface de démonstration.
« Raviver le feu » déclenche la même impulsion qu’un clic sur le décor.
Les boutons et liens de l’interface ne déclenchent pas d’effets parasites.
Les rubriques, chiffres et textes présentés sont des exemples statiques.

## Intégrer dans le forum

Copier `assets/`, `tore-background.css` et `tore-background.js`.
Le style de démonstration `demo.css` est séparé ; il n’est pas nécessaire
à l’intégration. Aucun appel réseau externe n’est effectué.

```html
<link rel="stylesheet" href="tore-background.css">
<div id="tore-background" class="tore-background">
  <div class="tore-background__content">
    <!-- Navigation, cartes et contenu du forum -->
  </div>
</div>
<script src="tore-background.js"></script>
<script>
  const toreBackground = new ToreBackground3D(
    document.querySelector('#tore-background'),
    { ...ToreBackground3D.presets.FORUM, quality: 'auto' }
  );
</script>
```

Le dossier `assets/` est résolu à côté du fichier JavaScript. Pour un autre
emplacement, fournir `assetsPath: '/mon-dossier/assets/'` (avec le slash final).
Le conteneur a une hauteur minimale de 100svh ; adapter sa hauteur dans
le CSS du forum si nécessaire. Le décor est limité à ce conteneur.

API : `start()`, `stop()`, `destroy()`, `setIntensity(0..1.5)`,
`setParallax(0..1.5)`, `triggerPulse()`,
`setQuality('low' | 'medium' | 'high' | 'auto')`.
Les appels `start()` sont idempotents ; `destroy()` retire le décor,
les écouteurs et les observateurs en préservant le contenu.
`triggerPulse()` respecte le preset et les préférences de mouvement.
L’événement `tore:asset-error` indique une image manquante via `event.detail`.

## Images

- `assets/*.webp` : exports alignés en **1920 × 1080**, environ **1,59 Mo** au total.
- `assets/*.png` : sources imagegen originales, 1672 × 941.
- `composition-test.png` : superposition statique de contrôle, sans interface.
- `layers-contact-sheet.png` : huit plans dans l’ordre des noms, deux colonnes,
  sur fond gris pour rendre les zones transparentes visibles.
- `ART-DIRECTION.md` : prompts et référence culturelle.

Toutes les couches sauf l’arrière-plan ont un vrai canal alpha, y compris
les zones semi-transparentes des fumées. Le terrain est recalé de 120 px
vers le bas lors de l’export, afin de rejoindre le socle. Les opacités de
fumée sont volontairement faibles. La statue et la ville sont des
interprétations artistiques inspirées du Torê et de Liège, pas des
reproductions documentaires exactes.

## Profondeur et performance

Profondeurs : ville −60 ; fumée arrière −35 ; halo −20 ; braises arrière 0 ;
statue +15 ; terrain +25 ; braises avant +35 ; roches +45 ; fumée avant +55.
La perspective est compensée pour conserver l’alignement au repos.
Toutes les couches et tous les Canvas partagent un seul cadre cover,
avec recadrage commun à droite sur mobile et marge pour la parallaxe.

Une seule boucle requestAnimationFrame est partagée même entre plusieurs
instances. Rendu décoratif limité à 40 FPS en haute qualité et 30 FPS
sinon ; interpolation indépendante de la fréquence d’écran. Au maximum
96 / 48 / 20 braises en haute / moyenne / basse qualité. Canvas avec DPR
plafonné à 1,5, fumée à résolution 0,35 ou 0,2, sprites précalculés,
aucun shadowBlur par particule. Les émetteurs restent sur le halo et la
lave, indépendants du curseur.

Le mode auto utilise la largeur du conteneur et les informations de
capacité du navigateur. Le mode basse qualité est sélectionnable manuellement.
L’animation s’arrête dans un onglet masqué, hors écran, ou avec
`prefers-reduced-motion: reduce`. Dans ce dernier cas la scène reste
statique, sans particules animées ni impulsion. Un bouton Pause est fourni.

## Vérifications

`asset-checks.json` : tailles exactes et transparence vérifiées pour chaque WebP.
`browser-checks.json` : tests automatisés Edge/Chromium en ouverture file:// :
chargement des huit images, souris, impulsion et retour au repos, coordonnées
des émetteurs, plafond de fréquence, pause/reprise/destruction, arrêt hors
écran, redimensionnement mobile, absence de débordement horizontal,
préférence de mouvement réduit, et trois presets sans erreur JavaScript.
Captures : `preview-desktop.png` et `preview-mobile.png`.

Le test mesure le plafond de fréquence sur cette machine ; il ne constitue
pas un benchmark de tous les ordinateurs portables ou navigateurs mobiles.

Scripts facultatifs pour le développement :

- `node serve.cjs` : aperçu sur http://127.0.0.1:4178.
- `node prepare-assets.cjs` : réexport et contrôles, nécessite `sharp`.
- `node verify.cjs` : contrôles navigateur, nécessite `playwright` et Edge.

Les bibliothèques de développement peuvent être trouvées via `NODE_PATH`.
Elles ne sont pas nécessaires pour utiliser le background.
