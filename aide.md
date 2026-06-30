# Aide - cookies YouTube pour extraction-multimedia

Ce document explique comment generer un `cookies.txt` pour aider `yt-dlp`
quand YouTube affiche un blocage du type :

- `Sign in to confirm you're not a bot`
- `Use --cookies-from-browser or --cookies`

Oui, **cela fonctionne avec Firefox et avec Chrome**, a condition :

- d'etre connecte a YouTube dans le navigateur
- d'exporter un cookies recent
- d'utiliser idealement la meme IP publique que celle utilisee pour ouvrir YouTube
- de fournir un fichier au format `cookies.txt` compatible Netscape

## Principe

L'application accepte un fichier `cookies.txt` exporte depuis ton navigateur.
Ce fichier permet a `yt-dlp` de reutiliser ta session YouTube pour acceder a
des videos que YouTube protege davantage contre les robots.

## Methode recommandee avant export

Avant d'exporter le cookies :

1. Ouvre YouTube dans ton navigateur.
2. Connecte-toi a ton compte si besoin.
3. Ouvre directement la video que tu veux traiter.
4. Verifie que la video se lance bien dans le navigateur.
5. Exporte ensuite le cookies sans fermer l'onglet.

## Firefox - extension cookies.txt

### Installer l'extension

1. Ouvre Firefox.
2. Va sur le site des modules Firefox.
3. Recherche l'extension `cookies.txt`.
4. Installe l'extension.

Lien souvent utilise :

- https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/

### Exporter le cookies

1. Ouvre `youtube.com` dans Firefox.
2. Connecte-toi si necessaire.
3. Ouvre la video cible.
4. Clique sur l'icone de l'extension `cookies.txt`.
5. Exporte le fichier.
6. Verifie que le fichier se nomme bien `cookies.txt`.

### Importer dans l'application

1. Ouvre l'application `Extraction multimedia`.
2. Dans la section `Cookies YouTube (optionnel)`, envoie le fichier `cookies.txt`.
3. Si un ancien cookies est deja present, coche `Forcer le remplacement`.
4. Relance le traitement.

## Chrome - extension cookies.txt

Oui, **Chrome marche aussi**, si tu utilises une extension capable d'exporter
un `cookies.txt` au format Netscape.

### Installer l'extension

1. Ouvre Chrome.
2. Va sur le Chrome Web Store.
3. Recherche une extension `cookies.txt` ou une extension d'export de cookies
   compatible Netscape.
4. Installe l'extension.

Important :

- l'extension doit permettre un **export au format Netscape**
- un simple export JSON n'est pas suffisant pour `yt-dlp`

### Exporter le cookies

1. Ouvre `youtube.com` dans Chrome.
2. Connecte-toi a ton compte si necessaire.
3. Ouvre la video cible.
4. Clique sur l'extension.
5. Exporte le fichier `cookies.txt`.
6. Enregistre-le sur ton ordinateur.

### Importer dans l'application

1. Ouvre l'application `Extraction multimedia`.
2. Envoie le nouveau `cookies.txt`.
3. Coche `Forcer le remplacement` si un ancien fichier est memorise.
4. Relance le traitement.

## Conseils si YouTube bloque encore

Si l'erreur persiste, essaye dans cet ordre :

1. Recharge YouTube dans le navigateur.
2. Verifie que la video est bien lisible a la main.
3. Re-exporte un **nouveau** `cookies.txt`.
4. Reimporte-le dans l'application avec `Forcer le remplacement`.
5. Utilise le meme navigateur pour recuperer aussi le `User-Agent`.
6. Colle ce `User-Agent` dans le champ prevu dans l'application.

## Recuperer le User-Agent du navigateur

Quand YouTube est strict, il vaut mieux utiliser un `User-Agent` coherent avec
le navigateur qui a servi a exporter le cookies.

Exemple de methode simple :

1. Ouvre le navigateur utilise pour exporter le cookies.
2. Va sur un site qui affiche le `User-Agent`.
3. Copie la valeur complete.
4. Colle-la dans le champ `User-Agent navigateur` de l'application.

## Erreurs frequentes

### 1. Le cookies est trop ancien

YouTube peut refuser un cookies exporte il y a plusieurs heures ou plusieurs
jours. Refaire un export recent resout souvent le probleme.

### 2. Mauvais format de fichier

Si le fichier n'est pas un vrai `cookies.txt` Netscape, `yt-dlp` ne pourra pas
l'utiliser correctement.

### 3. Ancien cookies conserve dans la session

Si tu importes un nouveau fichier sans cocher `Forcer le remplacement`, l'ancien
cookies peut rester en place.

### 4. Video testee sur un autre navigateur

Le meilleur resultat est obtenu quand :

- la video a ete ouverte dans le meme navigateur
- le cookies vient de ce meme navigateur
- le `User-Agent` vient aussi de ce meme navigateur

## Resume rapide

Pour maximiser les chances de succes :

1. ouvre la video sur YouTube dans Firefox ou Chrome
2. exporte un `cookies.txt` recent avec l'extension `cookies.txt`
3. importe ce fichier dans l'application
4. coche `Forcer le remplacement` si besoin
5. colle le `User-Agent` du meme navigateur
6. relance l'extraction
