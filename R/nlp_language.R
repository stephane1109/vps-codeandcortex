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

categories_morpho_iramuteq <- function() {
  c(
    "ADJ", "ADJ_DEM", "ADJ_IND", "ADJ_INT", "ADJ_NUM", "ADJ_POS", "ADJ_SUP",
    "ADV", "ADV_SUP", "ART_DEF", "ART_IND", "AUX", "CON", "NOM", "NOM_SUP",
    "ONO", "PRE", "PRO_DEM", "PRO_IND", "PRO_PER", "PRO_POS", "PRO_REL",
    "VER", "VER_SUP", "AUTRE_FORME"
  )
}

charger_lexique_fr_iramuteq <- local({
  cache <- NULL
  cache_path <- NULL

  function(path = file.path(getwd(), "dictionnaires", "lexique_fr.csv"), rv = NULL) {
    path <- normalizePath(path, winslash = "/", mustWork = FALSE)
    if (!file.exists(path)) {
      stop(paste0("Fichier lexique_fr.csv introuvable : ", path))
    }

    if (!is.null(cache) && identical(cache_path, path)) {
      return(cache)
    }

    lexique <- utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
    colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
    if (!all(colonnes_requises %in% names(lexique))) {
      stop("Le fichier lexique_fr.csv doit contenir les colonnes c_mot, c_lemme et c_morpho.")
    }

    lexique$c_mot <- tolower(trimws(as.character(lexique$c_mot)))
    lexique$c_lemme <- tolower(trimws(as.character(lexique$c_lemme)))
    lexique$c_morpho <- trimws(as.character(lexique$c_morpho))
    lexique <- lexique[
      nzchar(lexique$c_mot) & nzchar(lexique$c_lemme),
      c("c_mot", "c_lemme", "c_morpho"),
      drop = FALSE
    ]
    lexique <- lexique[!duplicated(lexique$c_mot), , drop = FALSE]
    attr(lexique, "source_file") <- path

    cache <<- lexique
    cache_path <<- path

    if (!is.null(rv)) {
      ajouter_log(rv, paste0("Lexique IRaMuTeQ-lite chargé : ", nrow(lexique), " entrées."))
    }

    lexique
  }
})

normaliser_selection_morpho_iramuteq <- function(selection, defaut = c("NOM", "VER", "ADJ")) {
  selection <- unique(toupper(trimws(as.character(unlist(selection, use.names = FALSE)))))
  selection <- selection[nzchar(selection)]
  if (!length(selection)) selection <- defaut
  unique(selection)
}

lemmatiser_tokens_lexique_iramuteq <- function(tok, lexique_fr_df, rv = NULL, libelle = "IRaMuTeQ-lite") {
  if (is.null(lexique_fr_df) || !is.data.frame(lexique_fr_df) || nrow(lexique_fr_df) == 0) {
    return(tok)
  }

  vocabulaire <- quanteda::featnames(quanteda::dfm(tok))
  idx <- match(vocabulaire, lexique_fr_df$c_mot)
  a_remplacer <- !is.na(idx)
  if (!any(a_remplacer)) {
    if (!is.null(rv)) ajouter_log(rv, paste0(libelle, " : lemmatisation lexique_fr active, mais aucune forme du vocabulaire n'a trouvé de lemme."))
    return(tok)
  }

  motifs <- vocabulaire[a_remplacer]
  remplacements <- lexique_fr_df$c_lemme[idx[a_remplacer]]
  tok <- quanteda::tokens_replace(
    tok,
    pattern = motifs,
    replacement = remplacements,
    valuetype = "fixed",
    case_insensitive = FALSE
  )

  if (!is.null(rv)) {
    ajouter_log(rv, paste0(libelle, " : lemmatisation lexique_fr appliquée sur ", length(motifs), " forme(s) du vocabulaire."))
  }

  tok
}

filtrer_dfm_lexique_iramuteq <- function(dfm_obj,
                                         lexique_fr_df,
                                         categories = c("NOM", "VER", "ADJ"),
                                         conserver_hors_lexique = TRUE,
                                         exclure_etre_verbe = FALSE,
                                         rv = NULL,
                                         libelle = "IRaMuTeQ-lite") {
  if (is.null(lexique_fr_df) || !is.data.frame(lexique_fr_df) || nrow(lexique_fr_df) == 0) {
    return(dfm_obj)
  }

  morpho_selection <- normaliser_selection_morpho_iramuteq(categories)
  inclure_autre_forme <- isTRUE(conserver_hors_lexique) || ("AUTRE_FORME" %in% morpho_selection)
  if (isTRUE(inclure_autre_forme) && !("AUTRE_FORME" %in% morpho_selection)) {
    morpho_selection <- c(morpho_selection, "AUTRE_FORME")
  }
  morpho_selection_lexique <- setdiff(morpho_selection, "AUTRE_FORME")

  if (!length(morpho_selection_lexique) && !isTRUE(inclure_autre_forme)) {
    if (!is.null(rv)) ajouter_log(rv, paste0(libelle, " : filtrage morphosyntaxique ignoré, aucune catégorie c_morpho sélectionnée."))
    return(dfm_obj)
  }

  lex <- lexique_fr_df
  lex_morpho <- toupper(trimws(as.character(lex$c_morpho)))
  categorie_verbe_selectionnee <- any(morpho_selection_lexique %in% c("VER", "VERB", "AUX", "VER_SUP"))

  idx <- nzchar(lex_morpho) & lex_morpho %in% morpho_selection_lexique
  termes_autorises <- unique(c(
    tolower(trimws(as.character(lex$c_mot[idx]))),
    tolower(trimws(as.character(lex$c_lemme[idx])))
  ))
  termes_autorises <- termes_autorises[nzchar(termes_autorises)]
  if (isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee)) {
    termes_autorises <- setdiff(termes_autorises, c("être", "etre"))
  }

  toutes_formes_lexique <- unique(c(
    tolower(trimws(as.character(lex$c_mot))),
    tolower(trimws(as.character(lex$c_lemme)))
  ))
  toutes_formes_lexique <- toutes_formes_lexique[nzchar(toutes_formes_lexique)]

  featnames_dfm <- quanteda::featnames(dfm_obj)
  featnames_norm <- tolower(trimws(as.character(featnames_dfm)))
  featnames_core <- gsub("^[[:punct:]]+|[[:punct:]]+$", "", featnames_norm, perl = TRUE)
  is_punct_feature <- !nzchar(featnames_core)

  in_selection <- (featnames_norm %in% termes_autorises) | (featnames_core %in% termes_autorises)
  in_lexique <- (featnames_norm %in% toutes_formes_lexique) | (featnames_core %in% toutes_formes_lexique)

  keep_mask <- in_selection
  if (isTRUE(inclure_autre_forme)) {
    keep_mask <- keep_mask | (!in_lexique & !is_punct_feature)
  }

  n_feat_avant <- quanteda::nfeat(dfm_obj)
  pattern_keep <- featnames_dfm[keep_mask]
  dfm_filtre <- quanteda::dfm_select(
    dfm_obj,
    pattern = pattern_keep,
    selection = "keep",
    valuetype = "fixed",
    case_insensitive = FALSE
  )
  n_feat_apres <- quanteda::nfeat(dfm_filtre)

  if (!is.null(rv)) {
    repartition_categories <- character(0)
    if (length(morpho_selection_lexique) > 0) {
      feat_ret_norm <- featnames_norm[keep_mask]
      feat_ret_core <- featnames_core[keep_mask]
      repartition_categories <- vapply(
        morpho_selection_lexique,
        function(cat) {
          idx_cat <- idx & lex_morpho == cat
          termes_cat <- unique(c(
            tolower(trimws(as.character(lex$c_mot[idx_cat]))),
            tolower(trimws(as.character(lex$c_lemme[idx_cat])))
          ))
          termes_cat <- termes_cat[nzchar(termes_cat)]
          if (!length(termes_cat)) return("0")
          as.character(sum((feat_ret_norm %in% termes_cat) | (feat_ret_core %in% termes_cat)))
        },
        character(1)
      )
    }
    if (length(repartition_categories) > 0) {
      ajouter_log(
        rv,
        paste0(
          libelle,
          " : répartition des termes conservés par c_morpho : ",
          paste0(names(repartition_categories), "=", repartition_categories, collapse = "; "),
          "."
        )
      )
    }
    ajouter_log(
      rv,
      paste0(
        libelle,
        " : filtrage morphosyntaxique lexique_fr appliqué (c_morpho=",
        paste(morpho_selection, collapse = ","),
        " | inclure_autre_forme=",
        ifelse(isTRUE(inclure_autre_forme), "1", "0"),
        " | exclure_etre_verbe=",
        ifelse(isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee), "1", "0"),
        ") : ",
        n_feat_avant,
        " -> ",
        n_feat_apres,
        " termes uniques."
      )
    )
  }

  dfm_filtre
}

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
