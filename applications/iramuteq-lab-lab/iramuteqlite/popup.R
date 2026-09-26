# Rôle du fichier: centraliser la logique de popup (modale) pour l'ouverture
# des segments relatifs à une forme sélectionnée dans Stats CHD.

nettoyer_html_vers_texte_popup <- function(x) {
  txt <- as.character(if (is.null(x)) "" else x)
  txt <- gsub("<[^>]+>", "", txt)
  trimws(txt)
}

extraire_segments_forme_classe_popup <- function(rv, classe, forme, max_segments = 200L) {
  if (is.null(rv$filtered_corpus) || is.null(rv$dfm) || !nzchar(trimws(as.character(forme)))) {
    return(character(0))
  }

  classes_docs <- suppressWarnings(as.character(quanteda::docvars(rv$filtered_corpus)$Classes))
  idx_classe <- which(classes_docs == as.character(classe))
  if (!length(idx_classe)) return(character(0))

  doc_ids_corpus <- as.character(quanteda::docnames(rv$filtered_corpus))[idx_classe]
  doc_ids_dfm <- as.character(quanteda::docnames(rv$dfm))
  doc_ids <- intersect(doc_ids_corpus, doc_ids_dfm)
  if (!length(doc_ids)) return(character(0))

  forme_use <- trimws(as.character(forme))
  feats <- as.character(quanteda::featnames(rv$dfm))

  if (forme_use %in% feats) {
    sous_dfm <- rv$dfm[doc_ids, forme_use, drop = FALSE]
    mat <- tryCatch(quanteda::convert(sous_dfm, to = "matrix"), error = function(...) NULL)
    if (!is.null(mat) && nrow(mat) > 0 && ncol(mat) > 0) {
      keep <- as.numeric(mat[, 1]) > 0
      doc_ids <- rownames(mat)[keep]
    } else {
      doc_ids <- character(0)
    }
  } else {
    segments_txt <- as.character(rv$filtered_corpus[doc_ids])
    motif <- paste0("\\b", gsub("([\\W])", "\\\\\\1", forme_use, perl = TRUE), "\\b")
    keep <- suppressWarnings(grepl(motif, segments_txt, perl = TRUE, ignore.case = TRUE))
    doc_ids <- doc_ids[keep]
  }

  if (!length(doc_ids)) return(character(0))

  segments <- as.character(rv$filtered_corpus[doc_ids])
  segments <- segments[!is.na(segments) & nzchar(trimws(segments))]
  if (!length(segments)) return(character(0))

  utils::head(segments, max(1L, as.integer(max_segments)))
}

enregistrer_popup_forme_stats_chd <- function(input, rv, classe, output_id, seuil_p_significativite) {
  observeEvent(input[[paste0(output_id, "_cell_clicked")]], {
    info <- input[[paste0(output_id, "_cell_clicked")]]
    if (is.null(info$row)) return(invisible(NULL))

    df_affiche <- extraire_stats_chd_classe(
      rv$res_stats_df,
      classe = classe,
      n_max = NULL,
      show_negative = FALSE,
      max_p = 1,
      seuil_p_significativite = seuil_p_significativite(),
      style = "iramuteq_clone"
    )
    if (!is.data.frame(df_affiche) || !"forme" %in% names(df_affiche) || nrow(df_affiche) == 0) {
      return(invisible(NULL))
    }

    row_idx <- suppressWarnings(as.integer(info$row))
    if (!is.finite(row_idx) || is.na(row_idx)) return(invisible(NULL))
    if (row_idx >= 0L && row_idx < nrow(df_affiche)) {
      row_idx <- row_idx + 1L
    }
    if (row_idx < 1L || row_idx > nrow(df_affiche)) return(invisible(NULL))

    forme_sel <- nettoyer_html_vers_texte_popup(df_affiche$forme[[row_idx]])

    col_idx <- suppressWarnings(as.integer(info$col))
    col_forme <- match("forme", names(df_affiche))
    if (is.finite(col_idx) && !is.na(col_idx) && !is.na(col_forme)) {
      if (identical(col_idx, col_forme) || identical(col_idx + 1L, col_forme)) {
        forme_clic <- nettoyer_html_vers_texte_popup(info$value)
        if (nzchar(forme_clic)) forme_sel <- forme_clic
      }
    }

    if (!nzchar(forme_sel)) return(invisible(NULL))

    segments_forme <- extraire_segments_forme_classe_popup(rv, classe, forme_sel, max_segments = 300L)

    showModal(modalDialog(
      title = paste0("Classe ", classe, " — forme: ", forme_sel),
      size = "l",
      easyClose = TRUE,
      footer = modalButton("Fermer"),
      if (!length(segments_forme)) {
        tags$p("Aucun segment trouvé pour cette forme dans la classe sélectionnée.")
      } else {
        tags$div(
          tags$p(paste0("Segments trouvés: ", length(segments_forme))),
          lapply(segments_forme, function(seg) {
            tags$p(
              class = "segment",
              HTML(surligner_segment_afc(seg, forme_sel))
            )
          })
        )
      }
    ))
  }, ignoreInit = TRUE)
}
