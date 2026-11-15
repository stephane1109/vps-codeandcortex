# Vérifie l'utilisation du moteur historique sur une matrice creuse.
# Ce test couvre les sommes de lignes/colonnes et l'entrée de la CHD,
# sans attacher explicitement le package Matrix avec library().

if (!requireNamespace("Matrix", quietly = TRUE)) {
  stop("Le package Matrix est nécessaire au test.")
}

source(file.path("iramuteqlite", "anacor.R"))
source(file.path("iramuteqlite", "CHD.R"))

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
