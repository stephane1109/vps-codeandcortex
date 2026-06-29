# Aide du tableau de bord VPS Code & Cortex

## À quoi sert la page d'accueil

La page d'accueil centralise l'état des applications hébergées sur le VPS :

- nombre de sessions actives ;
- charge totale du serveur ;
- taille de la file d'attente ;
- disponibilité de chaque application.

Elle permet surtout de savoir si une application est libre, occupée ou déjà saturée avant de l'ouvrir.

## Comprendre les statuts affichés

- `Libre` : l'application peut accueillir immédiatement un utilisateur.
- `En cours` : un utilisateur est déjà en train de travailler sur l'application.
- `File d'attente` : au moins une personne attend une place.
- `Synchronisation indisponible` : le dashboard n'arrive plus à lire Redis ; l'affichage peut être incomplet ou figé.

Sur les cartes :

- point vert : accès libre ;
- point orange : application en cours d'utilisation ou file d'attente en cours ;
- un message en haut de page signale les problèmes de synchronisation du dashboard.

## Comment libérer une application

Quand vous avez fini votre travail :

1. revenez dans l'application ;
2. cliquez sur le bouton `Libérer l'accès` si l'application l'affiche ;
3. attendez la confirmation de libération ;
4. fermez ensuite l'onglet si besoin.

Important :

- fermer l'onglet peut déclencher une libération automatique, mais ce n'est pas la méthode la plus sûre ;
- la libération manuelle reste la bonne pratique ;
- si un ticket n'est plus rafraîchi, il finit normalement par expirer automatiquement.

## Pourquoi certaines applications n'acceptent qu'un seul utilisateur

Le VPS ne travaille pas seulement avec un nombre d'utilisateurs : il gère aussi une charge globale.

La ligne `charge x/y` en haut de la page signifie :

- `x` = charge actuellement consommée ;
- `y` = capacité totale autorisée du serveur.

Sur cette architecture, la capacité globale par défaut est pilotée par `CAPACITE_SERVEUR`, généralement réglée à `6`.

Chaque application consomme un coût différent :

- les petites applications coûtent peu et peuvent accepter plusieurs sessions ;
- les grosses applications coûtent davantage et sont donc limitées à un seul utilisateur à la fois.

## Applications les plus lourdes

Les applications suivantes sont actuellement parmi les plus coûteuses en calcul et sont limitées à une seule session simultanée :

- `IRaMuTeQ Lite`
- `Symbolic Connectors`
- `Speech to text`
- `Vecteur émotionnel`
- `Analyses multi-modales`
- `StopMotion`
- `Divergence Jensen-Shannon`

## Exemples concrets

Exemple 1 :

- si `IRaMuTeQ Lite` consomme 4 points de charge sur une capacité totale de 6 ;
- il ne reste que 2 points disponibles pour le reste du serveur ;
- une autre application lourde devra donc attendre.

Exemple 2 :

- une application légère peut parfois encore démarrer ;
- mais si le nombre d'utilisateurs autorisés pour cette application est déjà atteint, elle passera quand même en file d'attente.

## Bonnes pratiques

- Évitez d'ouvrir plusieurs onglets de la même grosse application.
- Téléchargez vos résultats, puis libérez l'accès.
- Si vous voyez une file d'attente, laissez l'application ouverte et attendez votre tour.
- Si un état semble bloqué, rechargez la page d'accueil pour relire l'état courant.

## Si quelque chose semble bloqué

Si une application reste occupée alors que plus personne ne l'utilise :

- attendez quelques instants pour laisser la synchronisation se faire ;
- rechargez la page d'accueil ;
- vérifiez que l'utilisateur précédent a bien cliqué sur `Libérer l'accès` ;
- sinon, laissez expirer le ticket ou redémarrez le service concerné côté administration.

## En résumé

Le tableau de bord sert à partager proprement les ressources du VPS :

- on ouvre l'application ;
- on travaille ;
- on libère l'accès ;
- la personne suivante peut prendre la main.
