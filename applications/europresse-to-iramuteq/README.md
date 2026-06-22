-----------------------------------------
### Projet : Europresse to IRaMuTeQ - Appli streamlit Cloud
- Auteur : Stéphane Meurisse
- Contact : stephane.meurisse@gmail.com
- Site Web : https://www.codeandcortex.fr
- Appli : https://europress-to-iramuteq-v4.streamlit.app/
- LinkedIn : https://www.linkedin.com/in/st%C3%A9phane-meurisse-27339055/
- Date : 17 janvier 2026
- Version : 4
- Licence : Ce programme est un logiciel libre : vous pouvez le redistribuer selon les termes de la Licence Publique Générale GNU v3

-----------------------------------------
### Librairies 
- pip install streamlit beautifulsoup4 pandas lxml html5lib

-----------------------------------------
### Déploiement OVH / Coolify

Le projet inclut maintenant les fichiers nécessaires pour un déploiement sur **VPS OVH** via **Coolify** :

- `Dockerfile`
- `docker-entrypoint.sh`
- `.streamlit/config.toml`
- `DEPLOIEMENT_OVH_COOLIFY.md`

Exemple de sous-domaine cible :

- `europressetoiramuteq.codeandcortex.fr`

Lancez localement le conteneur avec :

```bash
docker build -t europress-to-iramuteq .
docker run --rm -p 8501:8501 europress-to-iramuteq
```

La procédure complète pour Coolify et le DNS OVH est documentée dans `DEPLOIEMENT_OVH_COOLIFY.md`.

-----------------------------------------
### Licence
Cette application est distribuée sous la licence GNU v3.  
Toute réutilisation ou modification de ce projet doit respecter les termes de cette licence.  
L'exploitation commerciale de ce projet est interdite sans autorisation.

-----------------------------------------
### Fonctionnalités
- Reconstruction des noms de journaux (version longue et abrégée).
- Conversion des dates en plusieurs formats.
- Nettoyage de multiples balises inutiles, URL et noms d’auteurs
- Export au format texte et CSV.

-----------------------------------------
### Fonctionnement du script (règles et options)

Cette application Streamlit lit un fichier HTML exporté depuis Europresse, extrait chaque article, nettoie le contenu et construit
un corpus compatible IRaMuTeQ. Les sorties sont générées en **TXT**, **CSV** et **XLSX** (dans un ZIP). Les règles principales sont
décrites ci-dessous.

#### 1) Détection et parsing des dates
- La fonction `parser_date` convertit une date française (ex. `31 décembre 2024`) ou anglaise (ex. `June 13, 2024`) en objet `datetime`.
- Un dictionnaire mappe les mois français vers les mois anglais pour permettre l’usage de `datetime.strptime`.
- Les dates sont ensuite converties en trois formats IRaMuTeQ :
  - `*date_YYYY-MM-DD` (année-mois-jour)
  - `*am_YYYY-MM` (année-mois)
  - `*annee_YYYY` (année)

#### 2) Extraction du nom du journal
- Le nom du journal est récupéré dans `div.rdp__DocPublicationName > span.DocPublicationName`.
- Il est normalisé via `nettoyer_nom_journal` :
  - suppression de tout ce qui suit une virgule,
  - remplacement des espaces/apostrophes par `_`,
  - préfixe `*source_` pour IRaMuTeQ.
- Deux méthodes existent :
  - **Méthode normale (0)** : extraction directe du texte (formatage minimal),
  - **Méthode clean (1)** : extraction par liste de fragments (`stripped_strings`) pour éviter des résidus de mise en forme.

#### 3) Extraction et nettoyage du contenu article
Pour chaque `<article>` :
- Le texte brut est récupéré via `article.get_text` puis nettoyé. Les sections non pertinentes (header, aside, footer, images, liens)
  sont supprimées. Des balises `<i>` et `<em>` sont conservées mais déroulées (unwrap).
- Option **expérimentale** : suppression conditionnelle de blocs contenant des rubriques (ex. “Edito”, “Opinions”, “Débats”, ...)
- Détails sur la suppression par termes (option expérimentale) :
  - Les termes saisis **complètent** le dictionnaire par défaut.
  - La comparaison est **sensible à la casse** (ex: « Autre » ne supprime pas « autre »).
  - La recherche **ne scanne pas tout le texte** : elle cible uniquement
    - les balises `<p>` avec la classe `sm-margin-bottomNews` (suppression si un terme est **contenu** dans le texte) ;
    - les balises `<div>` (suppression si le texte est **exactement égal** à un terme).
- Le titre est conservé dans le texte final (pas de suppression de la balise titre).
- Les mentions de journal/date brut sont retirées du texte (`re.sub`).
- Les sauts de lignes sont aplatis, les URLs “(lien : …)” sont retirées, et la première ligne reçoit un point final si besoin.

#### 4) En-tête IRaMuTeQ et construction du corpus
- Chaque article est précédé d’une ligne “étoilée” commençant par `****`, puis des variables (`*source_`, `*date_`, `*am_`,
  `*annee_`, variable utilisateur).
- Le corpus final est la concaténation des articles avec un saut de ligne entre chaque bloc.

#### 5) Détection des doublons (optionnel)
- Activée via “Recherche de doublons”.
- Un hash SHA-256 est calculé sur le corps de chaque article pour identifier les doublons. Le plus long article est conservé si
  deux articles partagent le même hash.
- Les articles “trop courts” sont listés si leur nombre de mots est inférieur au seuil configurable (300 mots par défaut).
- L’utilisateur peut exporter un corpus sans doublons et/ou sans articles courts. Le texte est reconstruit à partir des articles
  retenus.

#### 6) Exports générés
- **TXT** : corpus IRaMuTeQ complet.
- **CSV** : colonnes `Journal`, `Année-mois-jour`, `Année-mois`, `Année`, `Article`.
- **XLSX** : export Excel des mêmes colonnes (via pandas).
- Les trois fichiers sont dans un ZIP, nommé à partir du fichier HTML d’origine.

-----------------------------------------
### Aide regex

Ces motifs s’utilisent dans le champ Regex additionnelle (sans préfixe r) pour filtrer davantage les balises lors du nettoyage expérimental.
Principales règles

#### Exemple de 3 règles séparées à saisir dans l’interface
Ces trois règles sont **indépendantes**. L’utilisateur peut les tester **une par une** dans le champ **Regex additionnelle** selon le besoin.

1. **Supprimer exactement “Page 12”**  
   - **Regex** : `\bPage\s*12\b`  
   - **Effet** : supprime uniquement la balise qui contient “Page 12” (espaces facultatifs).  

2. **Supprimer le mot “Page” seul**  
   - **Regex** : `\bPage\b`  
   - **Effet** : supprime toute balise contenant le mot “Page”, sans imposer de numéro.  

3. **Supprimer le chiffre “3” seul**  
   - **Regex** : `\b3\b`  
   - **Effet** : supprime toute balise contenant le chiffre “3” en tant que mot isolé.  

#### Comment les intégrer dans le champ Regex
- Ouvrir l’interface et aller dans **Nettoyage expérimental → Regex additionnelle (optionnelle)**.  
- **Saisir une seule règle à la fois** pour vérifier le résultat.  
- Si besoin de combiner, utiliser l’alternative `|` :  
  `\bPage\s*12\b|\bPage\b|\b3\b`  
  (cela appliquera les trois règles en une seule expression).

-----------------------------------------
### Utilisation
1. Rendez-vous sur l'application [Europresse to IRaMuTeQ] : https://europress-to-iramuteq-v4.streamlit.app/
2. Glissez-déposez vos fichiers HTML pour les traiter.
3. Téléchargez les résultats au format texte ou CSV.
