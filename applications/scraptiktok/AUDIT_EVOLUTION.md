# Audit de départ et contrat de non-régression

État initial : 39 tests unitaires/API passent. Entrées conservées : `scraptiktok.py`
(CLI CSV/JSON/TXT) et `webapp.py` (FastAPI, TXT privé par session).
Fonctions à conserver : deux hashtags ET/OU, filtre français, manipulation manuelle
du navigateur distant, résultats partiels, annulation, contrôle d’accès, limites,
expiration, Chromium/Xvfb non-root, port 8501, branche Coolify avec fichiers à la racine.

Constats : collecte exclusivement par hashtags ; extraction JSON limitée à l’ID de
la publication ; aucun archivage SQLite, engagement ou commentaire ; pas de média
local ni de modèle audiovisuel. Le navigateur et ses commandes appartiennent à un
seul worker. Cette contrainte reste valable pour les nouvelles collectes.

Étapes : (1) collecte presse/engagement/commentaires et stockage/export enrichi,
(2) analyse audiovisuelle indépendante et bornée, (3) comparaison temporelle et
codage SHS, (4) intégration optionnelle, documentation, tests Linux et régression.
Les dépendances lourdes ne doivent jamais être importées par le parcours texte.
Les tests synthétiques valident les algorithmes ; ils ne prouvent pas l’exhaustivité
de TikTok, ni la précision scientifique des détecteurs sur un corpus réel.


## Évolution réalisée

- Étape collecte : 46 tests passaient après ajout des comptes, compteurs et commentaires.
- Étape analyse : tests synthétiques réels OpenCV (décodage MP4, compression, recadrage,
  ORB, ordre temporel), batch, export et cloisonnement ajoutés ; 69 tests locaux passent.
- Le parcours Chrome initial a été rejoué : mobile, ET/OU, français, capture actualisée
  pendant un glisser, annulation, saisie et TXT. Il est étendu à la sélection presse,
  aux comptes sans hashtag et au téléchargement ZIP enrichi.
- Une vérification bloque explicitement les imports des bibliothèques audiovisuelles
  et confirme que FastAPI, la sélection presse et les exports textuels fonctionnent.
- CI Linux : construction et tests des profils `INSTALL_VIDEO=0` et `1`.

Corrections de régression détectées pendant les étapes : colonnes CSV historiques
préservées malgré les métadonnées additionnelles ; création idempotente du répertoire
enrichi ; exceptions d’export séparées du TXT existant ; absence de données distinguée
de zéro ; résultats vidéo tronqués empêchant de conclure à une absence de réemploi.

Limites explicites : précision des détecteurs non calibrée sur corpus journalistique ;
aucun benchmark manuel présenté comme acquis ; disponibilité TikTok depuis le VPS
non garantie ; modèles Whisper/CLIP non téléchargés pour les tests unitaires.
Les comparaisons sont bornées au lot courant. Les groupes expriment une connectivité,
pas une identité transitive. Les fonctions de propriété éditoriale, de genre journalistique
ou de source originale ne déduisent pas ce qui n’a pas été observé.
