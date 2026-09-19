source("iramuteqlite/afc_iramuteq.R")

obj <- list(
  ca = list(),
  rowcoord = matrix(
    c(-0.35, -0.10, 0.28, 0.16),
    ncol = 2,
    byrow = TRUE,
    dimnames = list(c("Classe 1", "Classe 2"), c("Dim 1", "Dim 2"))
  ),
  colcoord = matrix(
    c(-1.60, -0.75, 1.20, 1.95, 8.00, 8.00),
    ncol = 2,
    byrow = TRUE,
    dimnames = list(c("terme_a", "terme_b", "terme_hors_sélection"), c("Dim 1", "Dim 2"))
  ),
  termes_stats = data.frame(
    Terme = c("terme_a", "terme_b", "terme_hors_sélection"),
    frequency = c(10, 9, 1),
    Classe_max = c("Classe 1", "Classe 2", "Classe 2"),
    chi2 = c(12, 11, 3),
    stringsAsFactors = FALSE
  )
)
Encoding(obj$termes_stats$Terme[[3]]) <- "unknown"
terme_repere_force <- rownames(obj$colcoord)[[3L]]
Encoding(terme_repere_force) <- "UTF-8"
normaliser_termes_test <- function(valeurs) {
  termes <- tolower(trimws(as.character(valeurs)))
  Encoding(termes) <- "UTF-8"
  termes
}

coords_enrichies <- ajouter_coordonnees_afc_aux_termes_iramuteq(
  data.frame(Terme = c("TERME_A", "terme_b", "terme_absent"), stringsAsFactors = FALSE),
  obj$colcoord
)
stopifnot(
  abs(coords_enrichies$afc_x[[1]] + 1.6) < 1e-12,
  abs(coords_enrichies$afc_y[[2]] - 1.95) < 1e-12,
  is.na(coords_enrichies$afc_x[[3]]),
  is.na(coords_enrichies$afc_y[[3]])
)

termes_avec_repere <- .selectionner_termes_trace_afc(
  obj,
  axes = c(1, 2),
  top_termes = 2L,
  termes_forces = terme_repere_force
)
stopifnot(
  all(
    normaliser_termes_test(c(obj$termes_stats$Terme[1:2], terme_repere_force)) %in%
      normaliser_termes_test(termes_avec_repere$mots)
  )
)

classes_file <- tempfile(fileext = ".pdf")
terms_file <- tempfile(fileext = ".pdf")

grDevices::pdf(classes_file)
tracer_afc_classes_seules(
  obj,
  axes = c(1, 2),
  top_termes = 2L,
  termes_forces = terme_repere_force
)
classes_limits <- graphics::par("usr")
grDevices::dev.off()

grDevices::pdf(terms_file)
tracer_afc_classes_termes(
  obj,
  axes = c(1, 2),
  top_termes = 2L,
  termes_forces = terme_repere_force,
  activer_repel = FALSE
)
terms_limits <- graphics::par("usr")
grDevices::dev.off()

stopifnot(isTRUE(all.equal(classes_limits, terms_limits, tolerance = 1e-12)))

unlink(c(classes_file, terms_file))
cat("test_afc_plot_scales.R: OK\n")
