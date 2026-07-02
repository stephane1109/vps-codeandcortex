# Module NLP - langue et dictionnaires spaCy
# Ce fichier regroupe la détection de langue du corpus, la vérification de cohérence
# entre langue estimée et langue sélectionnée, ainsi que la configuration des modèles
# spaCy et le chargement (caché) des stopwords par langue.

estimer_langue_corpus <- function(textes, rv = NULL, max_segments = 200) {
  if (is.null(textes) || length(textes) == 0) return(list(code = NA_character_, scores = c(fr = 0, en = 0, es = 0)))

  textes <- as.character(textes)
  textes <- textes[nzchar(trimws(textes))]
  if (length(textes) == 0) return(list(code = NA_character_, scores = c(fr = 0, en = 0, es = 0)))
  if (length(textes) > max_segments) textes <- textes[seq_len(max_segments)]

  tok <- quanteda::tokens(textes, remove_punct = TRUE, remove_numbers = TRUE)
  tok <- quanteda::tokens_tolower(tok)
  all_tokens <- unlist(as.list(tok), use.names = FALSE)
  all_tokens <- trimws(all_tokens)
  all_tokens <- all_tokens[nzchar(all_tokens)]

  if (length(all_tokens) == 0) return(list(code = NA_character_, scores = c(fr = 0, en = 0, es = 0)))

  scores <- c(
    fr = mean(all_tokens %in% obtenir_stopwords_spacy("fr", rv = rv)),
    en = mean(all_tokens %in% obtenir_stopwords_spacy("en", rv = rv)),
    es = mean(all_tokens %in% obtenir_stopwords_spacy("es", rv = rv))
  )

  langue <- names(scores)[which.max(scores)]
  list(code = langue, scores = scores)
}

verifier_coherence_dictionnaire_langue <- function(textes, langue_selectionnee, rv = NULL) {
  est <- estimer_langue_corpus(textes, rv = rv)
  if (is.na(est$code)) return(invisible(est))

  sel <- configurer_langue_spacy(langue_selectionnee)$code
  sc_sel <- as.numeric(est$scores[[sel]])
  sc_best <- as.numeric(max(est$scores))
  marge <- sc_best - sc_sel

  if (!identical(sel, est$code) && sc_best >= 0.02 && marge >= 0.01) {
    cfg_sel <- configurer_langue_spacy(sel)
    cfg_best <- configurer_langue_spacy(est$code)
    stop(
      paste0(
        "Langue incohérente : le corpus ressemble à du ", cfg_best$libelle,
        " mais le dictionnaire spaCy sélectionné est ", cfg_sel$libelle,
        ". Choisis le dictionnaire ", cfg_best$libelle, " avant de lancer l'analyse."
      )
    )
  }

  invisible(est)
}

configurer_langue_spacy <- function(langue) {
  if (is.null(langue) || !nzchar(as.character(langue))) langue <- "fr"
  langue <- trimws(tolower(as.character(langue)))
  if (!langue %in% c("fr", "en", "es")) langue <- "fr"

  switch(
    langue,
    fr = list(code = "fr", libelle = "Français", modele = "fr_core_news_md", stopwords_module = "fr"),
    en = list(code = "en", libelle = "Anglais", modele = "en_core_web_md", stopwords_module = "en"),
    es = list(code = "es", libelle = "Espagnol", modele = "es_core_news_md", stopwords_module = "es"),
    list(code = "fr", libelle = "Français", modele = "fr_core_news_md", stopwords_module = "fr")
  )
}

obtenir_stopwords_spacy <- local({
  cache <- new.env(parent = emptyenv())

  function(langue_spacy = "fr", rv = NULL) {
    cfg <- configurer_langue_spacy(langue_spacy)
    code <- cfg$code

    if (exists(code, envir = cache, inherits = FALSE)) {
      return(get(code, envir = cache, inherits = FALSE))
    }

    python_cmd <- Sys.which("python3")
    if (!nzchar(python_cmd)) python_cmd <- Sys.which("python")

    if (nzchar(python_cmd)) {
      py_code <- paste(
        paste0("from spacy.lang.", cfg$stopwords_module, ".stop_words import STOP_WORDS"),
        "for w in sorted(STOP_WORDS):",
        "    print(w)",
        sep = "\n"
      )

      sortie <- tryCatch(
        system2(python_cmd, args = c("-c", shQuote(py_code)), stdout = TRUE, stderr = TRUE),
        error = function(e) character(0)
      )

      if (length(sortie) > 0) {
        stopwords_spacy <- trimws(sortie)
        stopwords_spacy <- stopwords_spacy[nzchar(stopwords_spacy)]
        stopwords_spacy <- stopwords_spacy[!grepl("^Traceback", stopwords_spacy)]

        if (length(stopwords_spacy) > 0) {
          sw <- unique(stopwords_spacy)
          assign(code, sw, envir = cache)
          if (!is.null(rv)) {
            ajouter_log(rv, paste0("Stopwords spaCy chargés (", cfg$libelle, ") : ", length(sw), " termes."))
          }
          return(sw)
        }
      }
    }

    assign(code, character(0), envir = cache)
    if (!is.null(rv)) {
      ajouter_log(rv, paste0("Impossible de charger les stopwords spaCy pour ", cfg$libelle, "."))
    }
    get(code, envir = cache, inherits = FALSE)
  }
})
