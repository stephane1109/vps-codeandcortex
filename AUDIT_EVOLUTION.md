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
  ORB, ordre temporel), batch, export et cloisonnement ajoutés ; 71 tests locaux passent.
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


## Interface Streamlit (évolution demandée ensuite)

L’accueil devient une interface Streamlit minimaliste. Le moteur, FastAPI et la
fenêtre de contrôle historique restent conservés. Un relais privé HTTP/WebSocket
maintient un seul port public et l’isolation des sessions. Les méthodes SHA-256 et
pHash/ORB/temps sont accessibles dans le menu **Options vidéo (facultatif)**
de l’onglet Collecte ; leurs choix sont transmis au moteur. L’onglet Aide explique
les méthodes. L’accueil est servi à la racine, avec redirection des anciens liens.
Le profil texte affiche les options même sans dépendances vidéo, avec un message
sur leur indisponibilité. Les dates, ET/OU, le français, les commentaires et exports
sont repris dans le formulaire Streamlit. Les anciennes fonctions restent testées.

89 tests unitaires/API/Streamlit passent localement, avec contrôle de l’origine du
WebSocket, indépendance des méthodes et absence de calcul ORB quand il est désactivé.
La CI ajoute un parcours Chrome propre à Streamlit, incluant sa fenêtre de contrôle.
Les tests de gestes restent synthétiques : ils ne résolvent pas un CAPTCHA TikTok réel.


L’interface vidéo est réduite aux fichiers identiques et aux séquences communes.
Les réglages de modèles et d’administration restent hors du formulaire. Le profil
Docker standard installe les dépendances de comparaison sans les modèles lourds ;
les profils texte et audiovisuel avancé restent disponibles. La disponibilité est
contrôlée à partir des modules et de ffmpeg, pas uniquement d’une variable.
Un test lance le vrai sous-processus via l’API sur quatre MP4 synthétiques : copie
exacte, séquence recadrée et vidéo différente, avec vérification du ZIP final.
Il ne garantit pas qu’une vidéo TikTok distante sera téléchargeable depuis le VPS.
