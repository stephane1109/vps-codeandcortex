# Vérifie le chargement historique de Matrix avant la CHD creuse.
# Les fonctions R de transposition doivent traiter les objets dgCMatrix.

if (!requireNamespace("Matrix", quietly = TRUE)) {
  stop("Le package Matrix est nécessaire au test.")
}

source(file.path("iramuteqlite", "chd_iramuteq.R"))
.charger_scripts_iramuteq_chd("iramuteqlite")
stopifnot("package:Matrix" %in% search())

# Préparer un petit corpus binaire avec deux groupes lexicaux distincts.
nb_segments <- 40L
nb_termes <- 12L
indices_lignes <- rep(seq_len(nb_segments), each = 4L)
indices_colonnes <- unlist(lapply(seq_len(nb_segments), function(indice) {
  if (indice <= 20L) {
    c(1L, 2L, 3L, 4L)
  } else {
    c(7L, 8L, 9L, 10L)
  }
}), use.names = FALSE)

matrice_creuse <- Matrix::sparseMatrix(
  i = indices_lignes,
  j = indices_colonnes,
  x = rep(1, length(indices_lignes)),
  dims = c(nb_segments, nb_termes)
)
# Ajouter des formes partagées pour éviter une opposition strictement séparée.
matrice_creuse[seq_len(nb_segments), 11L] <- 1
matrice_creuse[seq(1L, nb_segments, by = 2L), 12L] <- 1
matrice_creuse <- Matrix::drop0(matrice_creuse)

stopifnot(inherits(matrice_creuse, "dgCMatrix"))
# Sans library(Matrix), t() peut appeler t.default et refuser une dgCMatrix.
matrice_transposee <- t(matrice_creuse)
stopifnot(inherits(matrice_transposee, "Matrix"))
stopifnot(identical(dim(matrice_transposee), rev(dim(matrice_creuse))))
stopifnot(isTRUE(all.equal(
  unname(Matrix::colSums(matrice_creuse)),
  unname(base::colSums(as.matrix(matrice_creuse))),
  check.attributes = FALSE
)))
stopifnot(isTRUE(all.equal(
  unname(Matrix::rowSums(matrice_creuse)),
  unname(base::rowSums(as.matrix(matrice_creuse))),
  check.attributes = FALSE
)))

# L'AFC du moteur doit accepter directement la matrice creuse.
methode_svd <- if (requireNamespace("irlba", quietly = TRUE)) "irlba" else "svdR"
set.seed(20260909L)
resultat_afc <- boostana(matrice_creuse, ndim = 1L, svd.method = methode_svd)
stopifnot(nrow(resultat_afc$row.scores) == nb_segments)

# Exercer réellement la fonction CHD, sans la remplacer par une simulation.
set.seed(20260909L)
resultat_chd <- CHD(
  data.in = matrice_creuse,
  x = 1L,
  mode.patate = TRUE,
  svd.method = methode_svd
)
stopifnot(is.list(resultat_chd))
stopifnot(!is.null(resultat_chd$n1))
stopifnot(nrow(resultat_chd$n1) == nb_segments)

cat("Compatibilité CHD / matrices creuses : OK\n")
