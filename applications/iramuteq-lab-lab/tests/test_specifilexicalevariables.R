# Tests du calcul complémentaire de toutes les formes par variable étoilée.
args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", grep("^--file=", args_all, value = TRUE)[[1]])
app_dir <- normalizePath(file.path(dirname(file_arg), ".."), mustWork = TRUE)
source(file.path(app_dir, "iramuteqlite", "calcul_specificites.R"), local = TRUE)
source(file.path(app_dir, "iramuteqlite", "specifilexicalevariables.R"), local = TRUE)

matrice <- Matrix::Matrix(
  c(8, 1, 0,
    5, 2, 0,
    0, 2, 7,
    0, 1, 9),
  nrow = 4, byrow = TRUE, sparse = TRUE,
  dimnames = list(paste0("segment_", 1:4), c("violence", "manifestation", "tension"))
)
source_test <- list(
  dfm = methods::as(matrice, "dgCMatrix"),
  classes = c(1L, 1L, 2L, 2L),
  docvars = data.frame(
    `*source` = c("original", "original", "ia", "ia"),
    `*profil` = c("cnews", "cnews", "cnews", "cnews"),
    check.names = FALSE
  )
)
repertoire <- tempfile("test-variables-")
dir.create(repertoire, recursive = TRUE)
on.exit(unlink(repertoire, recursive = TRUE, force = TRUE), add = TRUE)

resultat <- ecrire_specificites_lexicales_variables(
  source_test, "*source", "hypergeo", repertoire
)
stopifnot(identical(resultat$summary$n_forms, 3L))
stopifnot(identical(resultat$summary$n_modalities, 2L))
stopifnot(identical(resultat$summary$n_comparisons, 6L))
stopifnot(file.exists(file.path(repertoire, "specificites_formes_variables.csv")))
stopifnot(file.exists(file.path(repertoire, "resume_specificites_variables.json")))
tableau <- utils::read.csv(file.path(repertoire, "specificites_formes_variables.csv"))
stopifnot(nrow(tableau) == 6L)
stopifnot(all(c("p_value", "p_ajustee_bh", "score_specificite",
                "occurrences_attendues") %in% names(tableau)))
original_violent <- subset(tableau, modalite == "original" & forme == "violence")
ia_violent <- subset(tableau, modalite == "ia" & forme == "violence")
stopifnot(nrow(original_violent) == 1L && original_violent$score_specificite > 0)
stopifnot(nrow(ia_violent) == 1L && ia_violent$score_specificite < 0)
stopifnot(all(tableau$p_ajustee_bh >= tableau$p_value))
stopifnot(all(tableau$p_ajustee_bh <= 1))

resultat_chi2 <- ecrire_specificites_lexicales_variables(
  source_test, "*source", "chi2", repertoire
)
stopifnot(identical(resultat_chi2$summary$index, "chi2"))
stopifnot(inherits(try(
  ecrire_specificites_lexicales_variables(source_test, "*profil", "hypergeo", repertoire),
  silent = TRUE
), "try-error"))
cat("test_specifilexicalevariables: OK\n")
