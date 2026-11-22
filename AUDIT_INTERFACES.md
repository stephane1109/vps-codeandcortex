# ScrapTikTok : interface unique Streamlit

Mise à jour du 10 octobre 2026, après demande de suppression de l’interface historique.

## Résultat

Streamlit est désormais l’unique interface utilisateur. Les fichiers de l’ancien
formulaire (`static/index.html`, `static/app.js`, `static/style.css`) sont supprimés.
L’adresse `/classique`, avec ou sans paramètre `controle`, renvoie 404.
Le réglage `UI_STREAMLIT` est retiré du code d’exécution : il ne peut plus réactiver
un mode alternatif. `/interface/` reste une redirection vers l’accueil `/`.

`webapp.py` reste le serveur technique FastAPI nécessaire aux tâches de collecte,
à Selenium, aux sessions privées, aux exports et au relais HTTP/WebSocket de
Streamlit. Il ne contient plus de formulaire utilisateur autonome.

## Architecture conservée

```text
Navigateur utilisateur → FastAPI (port public)
                         ├─ / → Streamlit (port interne)
                         ├─ /controle → composant de contrôle TikTok intégré
                         └─ /api/* → Manager → moteur Selenium commun
                                             └─ stockage et exports
```

Le composant `/controle?collecte=<identifiant>` ne contient que les interactions
avec le navigateur du serveur : image, gestes, clavier et bouton Continuer. Il ne
charge aucun formulaire de collecte, catalogue de presse ou option vidéo.
Les ressources `controle.html`, `controle.css`, `controle.js` et `navigateur.js`
sont réservées à ce composant. Elles sont nécessaires pour une vérification TikTok
interactive dans Streamlit.

Le démarrage Docker/Coolify continue d’utiliser `lancer_interface.py`. Les variables
d’environnement de l’utilisateur et la configuration Redis restent inchangées.
Lancer Uvicorn seul ne démarre pas l’interface Streamlit.

## Contrôles de non-régression

- 128 tests automatisés : collecte, filtres, exports, sessions, accès et modules.
- Absence du formulaire et des anciens fichiers ; `/classique` et ses anciennes
  ressources renvoient 404, même avec `UI_STREAMLIT=0` dans l’environnement.
- Contrôleur testé dans Chrome : gestes et commandes ciblent uniquement la tâche
  affichée, sans création de tâche supplémentaire ni chargement d’un formulaire.
- Parcours Streamlit avec pages locales synthétiques : deux hashtags, sélection
  des 29 médias, exports TXT/ZIP/CSV et affichage mobile.
- `tests/smoke_browser.py` reste uniquement un point d’entrée de compatibilité pour
  la CI : il exécute le test du contrôleur. Le code du test de l’ancienne interface
  est supprimé ; les données synthétiques sont dans `tests/fixtures_navigateur.py`.

Ces parcours vérifient l’application avec de vrais navigateurs Chrome et des pages
locales. Ils ne garantissent pas l’accès aux profils TikTok depuis le VPS et ne
résolvent aucun CAPTCHA réel automatiquement.
