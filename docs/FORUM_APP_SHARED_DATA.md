# Données communes du forum et de l'application

Le forum (`tore_site`) et l'application Flutter (`tore/app`) utilisent le même
backend et la même base. Il n'y a pas de copie ni de tâche de réplication.

En local, démarrer `tore-backend/start-local.ps1` sur le port 8000, puis
`npm run dev` dans `tore_site`. Le forum utilise `http://localhost:8000` et
l'émulateur Android `http://10.0.2.2:8000`, qui désignent le même serveur.

Les comités/cercles sont les mêmes `Organization` : `/orgas` côté application,
`/forum/structures` côté forum. Les soirées sont les mêmes `Event` : `/events`
côté découverte et `/forum/structures/{slug}/events` côté gestion du forum.
Les identifiants sont conservés sur les deux interfaces.

Une soirée doit être publiée et publique pour apparaître dans la découverte.
La structure et son bloc événements doivent également être publics pour être
affichés sur sa page publique du forum. Les brouillons, documents privés et
droits des membres conservent leurs restrictions.

La découverte mobile et la page publique d'une structure relisent les données
toutes les 30 secondes lorsqu'elles sont ouvertes. La page du forum recharge
aussi les données au retour sur l'onglet. Hors connexion, le cache mobile peut
encore montrer la dernière version connue.

Pour un environnement distant, définir `VITE_API_BASE_URL` et
`TORE_API_BASE_URL` vers la même API HTTPS. Ces modifications locales ne
déploient ni le forum public ni une nouvelle version mobile.

Régression : `tests/test_forum_structure_mvp.py` vérifie la structure partagée,
la publication d'une soirée créée dans le forum, sa découverte par ville sans
bar associé, sa modification et son retrait des deux interfaces publiques.
