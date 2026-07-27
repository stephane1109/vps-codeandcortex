# concordancier.R

horodater <- function() format(Sys.time(), "%Y-%m-%d %H:%M:%S")

ajouter_log <- function(rv, texte) {
  rv$logs <- paste(rv$logs, paste0("[", horodater(), "] ", texte), sep = "\n")
}

trans_nfd <- function(x) {
  if (requireNamespace("stringi", quietly = TRUE)) return(stringi::stri_trans_nfd(x))
  x
}

trans_nfc <- function(x) {
  if (requireNamespace("stringi", quietly = TRUE)) return(stringi::stri_trans_nfc(x))
  x
}

echapper_regex <- function(x) {
  gsub("([\\^\\$\\*\\+\\?\\(\\)\\[\\]\\{\\}\\.\\|\\\\\\-])", "\\\\\\1", x)
}

construire_regex_terme_nfd <- function(terme) {
  if (is.na(terme) || !nzchar(terme)) return("")

  t <- tolower(trans_nfd(terme))
  chars <- strsplit(t, "", fixed = TRUE)[[1]]
  if (length(chars) == 0) return("")

  pieces <- vapply(chars, function(ch) {
    if (grepl("\\p{M}", ch, perl = TRUE)) return("")
    if (ch %in% c(" ", "\t", "\n", "\r")) return("\\s+")
    if (ch %in% c("'", "’")) return("['’]")

    if (grepl("\\p{L}", ch, perl = TRUE)) {
      return(paste0(echapper_regex(ch), "\\p{M}*"))
    }

    echapper_regex(ch)
  }, FUN.VALUE = character(1))

  paste0(pieces, collapse = "")
}

preparer_motifs_surlignage_nfd <- function(terms, taille_lot = 200) {
  terms <- unique(terms)
  terms <- terms[!is.na(terms) & nzchar(terms)]
  if (length(terms) == 0) return(list())

  terms <- terms[order(nchar(terms), decreasing = TRUE)]
  patterns <- vapply(terms, construire_regex_terme_nfd, FUN.VALUE = character(1))
  patterns <- patterns[nzchar(patterns)]
  if (length(patterns) == 0) return(list())

  lots <- split(patterns, ceiling(seq_along(patterns) / taille_lot))

  lapply(lots, function(lot) {
    paste0(
      "(*UCP)(?i)(?<![\\p{L}\\p{M}])(",
      paste0(lot, collapse = "|"),
      ")(?![\\p{L}\\p{M}])"
    )
  })
}

surligner_vecteur_html_unicode <- function(segments, motifs, start_tag, end_tag) {
  if (length(segments) == 0 || length(motifs) == 0) return(segments)

  out <- segments
  for (i in seq_along(out)) {
    s <- out[i]
    if (is.na(s) || !nzchar(s)) next

    s_nfd <- trans_nfd(s)

    for (pat in motifs) {
      s_nfd <- tryCatch(
        gsub(pat, paste0(start_tag, "\\1", end_tag), s_nfd, perl = TRUE),
        error = function(e) s_nfd
      )
    }

    out[i] <- trans_nfc(s_nfd)
  }
  out
}

detecter_segments_contenant_termes_unicode <- function(textes_index, termes) {
  if (length(textes_index) == 0) return(logical(0))

  termes <- unique(termes)
  termes <- termes[!is.na(termes) & nzchar(termes)]
  if (length(termes) == 0) return(rep(TRUE, length(textes_index)))

  motifs <- preparer_motifs_surlignage_nfd(termes, taille_lot = 200)
  if (length(motifs) == 0) return(rep(TRUE, length(textes_index)))

  present <- rep(FALSE, length(textes_index))
  textes_nfd <- trans_nfd(textes_index)

  for (pat in motifs) {
    ok <- tryCatch(grepl(pat, textes_nfd, perl = TRUE), error = function(e) rep(FALSE, length(textes_nfd)))
    present <- present | ok
  }

  present
}

decrire_nettoyage_concordancier <- function(mode_nettoyage_lexical = NULL) {
  mode <- as.character(mode_nettoyage_lexical)
  if (!length(mode) || !nzchar(mode[[1]])) {
    return("sur la matrice lexicale analysée")
  }
  mode <- mode[[1]]

  if (identical(mode, "stopwords_quanteda")) {
    return("après nettoyage par stopwords quanteda")
  }
  if (identical(mode, "lexique_iramuteq")) {
    return("après nettoyage par dictionnaire IRaMuTeQ-lite (lexique_fr)")
  }
  if (identical(mode, "aucun")) {
    return("sans nettoyage lexical supplémentaire")
  }

  "avec le nettoyage lexical sélectionné"
}

extraire_termes_significatifs_quanteda <- function(dfm_obj,
                                                   classes_docs,
                                                   classe_cible,
                                                   max_p = 0.05,
                                                   top_n = 200,
                                                   rv = NULL,
                                                   contexte_nettoyage = NULL) {
  if (is.null(dfm_obj) || ndoc(dfm_obj) == 0) return(character(0))
  if (is.null(classes_docs) || !length(classes_docs)) return(character(0))

  classes_docs <- as.character(classes_docs)
  if (length(classes_docs) != ndoc(dfm_obj)) return(character(0))

  cible <- classes_docs == as.character(classe_cible)
  cible[is.na(cible)] <- FALSE

  if (sum(cible) == 0 || sum(!cible) == 0) return(character(0))

  stats_keyness <- tryCatch(
    as.data.frame(quanteda.textstats::textstat_keyness(dfm_obj, target = cible, measure = "chi2")),
    error = function(e) {
      if (!is.null(rv)) {
        ajouter_log(rv, paste0("Concordancier : échec du calcul des termes significatifs pour la classe ", classe_cible, " : ", conditionMessage(e)))
      }
      NULL
    }
  )

  if (is.null(stats_keyness) || nrow(stats_keyness) == 0) return(character(0))

  if ("chi2" %in% names(stats_keyness)) {
    stats_keyness <- stats_keyness[is.finite(stats_keyness$chi2) & stats_keyness$chi2 > 0, , drop = FALSE]
    stats_keyness <- stats_keyness[order(stats_keyness$chi2, decreasing = TRUE), , drop = FALSE]
  }

  if ("p" %in% names(stats_keyness)) {
    stats_keyness <- stats_keyness[is.finite(stats_keyness$p) & stats_keyness$p <= max_p, , drop = FALSE]
  }

  if ("n_target" %in% names(stats_keyness)) {
    stats_keyness <- stats_keyness[is.finite(stats_keyness$n_target) & stats_keyness$n_target > 0, , drop = FALSE]
  }

  if (!nrow(stats_keyness) || !"feature" %in% names(stats_keyness)) return(character(0))

  if (is.finite(top_n) && !is.na(top_n) && top_n > 0) {
    stats_keyness <- head(stats_keyness, as.integer(top_n))
  }

  termes <- unique(as.character(stats_keyness$feature))
  termes <- termes[!is.na(termes) & nzchar(trimws(termes))]

  if (!is.null(rv)) {
    if (is.null(contexte_nettoyage) || !nzchar(as.character(contexte_nettoyage))) {
      contexte_nettoyage <- "sur la matrice lexicale analysée"
    }
    ajouter_log(rv, paste0("Concordancier : ", length(termes), " termes significatifs extraits ", contexte_nettoyage, " pour la classe ", classe_cible, "."))
  }

  termes
}

generer_concordancier_html <- function(
  chemin_sortie,
  segments_by_class,
  res_stats_df,
  max_p,
  textes_indexation,
  dfm_obj = NULL,
  classes_docs = NULL,
  top_termes_keyness = 200,
  explor_assets = NULL,
  mode_nettoyage_lexical = NULL,
  avancer = NULL,
  rv = NULL,
  ...
) {
  contexte_nettoyage <- decrire_nettoyage_concordancier(mode_nettoyage_lexical)
  if (!is.null(rv)) {
    ajouter_log(rv, paste0("Concordancier : génération HTML (segments filtrés et surlignés ; ", contexte_nettoyage, ")."))
  }

  con <- file(chemin_sortie, open = "wt", encoding = "UTF-8")
  on.exit(try(close(con), silent = TRUE), add = TRUE)

  writeLines("<html><head><meta charset='utf-8'/>", con)
  writeLines("<style>body{font-family:Arial,sans-serif;} span.highlight{background-color:yellow;}</style>", con)
  writeLines("</head><body>", con)

  writeLines("<h1>Concordancier Rainette</h1>", con)

  writeLines("<h2>Segments par classe</h2>", con)
  writeLines(paste0("<h3>Segments par classe (filtrés et surlignés à partir des termes significatifs ; ", htmltools::htmlEscape(contexte_nettoyage), ")</h3>"), con)

  noms_classes <- names(segments_by_class)
  n_classes <- length(noms_classes)
  if (n_classes == 0) n_classes <- 1

  for (i in seq_along(noms_classes)) {
    cl <- noms_classes[i]

    if (!is.null(avancer)) avancer(0.75 + (i / n_classes) * 0.08, paste0("HTML : classe ", cl))
    writeLines(paste0("<h2>Classe ", cl, "</h2>"), con)

    termes_cl <- extraire_termes_significatifs_quanteda(
      dfm_obj = dfm_obj,
      classes_docs = classes_docs,
      classe_cible = cl,
      max_p = max_p,
      top_n = top_termes_keyness,
      rv = rv,
      contexte_nettoyage = contexte_nettoyage
    )

    if (!length(termes_cl)) {
      termes_cl <- subset(res_stats_df, Classe == as.numeric(cl) & p <= max_p)$Terme
      termes_cl <- unique(termes_cl)
      termes_cl <- termes_cl[!is.na(termes_cl) & nzchar(termes_cl)]
      if (!is.null(rv)) {
        ajouter_log(rv, paste0("Concordancier : repli sur rainette_stats pour la classe ", cl, "."))
      }
    }

    segments <- segments_by_class[[cl]]
    ids_cl <- names(segments)

    if (length(ids_cl) == 0) {
      writeLines("<p><em>Aucun segment.</em></p>", con)
      next
    }

    termes_a_surligner <- unique(termes_cl)
    termes_a_surligner <- termes_a_surligner[!is.na(termes_a_surligner) & nzchar(termes_a_surligner)]

    keep <- detecter_segments_contenant_termes_unicode(unname(segments), termes_a_surligner)
    segments_keep <- segments[keep]

    writeLines(paste0("<p><em>Segments conservés : ", length(segments_keep), " / ", length(segments), "</em></p>"), con)

    if (length(segments_keep) == 0 || length(termes_a_surligner) == 0) {
      writeLines("<p><em>Aucun segment ne contient de terme significatif pour cette classe avec les paramètres courants.</em></p>", con)
      next
    }

    motifs <- preparer_motifs_surlignage_nfd(termes_a_surligner, taille_lot = 160)

    segments_hl <- surligner_vecteur_html_unicode(
      unname(segments_keep),
      motifs,
      "<span class='highlight'>",
      "</span>"
    )

    for (seg in segments_hl) writeLines(paste0("<p>", seg, "</p>"), con)
  }

  writeLines("</body></html>", con)
  close(con)

  if (!is.null(rv)) ajouter_log(rv, paste0("Concordancier : HTML écrit dans : ", chemin_sortie))
  chemin_sortie
}
