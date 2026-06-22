# Aide

## Fonctions (code)

### `parser_date(raw_date_str)`
- Convertit une date en français/anglais en `datetime` (ex. "31 décembre 2024", "June 13, 2024").
- Retourne `None` si le parsing échoue.

### `nettoyer_nom_journal(nom_journal)`
- Normalise le nom du journal et retourne un tag `*source_*`.
- Remplace espaces/apostrophes par `_` et coupe après la première virgule.

### `extraire_texte_html(...)`
- Parse le HTML Europresse et reconstruit :
  - le texte final au format IRaMuTeQ,
  - une table CSV,
  - une liste d’articles pour la détection de doublons.
- Applique les options : source, dates, variable supplémentaire, méthode d’extraction, type de contenu, suppression de balises expérimentale.

### `afficher_interface_europresse()`
- Construit l’interface Streamlit (upload, options, exports, aperçu, ZIP).

### `compter_mots(texte)`
- Compte les mots d’un texte via regex.

### `detecter_doublons_articles(articles, longueur_minimale=...)`
- Détecte les doublons par hash du corps d’article.
- Signale aussi les articles trop courts (< longueur minimale).

### `reconstruire_texte(articles)`
- Reconstruit le corpus à partir d’articles filtrés (sans doublons/courts).

### `extraire_apercu(article, longueur=200)`
- Génère un court aperçu pour affichage dans l’UI (doublons/courts).

## Options (interface)

### Upload
- **Importer un fichier HTML Europresse** : charge le fichier source à traiter.

### Options de métadonnées (ligne `****`)
- **Inclure le nom du journal** (`*source_*`).
- **Inclure la date (année-mois-jour)** (`*date_YYYY-MM-DD`).
- **Inclure la date (année-mois)** (`*am_YYYY-MM`).
- **Inclure l'année uniquement** (`*annee_YYYY`).
- **Variable supplémentaire (optionnel)** (`*votre_tag`).

### Méthode d’extraction du journal
- **Méthode normale** : extraction brute du nom du journal.
- **Méthode clean** : extraction avec nettoyage/formatage du nom du journal.

### Nettoyage expérimental
- **Supprimer les balises contenant “Edito”, “AUTRE”, ...** : nettoyage supplémentaire (expérimental).
- **Regex additionnelle (optionnelle)** : filtre appliqué au texte complet de l’article (tout le corpus). Les correspondances sont supprimées (sensible à la casse).

Détails sur la suppression par termes (option expérimentale) :
  - Les termes saisis `complètent le dictionnaire par défaut`.
  - La comparaison est `sensible à la casse` (ex: « Autre » ne supprime pas « autre »).
  - La recherche `ne scanne pas tout le texte` : elle cible uniquement les balises `<p>` avec la classe `sm-margin-bottomNews` et les balises `<div>`.

### Contenu à exporter
- **Texte complet**
- **Titre uniquement**
- **Chapeau uniquement**
- **Titre + chapeau**

### Recherche de doublons
- **Recherche de doublons** : active la détection par hash.
- **Longueur minimale (mots)** : seuil pour signaler les articles trop courts.

### Export
- **Exporter le corpus sans doublons** : supprime les doublons détectés.
- **Exporter le corpus sans les articles trop courts** : filtre par longueur minimale.
- **Télécharger les fichiers (ZIP)** : génère `.txt`, `.csv`, `.xlsx` dans un ZIP.

## Aide regex (rappels essentiels)

Ces motifs s’utilisent dans le champ **Regex additionnelle** (sans préfixe `r`) pour filtrer davantage les balises lors du nettoyage expérimental.

### Principales règles
- **Début/fin de ligne** : `^` (début), `$` (fin).  
  *Ex.* `^Le Figaro` (commence par “Le Figaro”).
- **Alternatives (OU)** : `motif1|motif2` pour une seule regex avec plusieurs options.  
  *Ex.* `\bPage\s*3\b|\bAnnexe\b`.
- **Conditions (ET)** : séparer plusieurs regex par `ET` pour appliquer plusieurs règles.  
  *Ex.* `\bPage\s*2\b ET \bPage\s*3\b` (chaque motif est évalué).  
  *(Pour exiger la présence simultanée : lookaheads comme `(?=.*\bPage\b)(?=.*\b3\b)`.)*
- **Classes de caractères** : `[A-Z]` (lettres majuscules), `[0-9]` (chiffres).  
  *Ex.* `^Page [0-9]+$`.
- **Quantificateurs** : `*` (0+), `+` (1+), `?` (0 ou 1), `{m,n}` (entre m et n).  
  *Ex.* `\s*` (espaces optionnels), `\d{2,4}`.
- **Caractères spéciaux** : `.` (n’importe quel caractère), `\s` (espaces), `\d` (chiffres), `\w` (lettres/chiffres/underscore), `\b` (frontière de mot).
- **Groupes** : `(…)` pour regrouper.  
  *Ex.* `^(Page|Annexe)\s*\d+$`.
- **Échapper un caractère spécial** : précéder par `\`.  
  *Ex.* `\.` pour un point, `\(` pour une parenthèse.

### Exemples utiles
- **Supprimer “Page 3”, “Page 12”** : `\bPage\s*\d+\b`
- **Supprimer une mention de source** : `^Source\s*:`
- **Supprimer les mentions “Annexe A/B”** : `\bAnnexe\s*[A-Z]\b`

### Cas demandé : 3 règles séparées à saisir dans l’interface
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

#### Comment les intégrer dans le champ
- Ouvrir l’interface et aller dans **Nettoyage expérimental → Regex additionnelle (optionnelle)**.  
- **Saisir une seule règle à la fois** pour vérifier le résultat.  
- Si besoin de combiner, utiliser l’alternative `|` :  
  `\bPage\s*12\b|\bPage\b|\b3\b`  
  (cela appliquera les trois règles en une seule expression).
