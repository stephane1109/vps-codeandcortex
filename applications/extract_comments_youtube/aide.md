# Aide - cle API YouTube et quotas

Cette application a besoin d'une **cle API YouTube Data v3** pour lire les
commentaires publics d'une video YouTube.

## A quoi sert la cle API

La cle API permet a l'application d'envoyer des requetes a l'API officielle de
YouTube pour :

- lire les metadonnees d'une video
- recuperer les commentaires publics
- recuperer eventuellement les reponses aux commentaires

Sans cle API valide, l'application ne peut pas fonctionner.

## Ou creer la cle API

La cle se cree dans **Google Cloud Console**.

Etapes generales :

1. Ouvre Google Cloud Console.
2. Connecte-toi avec ton compte Google.
3. Cree un projet ou choisis un projet existant.
4. Active l'API **YouTube Data API v3**.
5. Cree des **identifiants** de type **API key**.
6. Copie la cle et colle-la dans l'application.

## Procedure pas a pas

### 1. Creer ou choisir un projet Google Cloud

1. Va sur : https://console.cloud.google.com/
2. Connecte-toi.
3. En haut de la page, clique sur le selecteur de projet.
4. Cree un nouveau projet ou choisis un projet deja existant.

### 2. Activer YouTube Data API v3

1. Dans le menu Google Cloud, ouvre `APIs & Services`.
2. Clique sur `Library`.
3. Recherche : `YouTube Data API v3`
4. Ouvre la fiche de l'API.
5. Clique sur `Enable`.

Tant que cette API n'est pas activee dans le projet, la cle ne suffira pas.

### 3. Creer la cle API

1. Va dans `APIs & Services`
2. Clique sur `Credentials`
3. Clique sur `Create Credentials`
4. Choisis `API key`
5. Google affiche alors une nouvelle cle
6. Copie cette cle

Cette cle pourra ensuite etre :

- soit collee directement dans l'interface de l'application
- soit placee dans Coolify avec la variable d'environnement `YOUTUBE_API_KEY`

## Comment utiliser la cle dans l'application

Tu as deux possibilites :

### Option 1 - dans l'interface

Tu colles la cle API dans le champ prevu dans l'application.

### Option 2 - dans Coolify

Tu ajoutes la variable d'environnement :

```env
YOUTUBE_API_KEY=ta_cle_api
```

Cela permet de pre-remplir automatiquement la cle dans l'interface.

## Quotas YouTube API - principe

L'API YouTube fonctionne avec un **quota journalier**.

Chaque requete consomme un certain nombre d'unites de quota.

En pratique :

- ton projet Google Cloud recoit un quota quotidien
- chaque appel API utilise une partie de ce quota
- quand le quota est epuise, l'application renvoie une erreur du type :
  - `quotaExceeded`
  - `dailyLimitExceeded`

## Ce qu'il faut retenir sur les quotas

Pour cette application :

- lire les informations d'une video consomme peu
- recuperer beaucoup de commentaires consomme davantage
- recuperer les reponses ajoute encore des requetes supplementaires

Donc :

- plus tu demandes de commentaires
- plus tu explores de reponses
- plus tu consommes ton quota journalier

## Symptomes d'un quota depasse

Si le quota est atteint, tu peux voir des messages comme :

- `quotaExceeded`
- `dailyLimitExceeded`
- `La limite quotidienne de l'API YouTube est atteinte pour cette cle`

Dans ce cas, il faut :

1. attendre le renouvellement du quota
2. ou utiliser une autre cle API rattachee a un autre projet autorise

## Bonnes pratiques

Pour eviter d'user trop vite le quota :

1. teste d'abord avec un petit nombre de commentaires
2. n'active les reponses que si tu en as besoin
3. evite de relancer beaucoup de fois la meme extraction complete

## Securiser la cle API

Une cle API doit etre traitee avec prudence.

Bonnes pratiques :

- ne pas publier la cle dans un depot public
- ne pas l'envoyer en clair dans des documents publics
- la stocker de preference dans Coolify comme variable d'environnement

Si besoin, tu peux aussi restreindre la cle dans Google Cloud.

## Restriction de cle - attention

Google permet de restreindre une cle API.

Tu peux par exemple limiter :

- les API autorisees
- les adresses IP
- certains usages applicatifs

Mais attention :

- si tu restreins trop fort, l'application peut cesser de fonctionner
- si tu limites par IP, il faut utiliser l'IP publique de ton VPS

Le plus simple est souvent :

1. restreindre la cle a `YouTube Data API v3`
2. tester
3. ajouter ensuite des restrictions supplementaires seulement si necessaire

## Resume rapide

1. creer un projet dans Google Cloud
2. activer `YouTube Data API v3`
3. creer une `API key`
4. coller la cle dans l'application ou dans `YOUTUBE_API_KEY`
5. surveiller le quota si tu recuperes beaucoup de commentaires
