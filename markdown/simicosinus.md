### Fonctionnement de l’onglet "Simi cosinus"

- L’onglet repose sur `onglet_simi_cosinus.rendu_simi_cosinus`, qui agrège les textes par modalités via `simicosinus.aggregate_texts_by_variables`, vectorise chaque regroupement avec `TfidfVectorizer` puis calcule une matrice de similarité cosinus (`compute_cosine_similarity_matrix`).
- Le principe suivi est l’inverse de la génération d’une réponse par LLM : comme les LLM s’appuient sur des embeddings pour générer du texte, ici on vectorise la réponse textuelle (le contenu du corpus) pour mesurer la proximité entre deux groupes de textes au moyen du cosinus.
- Le filtrage des données se limite aux variables et modalités sélectionnées dans l’interface Streamlit ; les textes sont pris tels quels pour chaque groupe retenu.
- Aucune segmentation préalable ni filtrage par le dictionnaire de connecteurs n’est appliqué : l’analyse s’effectue sur le texte complet, avec pour seule option la suppression des stopwords français fournis par NLTK (case à cocher « Appliquer les stopwords français (NLTK) avant le calcul »).
