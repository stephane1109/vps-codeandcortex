source(file.path("iramuteqlite", "chd_iramuteq.R"))
source(file.path("iramuteqlite", "ui_chd_stats_mode_iramuteq.R"))

stopifnot(identical(normaliser_mode_stats_chd_iramuteq("classique"), "vectorise"))

classes <- c(1L, 1L, 1L, 2L, 2L, 2L)
mat_reference <- matrix(
  c(
    1, 2,
    1, 1,
    1, 2,
    1, 1,
    0, 2,
    0, 3
  ),
  nrow = 6,
  byrow = TRUE,
  dimnames = list(paste0("uce_", 1:6), c("cible", "autre"))
)
mat_repetitions <- mat_reference
mat_repetitions[1, "cible"] <- 25
mat_repetitions[4, "cible"] <- 7

stats_reference <- construire_stats_classes_iramuteq(mat_reference, classes)
stats_repetitions <- construire_stats_classes_iramuteq(
  mat_repetitions,
  classes,
  stats_mode = "classique"
)

extraire_cible <- function(x) {
  x[x$Terme == "cible", c("Classe", "chi2", "p", "eff_st", "eff_total", "occ_st", "occ_total")]
}

cible_reference <- extraire_cible(stats_reference)
cible_repetitions <- extraire_cible(stats_repetitions)

stopifnot(nrow(cible_reference) == 2L)
stopifnot(identical(cible_reference$eff_st, c(3, 1)))
stopifnot(all(cible_reference$eff_total == 4))

table_classe_1 <- matrix(c(3, 1, 0, 2), nrow = 2, byrow = TRUE)
chi_attendu <- unname(stats::chisq.test(table_classe_1, correct = FALSE)$statistic)
p_attendue <- stats::pchisq(chi_attendu, df = 1, lower.tail = FALSE)
stopifnot(isTRUE(all.equal(cible_reference$chi2, c(chi_attendu, -chi_attendu), tolerance = 1e-12)))
stopifnot(isTRUE(all.equal(cible_reference$p, c(p_attendue, p_attendue), tolerance = 1e-12)))
stopifnot(isTRUE(all.equal(cible_reference$chi2, cible_repetitions$chi2, tolerance = 1e-12)))
stopifnot(isTRUE(all.equal(cible_reference$p, cible_repetitions$p, tolerance = 1e-12)))
stopifnot(!identical(cible_reference$occ_st, cible_repetitions$occ_st))
stopifnot(!identical(cible_reference$occ_total, cible_repetitions$occ_total))

cat("Test statistiques CHD sur effectifs documentaires UCE : OK\n")
