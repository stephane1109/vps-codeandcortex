# Symbolic Connectors - version VPS

Application Streamlit pour explorer des corpus formates selon la norme **IRaMuTeQ** et y detecter des structures linguistiques typiques du "langage machine" : connecteurs logiques, motifs regex, patterns spaCy, densite, n-grams, TF-IDF, similarite cosinus, etc.

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- conteneur Docker autonome pour Streamlit
- cache d'import isole par session utilisateur au lieu d'un fichier global dans `/tmp`
- preinstallation des stopwords NLTK a la build
- compatibilite Coolify via `PORT`, `STREAMLIT_SERVER_BASE_URL_PATH` et `APP_DATA_DIR`
- configuration headless adaptee a un usage serveur

## Fonctionnalites principales

- **Import IRaMuTeQ** : televersement d'un fichier texte ou chaque article debute par une ligne d'en-tete `**** *variable_modalite`
- **Connecteurs symboliques** : filtrage et annotation des connecteurs a partir du dictionnaire `dictionnaires/connecteurs.json`
- **Analyses linguistiques** : densite, OpenLexicon, regex, patterns spaCy, n-grams, TF-IDF, similarite cosinus, chi2, etc.
- **Mode annotation** : import d'un texte brut et export JSON/Markdown des labels

## Lancer localement avec Docker

```bash
docker build -t symbolic-connectors .
docker run --rm -p 8501:8501 symbolic-connectors
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `APP_DATA_DIR` : cache local par session
- `APP_SESSION_TTL_HOURS` : duree de retention des sessions temporaires

## Structure des donnees attendue

Chaque article doit commencer par une ligne d'en-tete contenant les variables precedees d'un asterisque, par exemple :

```text
**** *model_gpt *prompt_1
Texte de l'article...
```

## Notes

- Le modele spaCy francais `fr_core_news_md` est installe via `requirements.txt`.
- Les stopwords NLTK sont telecharges a la build Docker pour eviter un acces reseau au runtime.
- Les tests `pytest` du projet source peuvent etre reutilises localement si besoin, mais ils ne sont pas necessaires au fonctionnement de l'application deployee.
