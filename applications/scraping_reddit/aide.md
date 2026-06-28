# Aide - creer les identifiants Reddit API

Cette application a besoin de trois informations pour interroger Reddit :

- `client_id`
- `client_secret`
- `user_agent`

## A quoi servent ces informations

Reddit demande qu'une application API soit declaree dans ton compte Reddit.

Ensuite :

- le `client_id` identifie l'application
- le `client_secret` sert a authentifier l'application
- le `user_agent` decrit ton script de facon lisible pour Reddit

## Ce qu'il faut avoir avant de commencer

Il te faut :

1. un compte Reddit
2. etre connecte a ce compte dans le navigateur

## Ou creer l'application Reddit

La page a utiliser est en pratique :

- `https://www.reddit.com/prefs/apps`

Si Reddit redirige vers une page de connexion, reconnecte-toi puis reviens sur
la meme URL.

## Procedure pas a pas

### 1. Ouvrir la page des applications Reddit

1. Connecte-toi a Reddit.
2. Ouvre `https://www.reddit.com/prefs/apps`
3. Descends vers la zone des applications personnelles.

### 2. Creer une nouvelle application

1. Clique sur `create app` ou `create another app`
2. Renseigne un nom d'application

Exemple :

- `scraping_reddit_codeandcortex`

### 3. Choisir le bon type d'application

Pour cette application Streamlit, le choix le plus simple est generalement :

- `script`

Pourquoi :

- l'application fait surtout de la lecture
- elle utilise des identifiants applicatifs simples
- c'est le format classique pour un usage personnel ou serveur

### 4. Renseigner les champs principaux

Champs courants a completer :

- `name` : nom libre de ton application
- `type` : `script`
- `description` : optionnel
- `about url` : optionnel
- `redirect uri` : requis par Reddit dans beaucoup de cas

Pour `redirect uri`, si tu n'as pas de besoin OAuth complexe, tu peux souvent
mettre une valeur technique simple, par exemple :

- `http://localhost:8080`

ou

- `http://127.0.0.1:8080`

## Recuperer le client_id et le client_secret

Une fois l'application creee :

- le `client_id` est en general la petite chaine affichee sous le nom de l'application
- le `client_secret` est la valeur affichee a cote de `secret`

En pratique :

1. cree l'application
2. reviens sur la fiche
3. copie le `client_id`
4. copie le `secret`

## Creer le user_agent

Le `user_agent` n'est pas fourni par Reddit : c'est toi qui le choisis.

Il doit etre explicite et lisible.

Format conseille :

```text
plateforme:nom_app:version (by u/ton_compte_reddit)
```

Exemples :

```text
web:scraping_reddit:1.0 (by u/mon_compte)
```

```text
script:codeandcortex_reddit_scraper:1.0 (by u/mon_compte)
```

Evite :

- `test`
- `python script`
- des valeurs trop vagues

## Comment utiliser ces informations dans l'application

Dans l'application `Scraper Reddit`, remplis :

- `Client ID`
- `Client Secret`
- `User Agent`

Tu peux aussi pre-remplir ces valeurs via des variables d'environnement :

```env
REDDIT_CLIENT_ID=ton_client_id
REDDIT_CLIENT_SECRET=ton_client_secret
REDDIT_USER_AGENT=web:scraping_reddit:1.0 (by u/ton_compte)
```

## Bonnes pratiques de securite

Le `client_secret` doit rester prive.

Conseils :

- ne pas le publier dans un depot Git public
- ne pas l'ecrire dans un document partage publiquement
- le stocker plutot dans Coolify comme variable d'environnement

## Erreurs frequentes

### 1. Mauvais type d'application

Si tu choisis un type autre que `script`, l'usage peut devenir plus complique.

### 2. Client ID / secret inverses

Le `client_id` et le `client_secret` ne sont pas la meme chose.

### 3. User agent trop vague

Reddit prefere un `user_agent` descriptif.

### 4. Compte Reddit non connecte

Si tu n'es pas connecte, la page `prefs/apps` peut rediriger vers la connexion.

## Resume rapide

1. se connecter a Reddit
2. ouvrir `https://www.reddit.com/prefs/apps`
3. creer une application
4. choisir `script`
5. renseigner un `redirect uri` simple si Reddit le demande
6. copier le `client_id`
7. copier le `client_secret`
8. creer un `user_agent` lisible
9. coller les trois valeurs dans l'application
