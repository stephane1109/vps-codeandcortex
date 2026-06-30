# Rôle du fichier: concordancier-iramuteq.R génère un concordancier HTML dédié au mode IRaMuTeQ-lite.
# Le rendu suit le style IRaMuTeQ-lite (segments par classe + surlignage),
# avec une sélection des termes alignée sur les filtres statistiques IRaMuTeQ-lite.

if (!exists("expandir_variantes_termes", mode = "function")) {
  expandir_variantes_termes <- function(termes) {
    termes <- as.character(termes)
    termes <- trimws(termes)
    termes <- termes[nzchar(termes)]
    unique(c(termes, tolower(termes)))
  }
}


if (!exists(".normaliser_cle_terme_concordancier", mode = "function")) {
  .normaliser_cle_terme_concordancier <- function(x) {
    x <- tolower(trimws(as.character(x)))
    x[is.na(x)] <- ""
    x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
    x[is.na(x)] <- ""
    x <- gsub("[^[:alnum:]_]+", "", x, perl = TRUE)
    x
  }
}

if (!exists("expandir_termes_avec_lexique", mode = "function")) {
  expandir_termes_avec_lexique <- function(termes, lexique_fr_df = NULL) {
    termes <- expandir_variantes_termes(termes)
    if (!length(termes)) return(character(0))

    if (is.null(lexique_fr_df) || !is.data.frame(lexique_fr_df) || nrow(lexique_fr_df) == 0) {
      return(termes)
    }
    colonnes_requises <- c("c_mot", "c_lemme")
    if (!all(colonnes_requises %in% names(lexique_fr_df))) {
      return(termes)
    }

    lex <- lexique_fr_df[, colonnes_requises, drop = FALSE]
    lex$c_mot <- trimws(as.character(lex$c_mot))
    lex$c_lemme <- trimws(as.character(lex$c_lemme))
    idx_ok <- nzchar(lex$c_mot) & nzchar(lex$c_lemme)
    lex <- lex[idx_ok, , drop = FALSE]
    if (!nrow(lex)) return(termes)

    key_lemme <- .normaliser_cle_terme_concordancier(lex$c_lemme)
    key_mot <- .normaliser_cle_terme_concordancier(lex$c_mot)

    map_lemme_to_mot <- split(lex$c_mot[nzchar(key_lemme)], key_lemme[nzchar(key_lemme)])
    map_mot_to_lemme <- split(lex$c_lemme[nzchar(key_mot)], key_mot[nzchar(key_mot)])

    keys <- unique(.normaliser_cle_terme_concordancier(termes))
    keys <- keys[nzchar(keys)]

    formes <- unlist(map_lemme_to_mot[keys], use.names = FALSE)
    lemmes <- unlist(map_mot_to_lemme[keys], use.names = FALSE)

    expandir_variantes_termes(unique(c(termes, formes, lemmes)))
  }
}

if (!exists(".echapper_regex", mode = "function")) {
  .echapper_regex <- function(x) {
    gsub("([][{}()+*^$|\\?.])", "\\\\\\1", x, perl = TRUE)
  }
}

if (!exists(".construire_regex_termes_bornes", mode = "function")) {
  .construire_regex_termes_bornes <- function(termes, taille_lot = 80L, capturer = FALSE, unicode = TRUE) {
    termes <- expandir_variantes_termes(termes)
    if (!length(termes)) return(character(0))

    escaped <- .echapper_regex(termes)
    taille_lot <- suppressWarnings(as.integer(taille_lot))
    if (!is.finite(taille_lot) || is.na(taille_lot) || taille_lot < 1L) taille_lot <- 80L
    lots <- split(escaped, ceiling(seq_along(escaped) / taille_lot))

    borne_gauche <- if (isTRUE(unicode)) "(?<![\\p{L}\\p{N}_])" else "(?<![[:alnum:]_])"
    borne_droite <- if (isTRUE(unicode)) "(?![\\p{L}\\p{N}_])" else "(?![[:alnum:]_])"
    ouvre <- if (isTRUE(capturer)) "(" else "(?:"

    vapply(
      lots,
      function(xs) {
        paste0("(?i)", borne_gauche, ouvre, paste(xs, collapse = "|"), ")", borne_droite)
      },
      character(1)
    )
  }
}

if (!exists("preparer_motifs_surlignage_nfd", mode = "function")) {
  preparer_motifs_surlignage_nfd <- function(termes, taille_lot = 80, unicode = TRUE) {
    # Évite les surlignages partiels (ex: "an" dans "délinquants") en
    # imposant des bornes de mot autour des termes ciblés.
    .construire_regex_termes_bornes(
      termes = termes,
      taille_lot = taille_lot,
      capturer = TRUE,
      unicode = unicode
    )
  }
}

if (!exists("surligner_vecteur_html_unicode", mode = "function")) {
  surligner_vecteur_html_unicode <- function(textes, motifs, prefix = "<span class='highlight'>", suffix = "</span>", on_error = NULL) {
    textes <- as.character(textes)
    if (!length(textes) || !length(motifs)) return(textes)

    out <- textes
    for (pat in motifs) {
      out <- vapply(out, function(txt) {
        tryCatch(
          gsub(pat, paste0(prefix, "\\1", suffix), txt, perl = TRUE),
          error = function(e) {
            if (!is.null(on_error)) on_error(e, pat)
            txt
          }
        )
      }, character(1))
    }
    out
  }
}

if (!exists("echapper_segments_en_preservant_surlignage", mode = "function")) {
  echapper_segments_en_preservant_surlignage <- function(segments, open_tag, close_tag) {
    segments <- as.character(segments)
    sentinel_open <- "___HLOPEN___"
    sentinel_close <- "___HLCLOSE___"

    x <- gsub(open_tag, sentinel_open, segments, fixed = TRUE)
    x <- gsub(close_tag, sentinel_close, x, fixed = TRUE)
    x <- htmltools::htmlEscape(x)
    x <- gsub(sentinel_open, open_tag, x, fixed = TRUE)
    gsub(sentinel_close, close_tag, x, fixed = TRUE)
  }
}

if (!exists("normaliser_espacement_ponctuation_fr", mode = "function")) {
  normaliser_espacement_ponctuation_fr <- function(textes) {
    textes <- as.character(textes)
    if (!length(textes)) return(textes)

    # Corrige les artefacts de concaténation tokenisée, ex: "propositions ."
    textes <- gsub("\\s+([\\.,;:!?%\\)\\]\\}»])", "\\1", textes, perl = TRUE)
    # Évite les doubles espaces et retire les bords.
    textes <- gsub("[[:space:]]{2,}", " ", textes, perl = TRUE)
    trimws(textes)
  }
}

if (!exists("detecter_segments_contenant_termes_unicode", mode = "function")) {
  detecter_segments_contenant_termes_unicode <- function(textes, termes, taille_lot = 80L) {
    textes <- as.character(textes)
    termes <- expandir_variantes_termes(termes)
    if (!length(textes)) return(logical(0))
    if (!length(termes)) return(rep(FALSE, length(textes)))

    patterns_unicode <- .construire_regex_termes_bornes(
      termes = termes,
      taille_lot = taille_lot,
      capturer = FALSE,
      unicode = TRUE
    )
    patterns_ascii <- .construire_regex_termes_bornes(
      termes = termes,
      taille_lot = taille_lot,
      capturer = FALSE,
      unicode = FALSE
    )

    tester_patterns <- function(patterns) {
      out <- rep(FALSE, length(textes))
      for (pat in patterns) {
        out <- out | grepl(pat, textes, perl = TRUE)
      }
      out
    }

    tryCatch(
      tester_patterns(patterns_unicode),
      error = function(e) {
        tryCatch(
          tester_patterns(patterns_ascii),
          error = function(e2) rep(FALSE, length(textes))
        )
      }
    )
  }
}

if (!exists(".filtrer_termes_concordancier", mode = "function")) {
  .filtrer_termes_concordancier <- function(df) {
    if (is.null(df) || !is.data.frame(df)) {
      return(data.frame())
    }
    if (nrow(df) == 0 || !"Terme" %in% names(df)) {
      return(df[0, , drop = FALSE])
    }

    termes <- trimws(as.character(df$Terme))
    keep <- !is.na(termes) & nzchar(termes)

    # Exclut les formes-outils trop génériques qui rendent le concordancier
    # quasi exhaustif pour une classe donnée.
    if ("Type" %in% names(df)) {
      types <- toupper(trimws(as.character(df$Type)))
      types[is.na(types)] <- ""
      types_exclus <- c(
        "PRE",
        "CON",
        "ART_DEF",
        "ART_IND",
        "PRO_DEM",
        "PRO_IND",
        "PRO_PER",
        "PRO_POS",
        "PRO_REL",
        "AUX"
      )
      keep <- keep & !(types %in% types_exclus)
    }

    termes_sans_bruit <- gsub("[^[:alnum:]_]+", "", termes, perl = TRUE)
    keep <- keep & nzchar(termes_sans_bruit) & nchar(termes_sans_bruit) >= 2L

    df[keep, , drop = FALSE]
  }
}

.generer_concordancier_iramuteq_termes <- function(res_stats_df, classe, max_p = 1, filtrer_pvalue = TRUE) {
  if (is.null(res_stats_df) || nrow(res_stats_df) == 0) return(character(0))
  if (!all(c("Classe", "Terme") %in% names(res_stats_df))) return(character(0))

  df <- res_stats_df
  cl <- suppressWarnings(as.numeric(classe))
  if (!is.na(cl)) {
    classes_num <- suppressWarnings(as.numeric(df$Classe))
    df <- df[!is.na(classes_num) & classes_num == cl, , drop = FALSE]
  }

  if (nrow(df) == 0) return(character(0))

  # Filtres IRaMuTeQ-like: p <= max_p et, par défaut, uniquement les chi2 positifs.
  if (isTRUE(filtrer_pvalue)) {
    if ("p" %in% names(df) && is.finite(max_p) && !is.na(max_p)) {
      p_vals <- suppressWarnings(as.numeric(df$p))
      df <- df[!is.na(p_vals) & p_vals <= max_p, , drop = FALSE]
    } else if ("p_value" %in% names(df) && is.finite(max_p) && !is.na(max_p)) {
      p_vals <- suppressWarnings(as.numeric(df$p_value))
      df <- df[!is.na(p_vals) & p_vals <= max_p, , drop = FALSE]
    }
  }

  if ("chi2" %in% names(df)) {
    chi2_vals <- suppressWarnings(as.numeric(df$chi2))
    df <- df[!is.na(chi2_vals) & chi2_vals > 0, , drop = FALSE]
    df <- .filtrer_termes_concordancier(df)
    chi2_vals <- suppressWarnings(as.numeric(df$chi2))
    df <- df[order(-chi2_vals), , drop = FALSE]
  }

  termes <- unique(as.character(df$Terme))
  termes <- termes[!is.na(termes) & nzchar(trimws(termes))]
  termes
}

generer_concordancier_iramuteq_html <- function(
  chemin_sortie,
  segments_by_class,
  res_stats_df,
  max_p,
  filtrer_pvalue = TRUE,
  textes_indexation,
  avancer = NULL,
  rv = NULL,
  ...
) {
  con <- file(chemin_sortie, open = "wt", encoding = "UTF-8")
  on.exit(try(close(con), silent = TRUE), add = TRUE)

  writeLines("<html><head><meta charset='utf-8'/>", con)
  writeLines("<style>body{font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55;color:#1f2937;background:#f8fafc;padding:10px;} h1,h2,h3{color:#0f172a;} .classe-heading{color:#b42318;font-size:1.42rem;font-weight:700;margin:0 0 .65rem 0;} span.highlight{background-color:yellow;color:inherit;font-weight:inherit;padding:0;border-radius:0;} p.segment{margin:0 0 .55rem 0;padding:.45rem .55rem;border-radius:.55rem;background:#ffffff;box-shadow:0 1px 3px rgba(15,23,42,.08);} .classe-bloc{margin-bottom:1.25rem;padding:.7rem .85rem;border:1px solid #e2e8f0;border-radius:.75rem;background:#fefefe;box-shadow:0 2px 8px rgba(15,23,42,.05);}</style>", con)
  writeLines("</head><body>", con)
  writeLines("<h1>Concordancier IRaMuTeQ-like</h1>", con)
  writeLines("<h2>Segments par classe</h2>", con)
  writeLines(if (isTRUE(filtrer_pvalue)) "<h3>Filtrage: p ≤ seuil</h3>" else "<h3>Filtrage: χ² positif (sans filtre p-value)</h3>", con)

  noms_classes <- names(segments_by_class)
  n_classes <- length(noms_classes)
  if (n_classes == 0) n_classes <- 1

  for (i in seq_along(noms_classes)) {
    cl <- noms_classes[[i]]
    if (!is.null(avancer)) avancer(0.75 + (i / n_classes) * 0.08, paste0("HTML IRaMuTeQ : classe ", cl))

    writeLines("<div class='classe-bloc'>", con)
    writeLines(paste0("<h2 class='classe-heading'>Classe ", cl, "</h2>"), con)

    segments <- segments_by_class[[cl]]
    ids_cl <- names(segments)
    if (length(ids_cl) == 0 || all(!nzchar(ids_cl))) {
      # Fallback robuste: certains split() peuvent perdre les noms de documents.
      ids_cl <- as.character(seq_along(segments))
    }

    textes_filtrage <- unname(segments)
    if (!is.null(textes_indexation) && length(textes_indexation) > 0) {
      tx <- textes_indexation[ids_cl]
      ok_tx <- !is.na(tx) & nzchar(tx)
      if (any(ok_tx)) textes_filtrage[ok_tx] <- tx[ok_tx]
    }

    termes_cl <- .generer_concordancier_iramuteq_termes(res_stats_df, cl, max_p = max_p, filtrer_pvalue = filtrer_pvalue)

    if (length(termes_cl) == 0 && !is.null(res_stats_df) && nrow(res_stats_df) > 0 && "Classe" %in% names(res_stats_df)) {
      df_cl <- res_stats_df[suppressWarnings(as.numeric(res_stats_df$Classe)) == suppressWarnings(as.numeric(cl)), , drop = FALSE]
      if (nrow(df_cl) > 0 && "chi2" %in% names(df_cl) && "Terme" %in% names(df_cl)) {
        chi2_vals <- suppressWarnings(as.numeric(df_cl$chi2))
        idx <- !is.na(chi2_vals) & !is.na(df_cl$Terme) & nzchar(as.character(df_cl$Terme))
        if (any(idx)) {
          df_cl <- df_cl[idx, , drop = FALSE]
          df_cl <- .filtrer_termes_concordancier(df_cl)
          df_cl <- df_cl[order(-suppressWarnings(as.numeric(df_cl$chi2))), , drop = FALSE]
          termes_cl <- unique(head(as.character(df_cl$Terme), 20))
        }
      }
    }

    termes_cl <- expandir_termes_avec_lexique(termes_cl, if (!is.null(rv)) rv$lexique_fr_df else NULL)
    keep <- detecter_segments_contenant_termes_unicode(textes_filtrage, termes_cl)
    keep[is.na(keep)] <- FALSE

    segments_keep <- segments[keep]
    ids_keep <- names(segments_keep)

    writeLines(paste0("<p><em>Segments conservés : ", length(segments_keep), " / ", length(segments), "</em></p>"), con)

    if (length(termes_cl) == 0) {
      writeLines("<p><em>Aucun terme concordancier exploitable pour cette classe avec les filtres courants.</em></p>", con)
      writeLines("</div>", con)
      next
    }

    if (length(segments_keep) == 0) {
      writeLines("<p><em>Aucun segment ne correspond aux termes retenus pour cette classe.</em></p>", con)
      writeLines("</div>", con)
      next
    }

    motifs <- preparer_motifs_surlignage_nfd(termes_cl, taille_lot = 80, unicode = TRUE)
    segments_hl <- surligner_vecteur_html_unicode(
      unname(segments_keep),
      motifs,
      "<span class='highlight'>",
      "</span>",
      on_error = function(e, pat) {}
    )

    has_hl <- any(grepl("<span class='highlight'>", segments_hl, fixed = TRUE))
    if (!has_hl) {
      motifs_ascii <- preparer_motifs_surlignage_nfd(termes_cl, taille_lot = 80, unicode = FALSE)
      if (length(motifs_ascii)) {
        segments_hl_ascii <- surligner_vecteur_html_unicode(
          unname(segments_keep),
          motifs_ascii,
          "<span class='highlight'>",
          "</span>",
          on_error = function(e, pat) {}
        )
        if (any(grepl("<span class='highlight'>", segments_hl_ascii, fixed = TRUE))) {
          segments_hl <- segments_hl_ascii
          has_hl <- TRUE
        }
      }
    }

    if (!has_hl) {
      textes_keep_idx <- textes_filtrage[ids_keep]
      if (length(textes_keep_idx) == 0) {
        textes_keep_idx <- textes_filtrage[keep]
      }
      segments_hl_idx <- surligner_vecteur_html_unicode(
        unname(textes_keep_idx),
        motifs,
        "<span class='highlight'>",
        "</span>",
        on_error = function(e, pat) {}
      )
      if (any(grepl("<span class='highlight'>", segments_hl_idx, fixed = TRUE))) {
        segments_hl <- segments_hl_idx
      }
    }

    if (length(segments_hl) == 0 && length(segments_keep) > 0) {
      segments_hl <- unname(segments_keep)
    }

    segments_hl <- normaliser_espacement_ponctuation_fr(segments_hl)
    for (seg in echapper_segments_en_preservant_surlignage(segments_hl, "<span class='highlight'>", "</span>")) {
      writeLines(paste0("<p class='segment'>", seg, "</p>"), con)
    }
    writeLines("</div>", con)
  }

  writeLines("</body></html>", con)
  close(con)
  chemin_sortie
}

generer_concordancier_afc_html <- function(chemin_sortie, afc_table_mots, rv = NULL, max_lignes_par_classe = 100) {
  if (is.null(afc_table_mots) || nrow(afc_table_mots) == 0) return(NULL)

  df <- afc_table_mots
  if (!all(c("Terme", "Classe_max") %in% names(df))) return(NULL)

  colonnes <- intersect(c("Terme", "frequency", "chi2", "p_value", "Segment_texte"), names(df))
  if (length(colonnes) == 0) return(NULL)

  classes <- unique(as.character(df$Classe_max))
  classes <- classes[!is.na(classes) & nzchar(classes)]
  classes <- sort(classes)
  if (length(classes) == 0) return(NULL)

  if (!is.null(rv)) {
    ajouter_log(rv, "Concordancier IRaMuTeQ-like : génération d'un fallback HTML à partir du concordancier AFC.")
  }

  con <- file(chemin_sortie, open = "wt", encoding = "UTF-8")
  on.exit(try(close(con), silent = TRUE), add = TRUE)

  writeLines("<html><head><meta charset='utf-8'/>", con)
  writeLines("<style>body{font-family:Inter,Segoe UI,Arial,sans-serif;line-height:1.55;color:#1f2937;background:#f8fafc;padding:10px;} h1,h2{color:#0f172a;} .classe-heading{color:#b42318;font-size:1.42rem;font-weight:700;margin:1.2rem 0 .65rem 0;} table{width:100%;border-collapse:collapse;margin-bottom:1rem;background:#ffffff;border:1px solid #e2e8f0;border-radius:.65rem;overflow:hidden;} th,td{padding:8px;border-bottom:1px solid #ececec;vertical-align:top;text-align:left;} th{background:#f1f5f9;} span.highlight{background-color:yellow;color:inherit;font-weight:inherit;padding:0;border-radius:0;}</style>", con)
  writeLines("</head><body>", con)
  writeLines("<h1>Concordancier AFC (fallback IRaMuTeQ-like)</h1>", con)

  for (cl in classes) {
    sous_df <- df[df$Classe_max == cl, , drop = FALSE]
    sous_df <- sous_df[, colonnes, drop = FALSE]

    if ("chi2" %in% names(sous_df)) {
      chi2_vals <- suppressWarnings(as.numeric(sous_df$chi2))
      sous_df <- sous_df[order(-chi2_vals), , drop = FALSE]
    }
    sous_df <- head(sous_df, max(1L, as.integer(max_lignes_par_classe)))

    writeLines(paste0("<h2 class='classe-heading'>Classe ", htmltools::htmlEscape(cl), "</h2>"), con)
    writeLines("<table><thead><tr>", con)
    for (col in names(sous_df)) {
      writeLines(paste0("<th>", htmltools::htmlEscape(col), "</th>"), con)
    }
    writeLines("</tr></thead><tbody>", con)

    for (i in seq_len(nrow(sous_df))) {
      terme_ligne <- if ("Terme" %in% names(sous_df)) as.character(sous_df$Terme[[i]]) else ""
      writeLines("<tr>", con)

      for (col in names(sous_df)) {
        val <- sous_df[[col]][[i]]
        txt <- ifelse(is.na(val), "", as.character(val))

        if (identical(col, "Segment_texte")) {
          motifs <- preparer_motifs_surlignage_nfd(terme_ligne, taille_lot = 1)
          if (length(motifs)) {
            txt <- surligner_vecteur_html_unicode(
              txt,
              motifs,
              "<span class='highlight'>",
              "</span>"
            )
            txt <- echapper_segments_en_preservant_surlignage(txt, "<span class='highlight'>", "</span>")
          } else {
            txt <- htmltools::htmlEscape(txt)
          }
        } else {
          txt <- htmltools::htmlEscape(txt)
        }

        writeLines(paste0("<td>", txt, "</td>"), con)
      }

      writeLines("</tr>", con)
    }

    writeLines("</tbody></table>", con)
  }

  writeLines("</body></html>", con)
  close(con)
  if (!is.null(rv)) ajouter_log(rv, paste0("Concordancier AFC (fallback) : HTML écrit dans : ", chemin_sortie))
  chemin_sortie
}
