source(file.path("iramuteqlite", "chd_iramuteq.R"))

matrix_underflow <- matrix(
  c(1610, 1000, 0, 5000),
  nrow = 2,
  byrow = TRUE,
  dimnames = list(c("segment_1", "segment_2"), c("cible", "autre"))
)

stats_vectorise <- construire_stats_classes_iramuteq(
  matrix_underflow,
  c(1L, 2L),
  stats_mode = "vectorise"
)
stats_classique <- construire_stats_classes_iramuteq(
  matrix_underflow,
  c(1L, 2L),
  stats_mode = "classique"
)

for (stats_df in list(stats_vectorise, stats_classique)) {
  ligne <- stats_df[stats_df$Terme == "cible" & stats_df$Classe == 1L, , drop = FALSE]
  stopifnot(nrow(ligne) == 1L)
  stopifnot(identical(ligne$p, 0))
  stopifnot(is.finite(ligne$p_log))
  stopifnot(ligne$p_log < log(.Machine$double.xmin))
}

batch_expressions <- parse(file = file.path("backend", "r", "run_iramuteq_batch.R"))
charger_formateur_batch <- function(name) {
  for (expression in batch_expressions) {
    if (
      is.call(expression) &&
        identical(as.character(expression[[1]]), "<-") &&
        identical(as.character(expression[[2]]), name)
    ) {
      eval(expression, envir = .GlobalEnv)
      return(invisible(TRUE))
    }
  }
  stop(paste("Formateur introuvable :", name))
}

charger_formateur_batch("formatter_p_affiche_batch")
charger_formateur_batch("formatter_p_scientifique_batch")

ligne_vectorisee <- stats_vectorise[
  stats_vectorise$Terme == "cible" & stats_vectorise$Classe == 1L,
  ,
  drop = FALSE
]
p_affiche <- formatter_p_affiche_batch(ligne_vectorisee$p)
p_scientifique <- formatter_p_scientifique_batch(ligne_vectorisee$p, ligne_vectorisee$p_log)

stopifnot(identical(p_affiche, "< 1e-323"))
stopifnot(grepl("^[0-9]+\\.[0-9]+e-[0-9]+$", p_scientifique))
stopifnot(!identical(p_scientifique, "0"))

cat("Test p-value sous-flux CHD : OK\n")
