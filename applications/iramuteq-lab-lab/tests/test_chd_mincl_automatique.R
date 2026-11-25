# Vérifie la valeur automatique de mincl, indépendamment de la classe 0.
# Le seuil manuel et le moteur statistique ne sont pas modifiés.

source(file.path("iramuteqlite", "chd_iramuteq.R"))

# 576 segments et 10 classes de première phase : 58, et non 52.
stopifnot(identical(calculer_mincl_auto_iramuteq(576L, 10L, "simple"), 58L))
stopifnot(identical(calculer_mincl_auto_iramuteq(581L, 10L, "simple"), 58L))
stopifnot(identical(calculer_mincl_auto_iramuteq(576L, 10L, "double"), 29L))

# Une classe 0 ainsi que dix classes positives apparaissent dans la
# dernière colonne, mais ne doivent pas produire un diviseur égal à 11.
n1 <- matrix(2L, nrow = 576L, ncol = 9L)
n1[, 9L] <- rep(c(0L, seq.int(2L, 11L)), length.out = nrow(n1))
arbre <- list(
  n1 = n1,
  list_mere = vector("list", 25L),
  list_fille = vector("list", 25L)
)

mincl_observe <- NULL
find.terminales <- function(n1, list_mere, list_fille, mincl) {
  mincl_observe <<- mincl
  c("2", "3")
}

# Avec la cible explicite, le nombre d'étapes et la classe 0
# n'interviennent pas dans le dénominateur.
resultat_auto <- reconstruire_classes_terminales_iramuteq(
  chd_obj = arbre,
  mincl_mode = "auto",
  classif_mode = "simple",
  nb_classes_cible = 10L,
  respecter_nb_classes = FALSE
)
stopifnot(identical(resultat_auto$mincl, 58L))
stopifnot(identical(mincl_observe, 58L))
stopifnot(any(resultat_auto$classes == 0L))

# Sans cible explicite, les 9 divisions donnent 10 classes prévues.
resultat_sans_cible <- reconstruire_classes_terminales_iramuteq(
  chd_obj = arbre,
  mincl_mode = "auto",
  classif_mode = "simple",
  respecter_nb_classes = FALSE
)
stopifnot(identical(resultat_sans_cible$mincl, 58L))

# En cas d'arrêt anticipé de la CHD, une cible de 10 classes
# continue de produire 58, même si seules 8 divisions sont présentes.
arbre_court <- arbre
arbre_court$n1 <- arbre$n1[, seq_len(8L), drop = FALSE]
resultat_court <- reconstruire_classes_terminales_iramuteq(
  chd_obj = arbre_court,
  mincl_mode = "auto",
  classif_mode = "simple",
  nb_classes_cible = 10L,
  respecter_nb_classes = FALSE
)
stopifnot(identical(resultat_court$mincl, 58L))

resultat_double <- reconstruire_classes_terminales_iramuteq(
  chd_obj = arbre,
  mincl_mode = "auto",
  classif_mode = "double",
  nb_classes_cible = 10L,
  respecter_nb_classes = FALSE
)
stopifnot(identical(resultat_double$mincl, 29L))

# L'option manuelle doit conserver la valeur indiquée par l'utilisateur.
resultat_manuel <- reconstruire_classes_terminales_iramuteq(
  chd_obj = arbre,
  mincl = 5L,
  mincl_mode = "manuel",
  classif_mode = "simple",
  nb_classes_cible = 10L,
  respecter_nb_classes = FALSE
)
stopifnot(identical(resultat_manuel$mincl, 5L))

# Vérifier aussi le passage réel de k depuis le moteur en mode Normal.
`%||%` <- function(x, y) if (is.null(x) || !length(x)) y else x
source(file.path("iramuteqlite", "chd_engine_iramuteq.R"))
.obtenir_fonction_iramuteq <- function(nom_fonction, ...) {
  if (identical(nom_fonction, "calculer_chd_iramuteq")) {
    return(function(...) arbre_court)
  }
  if (identical(nom_fonction, "reconstruire_classes_terminales_iramuteq")) {
    return(reconstruire_classes_terminales_iramuteq)
  }
  stop("Fonction simulée inattendue : ", nom_fonction)
}

resultat_moteur <- lancer_moteur_chd_iramuteq(
  dfm_obj = matrix(1L, nrow = 2L, ncol = 2L),
  k = 10L,
  classes_mode = "manuel",
  mincl_mode = "auto",
  classif_mode = "simple",
  svd_method = "svdR"
)
stopifnot(identical(resultat_moteur$mincl, 58L))

cat("Test mincl automatique CHD : 576 / 10 = 58, classe 0 exclue.\n")
