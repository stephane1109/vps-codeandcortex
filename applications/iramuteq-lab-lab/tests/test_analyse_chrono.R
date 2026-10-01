args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", grep("^--file=", args_all, value = TRUE)[[1]])
app_dir <- normalizePath(file.path(dirname(file_arg), ".."), winslash = "/", mustWork = TRUE)
source(file.path(app_dir, "iramuteqlite", "analyse-chrono.R"), local = TRUE)

source_data <- list(
  classes = c(1L, 1L, 2L, 2L, 1L, 2L, 1L, 2L, 2L, 2L, 1L, 1L),
  docvars = data.frame(
    `*annee` = rep(c("2022", "2023", "2024"), each = 4),
    `*quotidien` = rep(c("Libération", "Le Monde"), 6),
    segment_source = paste0("article_", rep(seq_len(6), each = 2)),
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
)

description <- decrire_analyse_chrono(source_data)
stopifnot(isTRUE(description$available))
stopifnot(identical(description$suggested_time_variable, "*annee"))
stopifnot(length(description$variables) == 2L)

output_dir <- tempfile("analyse-chrono-test-")
dir.create(output_dir, recursive = TRUE)
on.exit(unlink(output_dir, recursive = TRUE, force = TRUE), add = TRUE)
result <- ecrire_resultats_chrono(
  source_data,
  time_variable = "*annee",
  comparison_variable = "*quotidien",
  output_dir = output_dir
)

expected_files <- c(
  "chronologie_croisee_effectifs.csv",
  "chronologie_croisee_pourcentages.csv",
  "chronologie_croisee_chi2.csv",
  "chronologie_croisee_residus.csv",
  "chronologie_croisee_evolution.png",
  "chronologie_croisee_residus.png",
  "configuration_chronologie.json",
  "resume_chronologie.json"
)
stopifnot(all(file.exists(file.path(output_dir, expected_files))))
stopifnot(identical(result$summary$n_periods, 3L))
stopifnot(identical(result$summary$n_comparison_modalities, 2L))
stopifnot(identical(result$summary$n_classes, 2L))
stopifnot(identical(result$summary$n_chi2_tests, 2L))

percentages <- utils::read.csv(file.path(output_dir, "chronologie_croisee_pourcentages.csv"), check.names = FALSE)
totals <- stats::aggregate(pourcentage ~ periode + modalite_comparaison, percentages, sum)
stopifnot(all(abs(totals$pourcentage - 100) < 0.01))

same_variable_error <- tryCatch({
  preparer_donnees_chrono(source_data, "*annee", "*annee")
  FALSE
}, error = function(error) TRUE)
stopifnot(same_variable_error)

cat("test_analyse_chrono: OK\n")
