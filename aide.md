# Aide - cookies YouTube pour extraction-multimedia

Article du blog :

- https://www.codeandcortex.fr/extraction-multimedia-youtube/

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
