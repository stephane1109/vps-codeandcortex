args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", grep("^--file=", args_all, value = TRUE)[[1]])
app_dir <- normalizePath(file.path(dirname(file_arg), ".."), winslash = "/", mustWork = TRUE)
source(file.path(app_dir, "iramuteqlite", "variables_etoilees.R"), local = TRUE)
source(file.path(app_dir, "iramuteqlite", "calcul_specificites.R"), local = TRUE)

contient_valeur_utf8 <- function(valeurs, attendue) {
  attendue_raw <- charToRaw(attendue)
  any(vapply(
    as.character(valeurs),
    function(valeur) identical(charToRaw(valeur), attendue_raw),
    logical(1)
  ))
}

corpus_test_path <- normalizePath(
  file.path(app_dir, "..", "..", "corpus_test", "psychiatrie-darmanin-fr.txt"),
  winslash = "/",
  mustWork = TRUE
)
corpus_headers <- readLines(corpus_test_path, encoding = "UTF-8", warn = FALSE)
corpus_headers <- corpus_headers[grepl("^\\*\\*\\*\\*", corpus_headers)]
liberation_header <- corpus_headers[grepl("source_Lib", corpus_headers, fixed = TRUE)][[1L]]
liberation_tokens <- extraire_tokens_entete_iramuteq(liberation_header)
stopifnot(contient_valeur_utf8(liberation_tokens, "*source_Libération"))

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
    `*source` = c("Libération", "Libération", "Le Monde", "Le Monde", "La Croix", "La Croix"),
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
)

variables <- variables_specificites_disponibles(source_data)
stopifnot(length(variables) == 3L)
stopifnot(identical(variables[[1L]]$id, "__classes_chd__"))
stopifnot(identical(variables[[2L]]$id, "*annee"))
source_option <- variables[vapply(variables, function(option) identical(option$id, "*source"), logical(1))][[1L]]
stopifnot(contient_valeur_utf8(unlist(source_option$modalities, use.names = FALSE), "Libération"))

source_table <- table_lexicale_par_modalite(source_data, "*source")
stopifnot(contient_valeur_utf8(colnames(source_table), "Libération"))

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
  output_dir = output_dir
)

expected_files <- c(
  "specificites_terme_modalites.csv",
  "graphique_specificites.png",
  "configuration_specificites.json",
  "resume_specificites.json"
)
stopifnot(all(file.exists(file.path(output_dir, expected_files))))
stopifnot(identical(result$summary$term, "soin"))
stopifnot(identical(result$summary$best_modality, "Classe 1"))
stopifnot(!any(c(
  "tokens_modalite",
  "tokens_corpus",
  "frequence_relative_pour_mille"
) %in% names(result$result)))
stopifnot(!any(file.exists(file.path(output_dir, c(
  "effectifs_formes_modalites.csv",
  "scores_specificites_formes_modalites.csv",
  "frequences_relatives_formes_modalites.csv"
)))))

chi2_full <- calculer_scores_chi2_specificites(lexical_table)$scores["soin", ]
chi2_filtered <- calculer_scores_chi2_specificites(
  lexical_table["soin", , drop = FALSE],
  reference_col_totals = Matrix::colSums(lexical_table)
)$scores["soin", ]
stopifnot(isTRUE(all.equal(chi2_full, chi2_filtered, tolerance = 1e-12)))

cat("test_calcul_specificites: OK\n")
