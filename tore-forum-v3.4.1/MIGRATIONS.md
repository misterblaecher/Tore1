# MIGRATIONS v3.3

Le state local v3.3 est en `version: 4`. La migration conserve les données v3.2 et complète les champs manquants : `Role.audienceLevel`, permissions, `publicProfile`, `publicAlumni`, `notes`, `Document.description`, `Document.versions`, `Media.visibility`, `PublicPost.visibility`.

IndexedDB `tore-forum-blobs` reste compatible : aucune purge automatique.

Le service worker utilise `tore-forum-v3.3-shell` et supprime les anciens caches. Les données privées ne sont pas placées dans le cache du shell.
