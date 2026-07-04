# Module NLP - langue et stopwords quanteda
# Ce fichier gère la détection simple de langue du corpus, la vérification de
# cohérence entre langue estimée et langue sélectionnée, ainsi que le chargement
# des stopwords utilisés par quanteda.

configurer_langue_corpus <- function(langue) {
  if (is.null(langue) || !nzchar(as.character(langue))) langue <- "fr"
  langue <- trimws(tolower(as.character(langue)))
  if (!langue %in% c("fr", "en", "es")) langue <- "fr"

  switch(
    langue,
    fr = list(code = "fr", libelle = "Français"),
    en = list(code = "en", libelle = "Anglais"),
    es = list(code = "es", libelle = "Espagnol"),
    list(code = "fr", libelle = "Français")
  )
}

obtenir_stopwords_quanteda <- local({
  cache <- new.env(parent = emptyenv())

  function(langue = "fr", rv = NULL) {
    cfg <- configurer_langue_corpus(langue)
    code <- cfg$code

    if (exists(code, envir = cache, inherits = FALSE)) {
      return(get(code, envir = cache, inherits = FALSE))
    }

    sw <- tryCatch(
      unique(as.character(quanteda::stopwords(language = code))),
      error = function(e) character(0)
    )

    sw <- trimws(sw)
    sw <- sw[nzchar(sw)]

    assign(code, sw, envir = cache)
    if (!is.null(rv)) {
      if (length(sw) > 0) {
        ajouter_log(rv, paste0("Stopwords quanteda chargés (", cfg$libelle, ") : ", length(sw), " termes."))
      } else {
        ajouter_log(rv, paste0("Impossible de charger les stopwords quanteda pour ", cfg$libelle, "."))
      }
    }
    sw
  }
})

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
    fr = mean(all_tokens %in% obtenir_stopwords_quanteda("fr", rv = rv)),
    en = mean(all_tokens %in% obtenir_stopwords_quanteda("en", rv = rv)),
    es = mean(all_tokens %in% obtenir_stopwords_quanteda("es", rv = rv))
  )

  langue <- names(scores)[which.max(scores)]
  list(code = langue, scores = scores)
}

verifier_coherence_dictionnaire_langue <- function(textes, langue_selectionnee, rv = NULL) {
  est <- estimer_langue_corpus(textes, rv = rv)
  if (is.na(est$code)) return(invisible(est))

  sel <- configurer_langue_corpus(langue_selectionnee)$code
  sc_sel <- as.numeric(est$scores[[sel]])
  sc_best <- as.numeric(max(est$scores))
  marge <- sc_best - sc_sel

  if (!identical(sel, est$code) && sc_best >= 0.02 && marge >= 0.01) {
    cfg_sel <- configurer_langue_corpus(sel)
    cfg_best <- configurer_langue_corpus(est$code)
    stop(
      paste0(
        "Langue incohérente : le corpus ressemble à du ", cfg_best$libelle,
        " mais la langue sélectionnée est ", cfg_sel$libelle,
        ". Choisis la langue ", cfg_best$libelle, " avant de lancer l'analyse."
      )
    )
  }

  invisible(est)
}

# Compatibilité avec les anciens appels internes du projet.
configurer_langue_spacy <- function(langue) {
  configurer_langue_corpus(langue)
}

obtenir_stopwords_spacy <- function(langue_spacy = "fr", rv = NULL) {
  obtenir_stopwords_quanteda(langue = langue_spacy, rv = rv)
}
