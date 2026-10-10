# Audit de ScrapTikTok — 10 octobre 2026

## Conclusion

Deux interfaces de saisie coexistaient : Streamlit à l’accueil et le formulaire
HTML historique à `/classique`. Le cadre TikTok de Streamlit chargeait également
ce formulaire complet, masqué par du CSS. Ce doublon est supprimé du parcours
Streamlit : le cadre charge désormais une page réservée au contrôle du navigateur.

FastAPI et Streamlit ne constituent pas deux moteurs de collecte. FastAPI gère
les tâches, Selenium, les fichiers et les contrôles d’accès ; Streamlit affiche
le formulaire et les résultats. Supprimer FastAPI casserait ces fonctions.

## Périmètre vérifié

- Points d’entrée : `scraptiktok.py`, `webapp.py`, `streamlit_app.py`,
  `lancer_interface.py`, `docker-entrypoint.sh`, Dockerfile et Compose.
- Interface : `interface/`, `static/`, formulaire, catalogue de presse,
  sélection des sources, session, navigateur distant, résultats et téléchargements.
- Moteur et modules : `collecte/`, `language_filter.py`, `stockage/`, `corpus/`,
  `analyse/`, `video/`, `audio/`, configuration et traitement par lots.
- Accès : `ticket_gate.py`, client HTTP, passerelle HTTP/WebSocket et restrictions
  des routes de l’API ; aucune variable d’environnement ni valeur Redis modifiée.
- Tests existants et documentation. Les dépendances installées et les données
  utilisateur ne font pas partie du code audité.

La lecture du code et les tests ne constituent pas une certification des réponses
de TikTok ni de la précision des classifications audiovisuelles.

## Constats et corrections

| Élément | Constat | Résultat |
| --- | --- | --- |
| `/classique` en mode Streamlit | Second formulaire accessible, avec des options différentes | Redirection vers `/` |
| Ancien cadre `/classique?controle=1` | Chargeait le formulaire, le catalogue et leur JavaScript, puis les cachait | Redirection de compatibilité vers `/controle` |
| Nouveau cadre | Page autonome sans formulaire, résultats ou options vidéo | `static/controle.html` et `static/controle.js` |
| Collecte contrôlée | Le cadre reprenait la dernière tâche de la session, potentiellement différente de celle affichée | Identifiant transmis par Streamlit : `/controle?collecte=…` |
| Gestes, clavier et images | Risque de divergence en créant un nouveau contrôleur | Une seule implémentation partagée dans `static/navigateur.js` |
| Démarrage des tâches | Un seul moteur et un verrou par session dans `Manager.start` | Aucun second lancement automatique trouvé ; contrôle ajouté au parcours navigateur |
| Mode FastAPI autonome | Fonctionnalité historique conservée | Formulaire HTML disponible avec `UI_STREAMLIT=0` |
| Exports et filtres | Traitement effectué dans le moteur commun | Comportement préservé par les tests |

Le contrôleur lié à un identifiant ne consulte ni `/api/session` ni `/api/presse`
et ne crée jamais de collecte. L’API vérifie toujours que la tâche appartient à la
session du navigateur. Pour un ancien lien sans identifiant, la dernière tâche est
résolue une seule fois, puis le contrôleur reste lié à cette tâche.

## Architecture après correction

```text
Navigateur utilisateur → FastAPI (port public)
                         ├─ / → passerelle → Streamlit (port interne)
                         ├─ /controle → contrôle de la tâche affichée
                         └─ /api/* → Manager → moteur Selenium commun
                                             └─ stockage et exports
```

Streamlit interroge l’API pour les résultats ; le cadre interroge l’état et les
images de la même tâche pour les interactions. Ces lectures ne lancent aucune
nouvelle collecte. Les commandes CLI et le traitement vidéo par lots restent
des entrées explicites, indépendantes du démarrage de l’interface.

## Validation exécutée

- `python -m unittest discover -s tests` : **128 tests réussis**.
- `node --check` sur les trois modules JavaScript : syntaxe valide.
- `python tests/smoke_controle.py` : Chrome, cadre sans formulaire, absence de
  création de tâche, erreurs affichées et bouton Continuer lié à la bonne tâche
  malgré une tâche plus récente dans la même session.
- `python tests/smoke_streamlit.py` : Chrome + Streamlit + FastAPI, deux hashtags,
  session commune, 29 médias cochés avec deux requêtes ciblées par compte, gestes,
  TXT/ZIP/CSV, compteurs et affichage mobile. Deux lancements explicites créent
  exactement deux tâches.
- `python tests/smoke_browser.py` : interface HTML autonome, interactions,
  sélection presse/comptes, hashtag facultatif, archive privée et corpus IRaMuTeQ.

Les parcours navigateur utilisent des pages TikTok **synthétiques locales**.
Ils vérifient le câblage de l’application et les régressions sans prétendre résoudre
les restrictions d’accès de TikTok sur le VPS. Aucun CAPTCHA réel n’est automatisé.

## Observation sur le serveur local

Au moment de l’audit, le lanceur servant le port 8510 et son processus Streamlit
étaient démarrés depuis le 9 octobre à 14 h 10. Le lanceur désactive le rechargement
automatique (`fileWatcherType=none`) : modifier les fichiers ne suffit donc pas à
mettre ce processus à jour. Un redémarrage est nécessaire pour appliquer le
correctif localement, et une reconstruction/redéploiement pour l’image Coolify.

Le serveur local a ensuite été redémarré sur le port 8510, après vérification de
l’absence de navigateur de collecte actif. Les anciens onglets doivent être
rechargés pour remplacer leur document déjà ouvert.

Ce constat explique la possibilité d’une ancienne interface encore affichée ;
il ne prouve pas que les résultats vides de TikTok proviennent du doublon.
