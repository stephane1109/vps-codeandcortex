# Module CHD/AFC - préparation des données et génération des artefacts CHD
# Ce fichier centralise les fonctions de préparation DFM/docvars, l'ajustement de `k`,
# les utilitaires de graphes d'adjacence/cooccurrence, et la génération des exports
# CHD (PNG + HTML) afin d'alléger `app.R` sans modifier le comportement existant.

extraire_classes_alignees <- function(corpus_obj, doc_ids, nom_colonne = "Classes") {
  dv <- docvars(corpus_obj)
  if (!(nom_colonne %in% names(dv))) return(rep(NA_character_, length(doc_ids)))

  doc_ids <- as.character(doc_ids)
  dn_corpus <- as.character(docnames(corpus_obj))
  idx <- match(doc_ids, dn_corpus)

  out <- rep(NA_character_, length(doc_ids))
  ok <- !is.na(idx)
  if (any(ok)) {
    out[ok] <- as.character(dv[[nom_colonne]][idx[ok]])
  }

  normaliser_classes(out)
}

construire_segment_source <- function(corpus_segmente) {
  dv <- docvars(corpus_segmente)

  if ("segment_source" %in% names(dv)) {
    v <- as.character(dv$segment_source)
    if (length(v) == ndoc(corpus_segmente)) return(v)
  }

  dn <- docnames(corpus_segmente)

  if (any(grepl("_seg[0-9]+$", dn))) return(gsub("_seg[0-9]+$", "", dn))
  if (any(grepl("_[0-9]+$", dn))) return(gsub("_[0-9]+$", "", dn))
  if (any(grepl("-[0-9]+$", dn))) return(gsub("-[0-9]+$", "", dn))

  dn
}

assurer_docvars_dfm_minimal <- function(dfm_obj, corpus_aligne) {
  seg_source <- construire_segment_source(corpus_aligne)
  dv <- data.frame(segment_source = seg_source, stringsAsFactors = FALSE)
  rownames(dv) <- docnames(corpus_aligne)
  docvars(dfm_obj) <- dv
  dfm_obj
}

construire_dfm_avec_fallback_stopwords <- function(tok_base, min_docfreq, retirer_stopwords, langue_spacy, rv, libelle) {
  n_base <- compter_tokens(tok_base)
  ajouter_log(rv, paste0(libelle, " : tokens (avant stopwords) = ", n_base))

  if (isTRUE(retirer_stopwords)) {
    tok_sw <- tokens_remove(tok_base, obtenir_stopwords_spacy(langue_spacy = langue_spacy, rv = rv))
    tok_sw <- tokens_tolower(tok_sw)
    n_sw <- compter_tokens(tok_sw)
    ajouter_log(rv, paste0(libelle, " : tokens (après stopwords) = ", n_sw))
    tok_final <- tok_sw
  } else {
    ajouter_log(rv, paste0(libelle, " : suppression des stopwords désactivée."))
    tok_final <- tokens_tolower(tok_base)
  }

  dfm_obj <- dfm(tok_final)
  dfm_obj <- dfm_trim(dfm_obj, min_docfreq = min_docfreq)
  ajouter_log(
    rv,
    paste0(
      libelle,
      " : DFM après trim = ", ndoc(dfm_obj), " docs ; ", nfeat(dfm_obj),
      ifelse(isTRUE(retirer_stopwords), " termes (avec stopwords retirés)", " termes (sans suppression des stopwords)")
    )
  )

  if (isTRUE(retirer_stopwords) && nfeat(dfm_obj) < 2) {
    ajouter_log(rv, paste0(libelle, " : DFM trop pauvre avec stopwords retirés. Relance automatique sans suppression des stopwords."))
    tok_final <- tokens_tolower(tok_base)
    dfm_obj <- dfm(tok_final)
    dfm_obj <- dfm_trim(dfm_obj, min_docfreq = min_docfreq)
    ajouter_log(rv, paste0(libelle, " : DFM après trim = ", ndoc(dfm_obj), " docs ; ", nfeat(dfm_obj), " termes (sans stopwords)"))
  }

  list(tok = tok_final, dfm = dfm_obj)
}

supprimer_docs_vides_dfm <- function(dfm_obj, corpus_aligne, tok_aligne, rv) {
  rs <- tryCatch(Matrix::rowSums(dfm_obj), error = function(e) NULL)

  if (is.null(rs)) {
    ajouter_log(rv, "Impossible de calculer rowSums(dfm). Aucune suppression de segments vides.")
    return(list(dfm = dfm_obj, corpus = corpus_aligne, tok = tok_aligne))
  }

  n_vides <- sum(rs == 0)
  if (n_vides > 0) {
    ajouter_log(rv, paste0("Segments vides (aucun terme) détectés : ", n_vides, ". Suppression avant CHD."))
    garder <- rs > 0
    dfm_obj <- dfm_obj[garder, ]
    noms <- docnames(dfm_obj)
    corpus_aligne <- corpus_aligne[noms]
    tok_aligne <- tok_aligne[noms]
  }

  list(dfm = dfm_obj, corpus = corpus_aligne, tok = tok_aligne)
}

calculer_k_effectif <- function(dfm_obj, k_demande, min_split_members, rv = NULL) {
  n_docs <- ndoc(dfm_obj)
  if (!is.finite(min_split_members) || is.na(min_split_members) || min_split_members < 1) {
    min_split_members <- 1
  }

  k_max_theorique <- floor(n_docs / min_split_members)
  if (!is.finite(k_max_theorique) || is.na(k_max_theorique)) k_max_theorique <- n_docs
  k_max_theorique <- max(1, min(k_max_theorique, n_docs - 1))

  k_effectif <- min(k_demande, k_max_theorique)

  if (k_effectif < 2) {
    stop(
      "Paramètres incompatibles : min_split_members=", min_split_members,
      " est trop élevé pour ", n_docs,
      " segments. Réduis min_split_members ou augmente la taille du corpus segmenté."
    )
  }

  if (!is.null(rv) && k_effectif < k_demande) {
    ajouter_log(
      rv,
      paste0(
        "k ajusté automatiquement de ", k_demande, " à ", k_effectif,
        " pour respecter min_split_members=", min_split_members,
        " (", n_docs, " segments disponibles)."
      )
    )
  }

  k_effectif
}

verifier_dfm_avant_rainette <- function(dfm_obj, input) {
  if (ndoc(dfm_obj) < 2) {
    stop("Après filtrages, il reste moins de 2 segments utilisables. Réduis les filtrages ou augmente segment_size.")
  }
  if (nfeat(dfm_obj) < 2) {
    stop(
      "Après filtrages, il reste moins de 2 termes dans le DFM. ",
      "Même avec min_docfreq=1, cela arrive si le filtrage morphosyntaxique est trop strict et/ou si les stopwords retirent la majorité des formes. ",
      "Élargis les catégories morphosyntaxiques ou augmente segment_size."
    )
  }
}

obtenir_objet_dendrogramme <- function(res) {
  if (is.null(res)) return(NULL)

  if (inherits(res, "hclust") || inherits(res, "dendrogram")) return(res)

  if (is.list(res)) {
    candidats <- c("tree", "hc", "hclust", "dendro", "dendrogram")
    for (nm in candidats) {
      if (!is.null(res[[nm]]) && (inherits(res[[nm]], "hclust") || inherits(res[[nm]], "dendrogram"))) {
        return(res[[nm]])
      }
    }
  }

  NULL
}

construire_graphe_adjacence <- function(mat) {
  if ("graph_from_adjacency_matrix" %in% getNamespaceExports("igraph")) {
    igraph::graph_from_adjacency_matrix(mat, mode = "undirected", weighted = TRUE, diag = FALSE)
  } else {
    igraph::graph.adjacency(mat, mode = "undirected", weighted = TRUE, diag = FALSE)
  }
}

generer_chd_explor_si_absente <- function(rv) {
  if (is.null(rv$export_dir) || !nzchar(rv$export_dir)) return(FALSE)

  explor_dir <- file.path(rv$export_dir, "explor")
  dir.create(explor_dir, showWarnings = FALSE, recursive = TRUE)

  chd_png <- file.path(explor_dir, "chd.png")
  if (file.exists(chd_png)) return(TRUE)

  chd_obj <- rv$res_chd
  if (is.null(chd_obj)) chd_obj <- rv$res
  if (is.null(chd_obj)) return(FALSE)

  dfm_obj <- rv$dfm_chd
  err_msg <- NULL

  ecrire_png_secours <- function(message = NULL) {
    grDevices::png(chd_png, width = 2000, height = 1500, res = 180)
    tryCatch({
      plot.new()
      title("CHD (export)")
      txt <- "CHD indisponible pour cet export."
      if (!is.null(message) && nzchar(message)) {
        txt <- paste0(txt, "\n", message)
      }
      text(0.5, 0.5, txt, cex = 1.1)
    }, finally = {
      try(grDevices::dev.off(), silent = TRUE)
    })
    file.exists(chd_png) && is.finite(file.info(chd_png)$size) && file.info(chd_png)$size > 0
  }

  dessiner_chd <- function(avec_dfm = FALSE) {
    grDevices::png(chd_png, width = 2000, height = 1500, res = 180)
    ok_plot <- FALSE

    tryCatch({
      if (isTRUE(avec_dfm) && !is.null(dfm_obj)) {
        k_plot <- suppressWarnings(as.integer(rv$max_n_groups_chd))
        if (!is.finite(k_plot) || is.na(k_plot) || k_plot < 2) {
          if (!is.null(chd_obj$group)) {
            k_plot <- suppressWarnings(max(as.integer(chd_obj$group), na.rm = TRUE))
          }
        }
        if (!is.finite(k_plot) || is.na(k_plot) || k_plot < 2) k_plot <- 2L

        args_plot <- list(
          chd_obj,
          dfm_obj,
          k = k_plot,
          measure = "chi2",
          type = "bar",
          n_terms = 20,
          show_negative = FALSE,
          text_size = 12
        )

        params_plot <- tryCatch(names(formals(rainette_plot)), error = function(e) character(0))
        if ("same_scales" %in% params_plot) args_plot$same_scales <- TRUE
        if ("free_scales" %in% params_plot) args_plot$free_scales <- FALSE

        do.call(rainette_plot, args_plot)
      } else {
        rainette_plot(chd_obj)
      }
      ok_plot <- TRUE
    }, error = function(e) {
      err_msg <<- conditionMessage(e)
    }, finally = {
      try(grDevices::dev.off(), silent = TRUE)
    })

    isTRUE(ok_plot) && file.exists(chd_png) && is.finite(file.info(chd_png)$size) && file.info(chd_png)$size > 0
  }

  ok <- dessiner_chd(avec_dfm = FALSE)
  if (!ok && !is.null(dfm_obj)) {
    ok <- dessiner_chd(avec_dfm = TRUE)
  }

  if (!ok) {
    if (!is.null(rv)) {
      msg <- if (!is.null(err_msg) && nzchar(err_msg)) err_msg else "raison inconnue"
      ajouter_log(rv, paste0("CHD PNG non généré (", msg, ")."))
    }
    if (file.exists(chd_png)) unlink(chd_png)

    ok_fallback <- ecrire_png_secours(err_msg)
    if (ok_fallback) {
      if (!is.null(rv)) ajouter_log(rv, paste0("CHD PNG de secours généré : ", chd_png))
      ok <- TRUE
    }
  } else if (!is.null(rv)) {
    ajouter_log(rv, paste0("CHD PNG généré : ", chd_png))
  }

  ok
}

generer_chd_html_explor <- function(rv, chd_png_rel = NULL) {
  if (is.null(rv$export_dir) || !nzchar(rv$export_dir)) return(NULL)

  explor_dir <- file.path(rv$export_dir, "explor")
  dir.create(explor_dir, showWarnings = FALSE, recursive = TRUE)

  chd_html <- file.path(explor_dir, "chd.html")
  img_part <- "<p><em>CHD non disponible dans l'export.</em></p>"
  if (!is.null(chd_png_rel) && nzchar(chd_png_rel)) {
    img_src <- basename(chd_png_rel)
    img_part <- paste0("<p><img src='", img_src, "' style='max-width:100%;height:auto;border:1px solid #ddd;'/></p>")
  }

  con <- file(chd_html, open = "wt", encoding = "UTF-8")
  on.exit(try(close(con), silent = TRUE), add = TRUE)

  writeLines("<html><head><meta charset='utf-8'/><title>CHD Rainette</title>", con)
  writeLines("<style>body{font-family:Arial,sans-serif;margin:20px;} h1{margin-top:0;}</style>", con)
  writeLines("</head><body>", con)
  writeLines("<h1>CHD (Rainette)</h1>", con)
  writeLines(img_part, con)
  writeLines("</body></html>", con)

  if (!file.exists(chd_html)) return(NULL)
  if (!is.finite(file.info(chd_html)$size) || file.info(chd_html)$size <= 0) return(NULL)

  if (!is.null(rv)) ajouter_log(rv, paste0("CHD HTML généré : ", chd_html))
  file.path("explor", "chd.html")
}
