normaliser_classes <- function(x) {
  y <- trimws(as.character(x))
  y[y == "" | is.na(y)] <- NA_character_
  y
}

regex_echapper <- function(x) {
  gsub("([][{}()+*^$|\\?.])", "\\\\\\1", x)
}

surligner_terme_segment <- function(segment, terme) {
  if (is.na(segment) || !nzchar(segment) || is.na(terme) || !nzchar(terme)) {
    if (is.null(segment) || length(segment) == 0 || is.na(segment)) return("")
    return(htmlEscape(segment))
  }

  seg_safe <- htmlEscape(segment)
  terme_safe <- htmlEscape(terme)
  pattern <- paste0("(?i)(", regex_echapper(terme_safe), ")")

  gsub(
    pattern,
    "<span style='background-color: #fff59d; font-weight: 600;'>\\1</span>",
    seg_safe,
    perl = TRUE
  )
}

generer_table_html_afc_mots <- function(sous_df) {
  if (is.null(sous_df) || nrow(sous_df) == 0) {
    return(tags$p("Aucun terme disponible pour cette classe."))
  }

  en_tetes <- names(sous_df)
  lignes <- lapply(seq_len(nrow(sous_df)), function(i) {
    tags$tr(
      lapply(en_tetes, function(col) {
        val <- sous_df[[col]][i]
        if (col == "Segment_texte") {
          terme <- if ("Terme" %in% names(sous_df)) as.character(sous_df$Terme[i]) else ""
          return(tags$td(HTML(surligner_terme_segment(as.character(val), terme))))
        }
        if (is.null(val) || length(val) == 0 || is.na(val)) return(tags$td(""))
        tags$td(htmlEscape(as.character(val)))
      })
    )
  })

  tags$table(
    class = "table table-striped table-condensed",
    tags$thead(tags$tr(lapply(en_tetes, tags$th))),
    tags$tbody(lignes)
  )
}
