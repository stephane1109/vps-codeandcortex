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
    dimnames = list(c("terme_a", "terme_b", "terme_hors_selection"), c("Dim 1", "Dim 2"))
  ),
  termes_stats = data.frame(
    Terme = c("terme_a", "terme_b", "terme_hors_selection"),
    frequency = c(10, 9, 1),
    Classe_max = c("Classe 1", "Classe 2", "Classe 2"),
    chi2 = c(12, 11, 3),
    stringsAsFactors = FALSE
  )
)

classes_file <- tempfile(fileext = ".pdf")
terms_file <- tempfile(fileext = ".pdf")

grDevices::pdf(classes_file)
tracer_afc_classes_seules(obj, axes = c(1, 2), top_termes = 2L)
classes_limits <- graphics::par("usr")
grDevices::dev.off()

grDevices::pdf(terms_file)
tracer_afc_classes_termes(obj, axes = c(1, 2), top_termes = 2L, activer_repel = FALSE)
terms_limits <- graphics::par("usr")
grDevices::dev.off()

stopifnot(isTRUE(all.equal(classes_limits, terms_limits, tolerance = 1e-12)))

unlink(c(classes_file, terms_file))
cat("test_afc_plot_scales.R: OK\n")
