### Analyse de l’onglet TF-IDF
- L’onglet est branché sur la fonction `render_tfidf_tab` de `tf_idf.py`, via `onglet_tfidf.rendu_tfidf`. Le paramètre `filtered_connectors` transmis par les autres onglets est explicitement ignoré (`del tab, filtered_connectors`), ce qui signifie qu’aucun filtrage par connecteurs n’est appliqué dans cet onglet.

- Le calcul TF-IDF repose uniquement sur les textes regroupés par modalité et, de façon optionnelle, sur la suppression des stopwords français fournis par NLTK lorsque l’utilisateur coche la case correspondante. Aucun traitement spécifique des connecteurs n’est prévu : le choix se limite à “avec” ou “sans” stopwords NLTK.



L’onglet “TF-IDF” n’utilise pas le dictionnaire de connecteurs : il analyse les textes tels quels, avec pour seule option la suppression des stopwords français NLTK via la case à cocher. Si cette case n’est pas cochée, les connecteurs restent dans le texte ; si elle l’est, seuls les stopwords NLTK sont retirés (pas les connecteurs spécifiques de votre dictionnaire).
