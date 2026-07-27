safe_write_csv_utf8 <- function(data, path, row.names = FALSE) {
  utils::write.csv(data, file = path, row.names = row.names, fileEncoding = "UTF-8", na = "")
}

safe_png_export <- function(path, expr, rv = NULL, label = NULL, width = 1800, height = 1400, res = 160) {
  error_message <- NULL
  grDevices::png(path, width = width, height = height, res = res)
  tryCatch(
    force(expr),
    error = function(e) {
      error_message <<- conditionMessage(e)
      try({
        plot.new()
        text(0.5, 0.5, paste0("Export indisponible", if (!is.null(label) && nzchar(label)) paste0(" : ", label) else ""), cex = 1.1)
      }, silent = TRUE)
    },
    finally = {
      try(grDevices::dev.off(), silent = TRUE)
    }
  )

  if (!is.null(error_message) && !is.null(rv)) {
    ajouter_log(rv, paste0("Export graphique ignoré", if (!is.null(label) && nzchar(label)) paste0(" (", label, ")") else "", " : ", error_message))
  }

  isTRUE(file.exists(path))
}

normaliser_parametres_chdrainette <- function(params) {
  params$mode_decoupage <- as.character(params$mode_decoupage %||% "segment_size")
  if (!params$mode_decoupage %in% c("segment_size", "ponctuation")) {
    params$mode_decoupage <- "segment_size"
  }

  params$segment_size <- max(5L, as.integer(params$segment_size %||% 40L))
  params$langue_corpus <- configurer_langue_corpus(params$langue_corpus %||% "fr")$code
  mode_nettoyage_lexical <- as.character(params$mode_nettoyage_lexical %||% "")
  if (!mode_nettoyage_lexical %in% c("stopwords_quanteda", "lexique_iramuteq", "aucun")) {
    mode_nettoyage_lexical <- if (isTRUE(params$retirer_stopwords)) "stopwords_quanteda" else "aucun"
  }
  params$mode_nettoyage_lexical <- mode_nettoyage_lexical
  params$retirer_stopwords <- identical(mode_nettoyage_lexical, "stopwords_quanteda")
  params$lexique_utiliser_lemmes <- isTRUE(params$lexique_utiliser_lemmes %||% TRUE)
  params$pos_lexique_a_conserver <- normaliser_selection_morpho_iramuteq(
    params$pos_lexique_a_conserver %||% c("NOM", "VER", "ADJ")
  )
  params$morpho_conserver_hors_lexique <- isTRUE(params$morpho_conserver_hors_lexique %||% TRUE)
  params$morpho_exclure_etre_verbe <- isTRUE(params$morpho_exclure_etre_verbe)
  params$nettoyage_caracteres <- isTRUE(params$nettoyage_caracteres)
  params$supprimer_ponctuation <- isTRUE(params$supprimer_ponctuation)
  params$supprimer_chiffres <- isTRUE(params$supprimer_chiffres)
  params$supprimer_apostrophes <- isTRUE(params$supprimer_apostrophes)
  params$forcer_minuscules_avant <- isTRUE(params$forcer_minuscules_avant)
  params$k <- max(2L, as.integer(params$k %||% 6L))
  params$min_segment_size <- max(0L, as.integer(params$min_segment_size %||% 0L))
  params$min_split_members <- max(3L, as.integer(params$min_split_members %||% 12L))
  params$min_docfreq <- max(1L, as.integer(params$min_docfreq %||% 1L))
  params$max_p <- as.numeric(params$max_p %||% 0.05)
  if (!is.finite(params$max_p) || is.na(params$max_p)) params$max_p <- 0.05
  params$max_p <- min(max(params$max_p, 0), 1)
  params$top_n <- max(5L, as.integer(params$top_n %||% 20L))
  params$debug_mode <- isTRUE(params$debug_mode)

  params
}

construire_corpus_segmente <- function(corpus_brut, params, rv = NULL) {
  if (identical(params$mode_decoupage, "ponctuation")) {
    if (!is.null(rv)) ajouter_etape(rv, "Découpage du corpus par ponctuation.")
    return(split_sentences_with_docvars(corpus_brut))
  }

  if (!is.null(rv)) ajouter_etape(rv, paste0("Découpage du corpus avec segment_size = ", params$segment_size, "."))
  rainette::split_segments(corpus_brut, segment_size = params$segment_size)
}

construire_dfm_rainette <- function(corpus_segmente, params, rv = NULL) {
  textes_orig <- as.character(corpus_segmente)
  doc_ids <- as.character(quanteda::docnames(corpus_segmente))
  names(textes_orig) <- doc_ids

  ajouter_log_debug(rv, paste0("Prétraitement brut : ", length(textes_orig), " segments reçus en entrée."))

  textes_prepares <- appliquer_nettoyage_et_minuscules(
    textes = textes_orig,
    activer_nettoyage = params$nettoyage_caracteres,
    forcer_minuscules = params$forcer_minuscules_avant,
    supprimer_chiffres = params$supprimer_chiffres,
    supprimer_apostrophes = params$supprimer_apostrophes
  )
  names(textes_prepares) <- doc_ids

  ajouter_log_debug(
    rv,
    paste0(
      "Nettoyage texte : regex=", as.integer(isTRUE(params$nettoyage_caracteres)),
      " | minuscules=", as.integer(isTRUE(params$forcer_minuscules_avant)),
      " | chiffres=", as.integer(isTRUE(params$supprimer_chiffres)),
      " | apostrophes=", as.integer(isTRUE(params$supprimer_apostrophes))
    )
  )

  verifier_coherence_dictionnaire_langue(textes_prepares, params$langue_corpus, rv = rv)

  tok <- quanteda::tokens(
    textes_prepares,
    remove_punct = params$supprimer_ponctuation,
    remove_numbers = params$supprimer_chiffres
  )
  ajouter_log_debug(rv, paste0("Tokenisation : ", length(tok), " documents tokenisés."))
  if (identical(params$mode_nettoyage_lexical, "stopwords_quanteda")) {
    sw <- obtenir_stopwords_quanteda(params$langue_corpus, rv = rv)
    ajouter_log_debug(rv, paste0("Stopwords quanteda activés : ", length(sw), " termes chargés pour la langue ", params$langue_corpus, "."))
    tok <- quanteda::tokens_remove(tok, sw)
  } else if (identical(params$mode_nettoyage_lexical, "lexique_iramuteq")) {
    if (!identical(params$langue_corpus, "fr")) {
      stop("Le dictionnaire IRaMuTeQ-lite intégré est lexique_fr : sélectionne la langue Français ou utilise les stopwords quanteda.")
    }
    ajouter_log_debug(rv, "Stopwords quanteda désactivés : nettoyage lexical par dictionnaire IRaMuTeQ-lite.")
  } else {
    ajouter_log_debug(rv, "Nettoyage lexical désactivé pour cette analyse.")
  }
  tok <- quanteda::tokens_split(tok, "'")
  tok <- quanteda::tokens_remove(tok, pattern = c("\\b[a-zA-Z]\\b", "^[^[:alpha:]]+$"), valuetype = "regex")
  tok <- quanteda::tokens_tolower(tok)

  dfm_obj <- quanteda::dfm(tok)
  ajouter_log_debug(rv, paste0("DFM brute : ", quanteda::ndoc(dfm_obj), " segments x ", quanteda::nfeat(dfm_obj), " termes."))
  if (identical(params$mode_nettoyage_lexical, "lexique_iramuteq")) {
    lexique_fr_df <- charger_lexique_fr_iramuteq(rv = rv)
    if (isTRUE(params$lexique_utiliser_lemmes)) {
      tok <- lemmatiser_tokens_lexique_iramuteq(tok, lexique_fr_df, rv = rv)
      dfm_obj <- quanteda::dfm(tok)
      ajouter_log_debug(rv, paste0("DFM après lemmatisation lexique_fr : ", quanteda::ndoc(dfm_obj), " segments x ", quanteda::nfeat(dfm_obj), " termes."))
    } else {
      ajouter_log_debug(rv, "Lemmatisation lexique_fr désactivée.")
    }
    dfm_obj <- filtrer_dfm_lexique_iramuteq(
      dfm_obj = dfm_obj,
      lexique_fr_df = lexique_fr_df,
      categories = params$pos_lexique_a_conserver,
      conserver_hors_lexique = params$morpho_conserver_hors_lexique,
      exclure_etre_verbe = params$morpho_exclure_etre_verbe,
      rv = rv
    )
  }
  if (ncol(quanteda::docvars(corpus_segmente)) > 0) {
    quanteda::docvars(dfm_obj) <- quanteda::docvars(corpus_segmente)
  }
  dfm_obj <- quanteda::dfm_trim(dfm_obj, min_docfreq = params$min_docfreq)
  ajouter_log_debug(rv, paste0("DFM après min_docfreq=", params$min_docfreq, " : ", quanteda::ndoc(dfm_obj), " segments x ", quanteda::nfeat(dfm_obj), " termes."))

  keep <- Matrix::rowSums(dfm_obj) > 0
  if (!any(keep)) {
    stop("Après nettoyage et filtrage, aucun segment exploitable ne reste dans la matrice.")
  }

  dfm_ok <- dfm_obj[keep, ]
  corpus_ok <- corpus_segmente[quanteda::docnames(dfm_ok)]
  ajouter_log_debug(rv, paste0("Segments conservés après filtrage final : ", quanteda::ndoc(dfm_ok), "."))
  list(dfm = dfm_ok, corpus = corpus_ok)
}

calculer_k_effectif_rainette <- function(dfm_obj, k_demande, min_split_members, rv = NULL) {
  n_docs <- quanteda::ndoc(dfm_obj)
  k_max_theorique <- floor(n_docs / max(1L, min_split_members))
  if (!is.finite(k_max_theorique) || is.na(k_max_theorique)) {
    k_max_theorique <- n_docs
  }
  k_max_theorique <- max(2L, min(k_max_theorique, max(2L, n_docs - 1L)))
  k_effectif <- min(k_demande, k_max_theorique)
  if (!is.null(rv) && k_effectif < k_demande) {
    ajouter_log(rv, paste0("k ajusté automatiquement de ", k_demande, " à ", k_effectif, " pour respecter min_split_members."))
  }
  ajouter_log_debug(rv, paste0("k effectif retenu : ", k_effectif, " | min_split_members=", min_split_members, " | segments=", n_docs, "."))
  k_effectif
}

calculer_stats_rainette <- function(dfm_obj, groupes, max_p, rv = NULL) {
  stats_list <- rainette::rainette_stats(
    dtm = dfm_obj,
    groups = groupes,
    measure = c("chi2", "lr", "frequency", "docprop"),
    n_terms = 9999,
    show_negative = TRUE,
    max_p = max_p
  )

  stats_df <- dplyr::bind_rows(stats_list, .id = "Classe")
  if (!nrow(stats_df)) {
    stop("Rainette n'a renvoyé aucune statistique exploitable.")
  }

  for (column_name in c("p", "chi2", "lr", "frequency", "docprop", "n_target", "n_reference")) {
    if (!column_name %in% names(stats_df)) {
      stats_df[[column_name]] <- NA_real_
    }
  }

  stats_df <- stats_df %>%
    dplyr::rename(Terme = feature) %>%
    dplyr::mutate(
      Classe = suppressWarnings(as.integer(Classe)),
      p = as.numeric(p),
      chi2 = as.numeric(chi2),
      lr = as.numeric(lr),
      frequency = as.numeric(frequency),
      docprop = as.numeric(docprop),
      n_target = as.numeric(n_target),
      n_reference = as.numeric(n_reference)
    ) %>%
    dplyr::arrange(Classe, dplyr::desc(chi2))

  if (!is.null(rv)) {
    ajouter_log(rv, paste0("Statistiques Rainette calculées pour ", length(unique(stats_df$Classe)), " classes."))
  }
  ajouter_log_debug(rv, paste0("Statistiques Rainette : ", nrow(stats_df), " lignes de termes discriminants générées."))
  stats_df
}

construire_termes_significatifs <- function(res_stats_df, max_p, top_n) {
  classes <- sort(unique(res_stats_df$Classe))
  out <- lapply(classes, function(cl) {
    res_stats_df %>%
      dplyr::filter(Classe == cl, is.finite(chi2), chi2 > 0, !is.na(p), p <= max_p, nchar(Terme) >= 3) %>%
      dplyr::arrange(dplyr::desc(chi2)) %>%
      dplyr::slice_head(n = top_n) %>%
      dplyr::pull(Terme) %>%
      unique()
  })
  names(out) <- as.character(classes)
  out
}

construire_resume_classes <- function(groupes, termes_significatifs) {
  df <- as.data.frame(table(Classe = groupes), stringsAsFactors = FALSE)
  df$Classe <- suppressWarnings(as.integer(as.character(df$Classe)))
  df$Segments <- as.integer(df$Freq)
  df$Pourcentage <- round(100 * df$Segments / sum(df$Segments), 2)
  df$Top_termes <- vapply(
    df$Classe,
    function(cl) {
      termes <- termes_significatifs[[as.character(cl)]] %||% character(0)
      if (!length(termes)) return("")
      paste(utils::head(termes, 8), collapse = ", ")
    },
    character(1)
  )
  df$Freq <- NULL
  df[order(df$Classe), , drop = FALSE]
}

construire_segments_exportables <- function(corpus_affichage, groupes, termes_significatifs) {
  segments_all <- as.character(corpus_affichage)
  names(segments_all) <- quanteda::docnames(corpus_affichage)
  classes_chr <- as.character(groupes)
  segments_split <- split(segments_all, classes_chr)

  segments_filtres <- lapply(names(segments_split), function(cl) {
    segs <- segments_split[[cl]]
    termes <- termes_significatifs[[cl]] %||% character(0)
    if (!length(termes)) {
      return(segs)
    }
    keep <- detecter_segments_contenant_termes_unicode(unname(segs), termes)
    segs_keep <- segs[keep]
    if (!length(segs_keep)) {
      segs
    } else {
      segs_keep
    }
  })
  names(segments_filtres) <- names(segments_split)

  list(all = segments_split, export = segments_filtres)
}

exporter_segments_par_classe <- function(segments_by_class, path) {
  lignes <- unlist(lapply(names(segments_by_class), function(cl) {
    c(paste0("Classe ", cl, " :"), unname(segments_by_class[[cl]]), "")
  }), use.names = FALSE)
  writeLines(lignes, con = path, useBytes = TRUE)
  path
}

extraire_frequences_dfm <- function(dfm_obj, rv = NULL, label = NULL) {
  empty <- data.frame(
    feature = character(0),
    frequency = numeric(0),
    rank = integer(0),
    docfreq = integer(0),
    group = character(0),
    stringsAsFactors = FALSE
  )

  if (is.null(dfm_obj) || quanteda::ndoc(dfm_obj) == 0 || quanteda::nfeat(dfm_obj) == 0) {
    return(empty)
  }

  total <- tryCatch(sum(dfm_obj), error = function(e) 0)
  if (!is.finite(total) || total <= 0) {
    return(empty)
  }

  tryCatch(
    as.data.frame(quanteda.textstats::textstat_frequency(dfm_obj), stringsAsFactors = FALSE),
    error = function(e) {
      if (!is.null(rv)) {
        ajouter_log(rv, paste0("Fréquences ignorées", if (!is.null(label) && nzchar(label)) paste0(" (", label, ")") else "", " : ", conditionMessage(e)))
      }
      empty
    }
  )
}

preparer_termes_wordcloud <- function(words, freq, top_n) {
  words <- trimws(as.character(words))
  freq <- suppressWarnings(as.numeric(freq))
  keep <- !is.na(words) & nzchar(words) & is.finite(freq) & !is.na(freq) & freq > 0
  words <- words[keep]
  freq <- freq[keep]

  if (!length(words)) {
    return(data.frame(words = character(0), freq = numeric(0), stringsAsFactors = FALSE))
  }

  ord <- order(freq, decreasing = TRUE)
  words <- words[ord]
  freq <- freq[ord]
  n <- min(as.integer(top_n), length(words))

  data.frame(
    words = words[seq_len(n)],
    freq = freq[seq_len(n)],
    stringsAsFactors = FALSE
  )
}

exporter_wordclouds <- function(res_stats_df, dfm_obj, groupes, clusters, top_n, output_dir, rv = NULL) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  out <- list()

  for (cl in clusters) {
    subset_stats <- res_stats_df %>%
      dplyr::filter(Classe == cl, !is.na(p), p <= 0.05, is.finite(chi2), chi2 > 0) %>%
      dplyr::arrange(dplyr::desc(chi2)) %>%
      dplyr::slice_head(n = top_n)

    termes_chi2 <- preparer_termes_wordcloud(subset_stats$Terme, subset_stats$chi2, top_n)
    if (nrow(termes_chi2) > 0) {
      file_chi2 <- file.path(output_dir, paste0("cluster_", cl, "_wordcloud_chi2.png"))
      safe_png_export(
        file_chi2,
        {
          suppressWarnings(wordcloud(
            words = termes_chi2$words,
            freq = termes_chi2$freq,
            scale = c(10, 0.5),
            max.words = top_n,
            colors = brewer.pal(8, "Dark2")
          ))
        },
        rv = rv,
        label = paste0("wordcloud chi2 classe ", cl)
      )
      out[[length(out) + 1L]] <- data.frame(
        classe = as.character(cl),
        type = "chi2",
        src = file.path("wordclouds", basename(file_chi2)),
        stringsAsFactors = FALSE
      )
    }

    segments_idx <- which(groupes == cl)
    if (length(segments_idx) > 0) {
      dfm_cl <- dfm_obj[segments_idx, ]
      freq_terms <- extraire_frequences_dfm(dfm_cl, rv = rv, label = paste0("wordcloud fréquence classe ", cl))
      freq_terms <- freq_terms[seq_len(min(top_n, nrow(freq_terms))), , drop = FALSE]
      termes_freq <- preparer_termes_wordcloud(freq_terms$feature, freq_terms$frequency, top_n)
      if (nrow(termes_freq) > 0) {
        file_freq <- file.path(output_dir, paste0("cluster_", cl, "_wordcloud_frequence.png"))
        safe_png_export(
          file_freq,
          {
            suppressWarnings(wordcloud(
              words = termes_freq$words,
              freq = termes_freq$freq,
              scale = c(10, 0.5),
              max.words = top_n,
              colors = brewer.pal(8, "Set2")
            ))
          },
          rv = rv,
          label = paste0("wordcloud fréquence classe ", cl)
        )
        out[[length(out) + 1L]] <- data.frame(
          classe = as.character(cl),
          type = "frequence",
          src = file.path("wordclouds", basename(file_freq)),
          stringsAsFactors = FALSE
        )
      }
    }
  }

  if (!length(out)) {
    return(data.frame(classe = character(0), type = character(0), src = character(0), stringsAsFactors = FALSE))
  }

  dplyr::bind_rows(out)
}

exporter_mots_et_segments <- function(segments_by_class_all, res_stats_df, dfm_obj, groupes, top_n, export_dir) {
  clusters <- sort(unique(groupes))
  termes_significatifs <- construire_termes_significatifs(res_stats_df, max_p = 0.05, top_n = top_n)
  mot_segment_liste <- list()

  for (cl in clusters) {
    segs <- segments_by_class_all[[as.character(cl)]] %||% character(0)
    if (!length(segs)) next

    mots_cl <- termes_significatifs[[as.character(cl)]] %||% character(0)
    if (!length(mots_cl)) next

    noms_segments <- names(segs)
    if (is.null(noms_segments) || length(noms_segments) != length(segs)) {
      noms_segments <- paste0("segment_", seq_along(segs))
    }

    for (mot in mots_cl) {
      motif <- paste0("\\b", echapper_regex(mot), "\\b")
      keep <- grepl(motif, segs, ignore.case = TRUE, perl = TRUE)
      if (!any(keep)) next

      mot_segment_liste[[length(mot_segment_liste) + 1L]] <- data.frame(
        Mot = mot,
        Classe = as.integer(cl),
        Segment = unname(segs[keep]),
        Nom_Segment = noms_segments[keep],
        stringsAsFactors = FALSE
      )
    }
  }

  if (length(mot_segment_liste)) {
    df_mot_segments <- dplyr::bind_rows(mot_segment_liste)
  } else {
    df_mot_segments <- data.frame(
      Mot = character(0),
      Classe = integer(0),
      Segment = character(0),
      Nom_Segment = character(0),
      stringsAsFactors = FALSE
    )
  }

  csv_mot_segments_path <- file.path(export_dir, "mots_chi2_segments.csv")
  safe_write_csv_utf8(df_mot_segments, csv_mot_segments_path, row.names = FALSE)

  stats_clean <- res_stats_df %>%
    dplyr::rename(Mot = Terme, Chi2 = chi2, p_value = p) %>%
    dplyr::select(dplyr::any_of(c("Mot", "Classe", "Chi2", "p_value", "lr", "frequency", "docprop", "n_target", "n_reference")))

  if (nrow(df_mot_segments)) {
    donnees_finales <- merge(df_mot_segments, stats_clean, by = c("Mot", "Classe"), all.x = TRUE)
  } else {
    donnees_finales <- df_mot_segments
  }

  frequences_par_classe <- lapply(clusters, function(cl) {
    dfm_cl <- dfm_obj[groupes == cl, ]
    freq <- extraire_frequences_dfm(dfm_cl, label = paste0("classe ", cl))
    if (nrow(freq)) {
      freq$Classe <- as.integer(cl)
    }
    freq
  })
  frequences_df <- dplyr::bind_rows(frequences_par_classe)
  if (nrow(frequences_df)) {
    frequences_df <- frequences_df %>%
      dplyr::rename(Mot = feature, Frequence = frequency) %>%
      dplyr::select(Mot, Classe, Frequence)
  } else {
    frequences_df <- data.frame(Mot = character(0), Classe = integer(0), Frequence = numeric(0), stringsAsFactors = FALSE)
  }

  if (nrow(donnees_finales)) {
    donnees_finales <- merge(donnees_finales, frequences_df, by = c("Mot", "Classe"), all.x = TRUE)
    donnees_finales <- donnees_finales %>%
      dplyr::arrange(Classe, dplyr::desc(Chi2), Mot)
  }

  csv_fusion_path <- file.path(export_dir, "mots_chi2_frequence_segments.csv")
  safe_write_csv_utf8(donnees_finales, csv_fusion_path, row.names = FALSE)

  classe_dir <- file.path(export_dir, "mots_par_classe_csv")
  dir.create(classe_dir, showWarnings = FALSE, recursive = TRUE)

  for (cl in clusters) {
    data_cl <- donnees_finales[donnees_finales$Classe == cl, , drop = FALSE]
    fichier_cl <- file.path(classe_dir, paste0("classe_", cl, "_mots_chi2_segments.csv"))
    safe_write_csv_utf8(data_cl, fichier_cl, row.names = FALSE)
  }

  list(
    mots_segments = csv_mot_segments_path,
    mots_segments_fusion = csv_fusion_path
  )
}

exporter_bundle_rainette <- function(res, dfm_obj, corpus_obj, classes_df, stats_df, params, export_dir) {
  bundle_file <- file.path(export_dir, "analysis_bundle.rds")
  script_file <- file.path(export_dir, "ouvrir_rainette_explor.R")

  saveRDS(
    list(
      res = res,
      dtm = dfm_obj,
      corpus = corpus_obj,
      classes = classes_df,
      stats = stats_df,
      params = params
    ),
    bundle_file
  )

  writeLines(
    c(
      "library(rainette)",
      "bundle <- readRDS('analysis_bundle.rds')",
      "rainette_explor(bundle$res, bundle$dtm, bundle$corpus)"
    ),
    con = script_file,
    useBytes = TRUE
  )

  list(bundle_file = bundle_file, script_file = script_file)
}

chdrainette_normaliser_appel_rainette <- function(res, min_segment_size = 0L) {
  if (is.null(res) || is.null(res$call)) {
    return(res)
  }

  valeur <- suppressWarnings(as.integer(min_segment_size[[1]]))
  if (!is.finite(valeur) || is.na(valeur) || valeur < 0L) {
    valeur <- 0L
  }

  # rainette_explor() et docs_sample_ui() attendent ici une valeur evaluee,
  # alors que match.call() peut avoir conserve un symbole ou un appel R.
  res$call$min_segment_size <- valeur
  res
}

creer_archive_exports <- function(base_dir, zip_name = "exports_rainette.zip") {
  zip_file <- file.path(base_dir, zip_name)
  if (file.exists(zip_file)) unlink(zip_file)
  old_wd <- getwd()
  on.exit(setwd(old_wd), add = TRUE)
  setwd(base_dir)
  utils::zip(zipfile = zip_file, files = "exports")
  zip_file
}

run_chdrainette_analysis <- function(input_path, original_name, params, rv = NULL, session_token = "session") {
  if (!file.exists(input_path)) {
    stop("Le fichier importé est introuvable côté serveur.")
  }

  params <- normaliser_parametres_chdrainette(params)
  file_stem <- tools::file_path_sans_ext(basename(original_name %||% basename(input_path)))
  if (!nzchar(file_stem)) file_stem <- "chdrainette"

  base_dir <- chdrainette_new_job_dir(session_token = session_token)
  export_dir <- file.path(base_dir, "exports")
  dir.create(export_dir, recursive = TRUE, showWarnings = FALSE)

  if (!is.null(rv)) {
    rv$progression <- 3
    rv$statut <- "Import du corpus."
    ajouter_etape(rv, "Initialisation du répertoire de travail.")
    ajouter_log(rv, paste0("Répertoire d'export : ", export_dir))
    ajouter_log_debug(
      rv,
      paste0(
        "Paramètres d'analyse : mode=", params$mode_decoupage,
        " | segment_size=", params$segment_size,
        " | k=", params$k,
        " | min_segment_size=", params$min_segment_size,
        " | min_split_members=", params$min_split_members,
        " | min_docfreq=", params$min_docfreq,
        " | max_p=", params$max_p,
        " | top_n=", params$top_n,
        " | nettoyage_lexical=", params$mode_nettoyage_lexical,
        " | stopwords_quanteda=", as.integer(isTRUE(params$retirer_stopwords)),
        " | lexique_lemmes=", as.integer(isTRUE(params$lexique_utiliser_lemmes)),
        " | lexique_categories=", paste(params$pos_lexique_a_conserver, collapse = ","),
        " | lexique_hors_lexique=", as.integer(isTRUE(params$morpho_conserver_hors_lexique)),
        " | debug=", as.integer(isTRUE(params$debug_mode))
      )
    )
  }

  corpus_brut <- rainette::import_corpus_iramuteq(input_path)
  if (!is.null(rv)) {
    rv$progression <- 10
    rv$statut <- "Segmentation du corpus."
    ajouter_etape(rv, "Import du corpus IRaMuTeQ terminé.")
    ajouter_log(rv, paste0("Documents importés : ", quanteda::ndoc(corpus_brut)))
  }

  corpus_segmente <- construire_corpus_segmente(corpus_brut, params, rv = rv)
  if (!is.null(rv)) {
    rv$progression <- 20
    rv$statut <- "Prétraitement et DFM."
    ajouter_etape(rv, "Segmentation du corpus terminée.")
    ajouter_log(rv, paste0("Segments créés : ", quanteda::ndoc(corpus_segmente)))
  }

  prepared <- construire_dfm_rainette(corpus_segmente, params, rv = rv)
  dfm_ok <- prepared$dfm
  corpus_ok <- prepared$corpus
  if (!is.null(rv)) {
    rv$progression <- 35
    rv$statut <- "Classification Rainette."
    ajouter_etape(rv, "Prétraitement et DFM terminés.")
    ajouter_log(rv, paste0("DFM prête : ", quanteda::ndoc(dfm_ok), " segments x ", quanteda::nfeat(dfm_ok), " termes."))
  }

  k_effectif <- calculer_k_effectif_rainette(dfm_ok, params$k, params$min_split_members, rv = rv)
  res <- rainette::rainette(
    dtm = dfm_ok,
    k = k_effectif,
    min_segment_size = params$min_segment_size,
    min_split_members = max(3L, params$min_split_members),
    doc_id = "segment_source"
  )
  res <- chdrainette_normaliser_appel_rainette(
    res,
    min_segment_size = params$min_segment_size
  )

  groupes <- as.integer(res$group)
  quanteda::docvars(corpus_ok)$Classes <- groupes
  clusters <- sort(unique(groupes))

  if (!is.null(rv)) {
    rv$progression <- 50
    rv$statut <- "Calcul des statistiques."
    ajouter_etape(rv, "Classification Rainette terminée.")
    ajouter_log(rv, paste0("Classes obtenues : ", paste(clusters, collapse = ", ")))
    ajouter_log_debug(rv, paste0("Taille des classes : ", paste(as.integer(table(groupes)), collapse = ", "), "."))
  }

  res_stats_df <- calculer_stats_rainette(dfm_ok, groupes, params$max_p, rv = rv)
  termes_significatifs <- construire_termes_significatifs(res_stats_df, params$max_p, params$top_n)
  classes_df <- construire_resume_classes(groupes, termes_significatifs)

  afc_obj <- NULL
  afc_error <- NULL
  afc_files <- NULL
  if (!is.null(rv)) {
    rv$progression <- 60
    rv$statut <- "Calcul de l'AFC classes-termes."
    ajouter_etape(rv, "Construction de l'AFC à partir des classes de la CHD.")
  }
  tryCatch({
    afc_obj <- chdrainette_compute_afc(
      dfm_obj = dfm_ok,
      groups = groupes,
      max_terms = 400L
    )
    afc_files <- chdrainette_export_afc(afc_obj, export_dir = export_dir)
    if (!is.null(rv)) {
      ajouter_log(rv, "AFC classes-termes calculée et exportée.")
    }
  }, error = function(error) {
    afc_error <<- paste0("AFC indisponible : ", conditionMessage(error))
    if (!is.null(rv)) {
      ajouter_log(rv, afc_error)
    }
  })

  if (!is.null(rv)) {
    rv$progression <- 65
    rv$statut <- "Exports texte et concordancier."
    ajouter_etape(rv, "Calcul des statistiques discriminantes terminé.")
  }

  segments_info <- construire_segments_exportables(corpus_ok, groupes, termes_significatifs)
  segments_file <- file.path(export_dir, paste0(file_stem, "_segments_par_classe.txt"))
  exporter_segments_par_classe(segments_info$export, segments_file)

  stats_file <- file.path(export_dir, paste0(file_stem, "_stats_par_classe.csv"))
  safe_write_csv_utf8(res_stats_df, stats_file, row.names = FALSE)
  safe_write_csv_utf8(classes_df, file.path(export_dir, paste0(file_stem, "_resume_classes.csv")), row.names = FALSE)

  html_file <- file.path(export_dir, paste0(file_stem, "_segments_par_classe.html"))
  generer_concordancier_html(
    chemin_sortie = html_file,
    segments_by_class = segments_info$export,
    res_stats_df = res_stats_df,
    max_p = params$max_p,
    textes_indexation = setNames(as.character(corpus_ok), quanteda::docnames(corpus_ok)),
    dfm_obj = dfm_ok,
    classes_docs = groupes,
    top_termes_keyness = max(100L, params$top_n * 10L),
    mode_nettoyage_lexical = params$mode_nettoyage_lexical,
    rv = rv
  )

  if (!is.null(rv)) {
    rv$progression <- 80
    rv$statut <- "Nuages de mots et exports détaillés."
    ajouter_etape(rv, "Exports texte et concordancier générés.")
  }

  wordclouds <- tryCatch(
    exporter_wordclouds(
      res_stats_df = res_stats_df,
      dfm_obj = dfm_ok,
      groupes = groupes,
      clusters = clusters,
      top_n = params$top_n,
      output_dir = file.path(export_dir, "wordclouds"),
      rv = rv
    ),
    error = function(e) {
      if (!is.null(rv)) {
        ajouter_log(rv, paste0("Exports nuages de mots ignorés : ", conditionMessage(e)))
      }
      data.frame(classe = character(0), type = character(0), src = character(0), stringsAsFactors = FALSE)
    }
  )

  tryCatch(
    exporter_mots_et_segments(
      segments_by_class_all = segments_info$all,
      res_stats_df = res_stats_df,
      dfm_obj = dfm_ok,
      groupes = groupes,
      top_n = params$top_n,
      export_dir = export_dir
    ),
    error = function(e) {
      if (!is.null(rv)) {
        ajouter_log(rv, paste0("Exports mots/segments ignorés : ", conditionMessage(e)))
      }
      NULL
    }
  )

  bundle_info <- exporter_bundle_rainette(
    res = res,
    dfm_obj = dfm_ok,
    corpus_obj = corpus_ok,
    classes_df = classes_df,
    stats_df = res_stats_df,
    params = params,
    export_dir = export_dir
  )

  if (!is.null(rv)) {
    rv$progression <- 92
    rv$statut <- "Création de l'archive ZIP."
    ajouter_etape(rv, "Nuages de mots et exports détaillés terminés.")
  }

  zip_file <- creer_archive_exports(base_dir = base_dir)
  ajouter_log_debug(rv, paste0("Archive ZIP finale : ", zip_file))

  if (!is.null(rv)) {
    rv$progression <- 100
    rv$statut <- "Analyse terminée."
    ajouter_etape(rv, "Archive ZIP générée, analyse finalisée.")
  }

  list(
    corpus_importe = corpus_brut,
    corpus_segmente = corpus_segmente,
    filtered_corpus = corpus_ok,
    dfm = dfm_ok,
    res = res,
    res_stats_df = res_stats_df,
    classes_df = classes_df,
    clusters = clusters,
    base_dir = base_dir,
    export_dir = export_dir,
    file_stem = file_stem,
    segments_file = segments_file,
    stats_file = stats_file,
    html_file = html_file,
    zip_file = zip_file,
    bundle_file = bundle_info$bundle_file,
    bundle_script_file = bundle_info$script_file,
    wordclouds = wordclouds,
    afc_obj = afc_obj,
    afc_error = afc_error,
    afc_files = afc_files,
    params_used = params
  )
}
