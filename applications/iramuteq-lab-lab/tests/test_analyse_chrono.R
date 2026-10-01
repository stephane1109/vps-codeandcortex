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
stopifnot(isTRUE(description$iramuteq_available))
stopifnot(isTRUE(description$crossed_available))
stopifnot(identical(description$suggested_time_variable, "*annee"))
stopifnot(length(description$variables) == 2L)

single_variable_source <- source_data
single_variable_source$docvars$`*quotidien` <- NULL
single_variable_description <- decrire_analyse_chrono(single_variable_source)
stopifnot(isTRUE(single_variable_description$available))
stopifnot(isTRUE(single_variable_description$iramuteq_available))
stopifnot(identical(single_variable_description$crossed_available, FALSE))

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

single_output_dir <- tempfile("vue-chronologique-test-")
dir.create(single_output_dir, recursive = TRUE)
on.exit(unlink(single_output_dir, recursive = TRUE, force = TRUE), add = TRUE)
single_result <- ecrire_resultats_chrono(
  source_data,
  time_variable = "*annee",
  output_dir = single_output_dir,
  analysis_mode = "iramuteq"
)
single_expected_files <- c(
  "vue_chronologique_proportions.csv",
  "vue_chronologique_chi2.csv",
  "vue_chronologique_test_global.csv",
  "vue_chronologique_proportions.png",
  "vue_chronologique_chi2.png",
  "configuration_chronologie.json",
  "resume_chronologie.json"
)
stopifnot(all(file.exists(file.path(single_output_dir, single_expected_files))))
stopifnot(identical(single_result$summary$analysis_mode, "iramuteq"))
stopifnot(identical(single_result$summary$n_periods, 3L))
stopifnot(identical(single_result$summary$n_classes, 2L))

single_proportions <- utils::read.csv(
  file.path(single_output_dir, "vue_chronologique_proportions.csv"),
  check.names = FALSE
)
single_totals <- stats::aggregate(pourcentage ~ periode, single_proportions, sum)
stopifnot(all(abs(single_totals$pourcentage - 100) < 0.01))
single_chi2 <- utils::read.csv(file.path(single_output_dir, "vue_chronologique_chi2.csv"), check.names = FALSE)
stopifnot(nrow(single_chi2) == 6L)
stopifnot(all(c("observe", "attendu", "chi2", "p_value") %in% names(single_chi2)))

same_variable_error <- tryCatch({
  preparer_donnees_chrono(source_data, "*annee", "*annee")
  FALSE
}, error = function(error) TRUE)
stopifnot(same_variable_error)

cat("test_analyse_chrono: OK\n")
