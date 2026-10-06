script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
repo_root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
source(file.path(repo_root, "iramuteqlite", "distance-labbe.R"), local = TRUE)

assert_close <- function(actual, expected, tolerance = 1e-12) {
  stopifnot(isTRUE(all.equal(actual, expected, tolerance = tolerance)))
}

identical_tab <- cbind(A = c(5, 3, 2), B = c(5, 3, 2))
assert_close(compute.labbe(1, 2, identical_tab), 0)

proportional_tab <- cbind(A = c(10, 6, 4), B = c(5, 3, 2))
assert_close(compute.labbe(1, 2, proportional_tab), 0)
assert_close(compute.labbe(2, 1, proportional_tab), 0)

disjoint_tab <- cbind(A = c(10, 0), B = c(0, 10))
assert_close(compute.labbe(1, 2, disjoint_tab), 1)

# Fonction de référence recopiée du script officiel d'IRaMuTeQ.
compute_labbe_reference <- function(x, y, tab) {
  mini.tab <- tab[, c(x, y)]
  cs <- colSums(mini.tab)
  N1 <- cs[1]
  N2 <- cs[2]
  plus.grand <- ifelse(N1 > N2, 1, 2)
  plus.petit <- ifelse(N1 > N2, 2, 1)
  if (plus.grand == 1) {
    U <- N2 / N1
    mini.tab[, 1] <- mini.tab[, 1] * U
    col.plusgrand <- mini.tab[, 1]
    cs.plus.grand <- sum(col.plusgrand[col.plusgrand >= 1])
  } else {
    U <- N1 / N2
    mini.tab[, 2] <- mini.tab[, 2] * U
    col.plusgrand <- mini.tab[, 2]
    cs.plus.grand <- sum(col.plusgrand[col.plusgrand > 1])
  }
  commun <- which((mini.tab[, 1] > 0) & (mini.tab[, 2] > 0))
  deA <- which((mini.tab[, plus.petit] > 0) & (mini.tab[, plus.grand] == 0))
  deB <- which((mini.tab[, plus.petit] == 0) & (mini.tab[, plus.grand] >= 1))
  dist.labbe <-
    sum(abs(mini.tab[commun, plus.petit] - mini.tab[commun, plus.grand])) +
    sum(abs(mini.tab[deA, plus.petit] - mini.tab[deA, plus.grand])) +
    sum(abs(mini.tab[deB, plus.petit] - mini.tab[deB, plus.grand]))
  unname(dist.labbe / (cs[plus.petit] + cs.plus.grand))
}

reference_tabs <- list(
  cbind(A = c(2, 0, 2), B = c(1, 1, 2)),
  cbind(A = c(8, 3, 1, 0), B = c(2, 2, 0, 4)),
  cbind(A = c(5, 1, 7), B = c(2, 4, 3))
)
for (reference_tab in reference_tabs) {
  assert_close(compute.labbe(1, 2, reference_tab), compute_labbe_reference(1, 2, reference_tab))
}

matrix_result <- dist.labbe(cbind(A = c(5, 3, 2), B = c(5, 3, 2), C = c(0, 8, 2)))
stopifnot(isTRUE(all.equal(matrix_result, t(matrix_result))))
stopifnot(all(diag(matrix_result) == 0))
stopifnot(all(matrix_result >= 0 & matrix_result <= 1))

tree_path <- tempfile(fileext = ".png")
tracer_dendrogramme_labbe(matrix_result, tree_path)
stopifnot(file.exists(tree_path), file.info(tree_path)$size > 0)
unlink(tree_path)

invalid <- try(compute.labbe(1, 2, cbind(A = c(0, 0), B = c(1, 2))), silent = TRUE)
stopifnot(inherits(invalid, "try-error"))

# L'analyse est autonome : seules les modalités du corpus définissent les textes.
source_data <- list(
  dfm = Matrix::Matrix(
    matrix(c(3, 0, 1, 2, 0, 4), nrow = 3, byrow = TRUE, dimnames = list(NULL, c("alpha", "beta"))),
    sparse = TRUE
  ),
  docvars = data.frame(`*source` = c("A", "A", "B"), check.names = FALSE),
  classes = c(1L, 2L, 3L)
)
available <- variables_labbe_disponibles(source_data)
stopifnot(identical(vapply(available, function(item) item$id, character(1)), "*source"))
aggregated <- table_labbe_par_modalite(source_data, "*source", min_effectif = 1L)
stopifnot(identical(colnames(aggregated), c("A", "B")))
frequency_filtered <- table_labbe_par_modalite(source_data, "*source", min_effectif = 5L)
stopifnot(identical(rownames(frequency_filtered), "beta"))

lexicon_source <- list(
  dfm = Matrix::Matrix(
    matrix(c(3, 2, 1, 1, 4, 2), nrow = 2, byrow = TRUE, dimnames = list(NULL, c("chat", "avec", "inconnu"))),
    sparse = TRUE
  ),
  docvars = data.frame(`*source` = c("A", "B"), check.names = FALSE),
  lexique = data.frame(
    c_mot = c("chat", "avec"),
    c_lemme = c("chat", "avec"),
    c_morpho = c("nom", "pre"),
    stringsAsFactors = FALSE
  ),
  preprocessing = list(lemmatisation = TRUE, type_formes = "active")
)
active_table <- table_labbe_par_modalite(lexicon_source, "*source", min_effectif = 1L)
stopifnot(identical(rownames(active_table), c("chat", "inconnu")))
supplementary_table <- table_labbe_par_modalite(
  lexicon_source,
  "*source",
  min_effectif = 1L,
  type_formes = "supplementary"
)
stopifnot(identical(rownames(supplementary_table), "avec"))

cat("Tests distance de Labbe: OK\n")
