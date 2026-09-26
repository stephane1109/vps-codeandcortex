# Rôle du fichier: point d'entrée UI pour le tracé du dendrogramme IRaMuTeQ-like.
# Ce fichier pilote le mode d'affichage; le rendu graphique bas niveau est implémenté
# dans `tracer_dendrogramme_chd_iramuteq()` (fichier chd_iramuteq.R).

.extraire_payload_dendrogramme <- function(rv) {
  if (is.null(rv)) return(list(chd = NULL, terminales = NULL, classes = NULL, stats = NULL))

  res <- rv$res
  chd <- NULL
  terminales <- NULL
  classes <- NULL

  if (is.list(res)) {
    if (!is.null(res$chd) && is.list(res$chd)) chd <- res$chd
    if (!is.null(res$terminales)) terminales <- res$terminales
    if (!is.null(res$classes)) classes <- res$classes
  }

  if (is.null(classes) && !is.null(rv$filtered_corpus) &&
      requireNamespace("quanteda", quietly = TRUE)) {
    dv <- tryCatch(quanteda::docvars(rv$filtered_corpus), error = function(e) NULL)
    if (!is.null(dv) && "Classes" %in% names(dv)) classes <- dv$Classes
  }

  list(
    chd = chd,
    terminales = terminales,
    classes = classes,
    stats = rv$res_stats_df
  )
}

tracer_dendrogramme_iramuteq_ui <- function(rv,
                                            top_n_terms = 4,
                                            orientation = "horizontal",
                                            style_affichage = c("iramuteq_bars", "factoextra"),
                                            edge_style = c("orthogonal", "diagonal"),
                                            edge_lwd = 2.2) {
  orientation <- match.arg(orientation, c("vertical", "horizontal"))
  style_affichage <- match.arg(style_affichage)
  edge_style <- match.arg(edge_style)
  edge_lwd <- suppressWarnings(as.numeric(edge_lwd))
  if (!is.finite(edge_lwd) || is.na(edge_lwd) || edge_lwd <= 0) edge_lwd <- 2.2

  payload <- .extraire_payload_dendrogramme(rv)

  if (is.null(payload$chd) && (is.null(payload$stats) || !is.data.frame(payload$stats))) {
    plot.new()
    text(0.5, 0.5, "Dendrogramme CHD indisponible.", cex = 1.1)
    return(invisible(NULL))
  }

  ok <- tryCatch({
    tracer_dendrogramme_chd_iramuteq(
      chd_obj = payload$chd,
      terminales = payload$terminales,
      classes = payload$classes,
      res_stats_df = payload$stats,
      top_n_terms = top_n_terms,
      orientation = orientation,
      style_affichage = style_affichage,
      edge_style = edge_style,
      edge_lwd = edge_lwd
    )
    TRUE
  }, error = function(e) FALSE)

  if (!isTRUE(ok)) {
    plot.new()
    text(0.5, 0.5, "Impossible de tracer le dendrogramme CHD.", cex = 1.0)
  }

  invisible(NULL)
}
