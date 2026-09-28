args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", grep("^--file=", args_all, value = TRUE)[[1]])
app_dir <- normalizePath(file.path(dirname(file_arg), ".."), winslash = "/", mustWork = TRUE)
source(file.path(app_dir, "iramuteqlite", "calcul_specificites.R"), local = TRUE)

dfm <- Matrix::Matrix(
  c(
    4, 1, 0,
    3, 1, 0,
    0, 2, 3,
    0, 1, 4,
    1, 3, 1,
    0, 4, 1
  ),
  nrow = 6,
  byrow = TRUE,
  sparse = TRUE,
  dimnames = list(
    paste0("segment", seq_len(6)),
    c("soin", "patient", "loi")
  )
)
source_data <- list(
  dfm = methods::as(dfm, "dgCMatrix"),
  classes = c(1L, 1L, 2L, 2L, 3L, 3L),
  docvars = data.frame(
    `*annee` = c("2024", "2024", "2025", "2025", "2026", "2026"),
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
)

variables <- variables_specificites_disponibles(source_data)
stopifnot(length(variables) == 2L)
stopifnot(identical(variables[[1L]]$id, "__classes_chd__"))
stopifnot(identical(variables[[2L]]$id, "*annee"))

lexical_table <- table_lexicale_par_modalite(source_data, "__classes_chd__")
stopifnot(identical(dim(lexical_table), c(3L, 3L)))
scores <- calculer_scores_hypergeometriques(lexical_table)$scores
stopifnot(scores["soin", "Classe 1"] > 0)
stopifnot(scores["soin", "Classe 2"] < 0)

output_dir <- tempfile("specificites-test-")
dir.create(output_dir, recursive = TRUE)
on.exit(unlink(output_dir, recursive = TRUE, force = TRUE), add = TRUE)
result <- ecrire_resultats_specificites(
  source = source_data,
  term = "soin",
  variable = "__classes_chd__",
  index = "hypergeo",
  min_frequency = 1L,
  output_dir = output_dir
)

expected_files <- c(
  "specificites_terme_modalites.csv",
  "effectifs_formes_modalites.csv",
  "scores_specificites_formes_modalites.csv",
  "frequences_relatives_formes_modalites.csv",
  "graphique_specificites.png",
  "configuration_specificites.json",
  "resume_specificites.json"
)
stopifnot(all(file.exists(file.path(output_dir, expected_files))))
stopifnot(identical(result$summary$term, "soin"))
stopifnot(identical(result$summary$best_modality, "Classe 1"))

high_threshold_dir <- file.path(output_dir, "high-threshold")
high_threshold_result <- ecrire_resultats_specificites(
  source = source_data,
  term = "soin",
  variable = "__classes_chd__",
  index = "hypergeo",
  min_frequency = 99L,
  output_dir = high_threshold_dir
)
stopifnot(identical(high_threshold_result$summary$term, "soin"))
stopifnot(identical(high_threshold_result$summary$n_forms, 1L))

cat("test_calcul_specificites: OK\n")
