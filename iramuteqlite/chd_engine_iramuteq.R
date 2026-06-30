# Rôle du fichier: chd_engine_iramuteq.R encapsule le lancement du moteur CHD IRaMuTeQ-like.
# Ce module sert de point d'entrée dédié pour exécuter la CHD historique et reconstruire
# les classes terminales avec mincl (auto ou manuel).

.obtenir_fonction_iramuteq <- function(nom_fonction,
                                       chemin_module = "iramuteqlite/chd_iramuteq.R",
                                       env = parent.frame()) {
  fn <- get0(nom_fonction, mode = "function", inherits = TRUE)
  if (!is.null(fn)) return(fn)

  # Répertoire du projet (quand l'app est lancée hors du dossier racine).
  racine_projet <- tryCatch({
    if (requireNamespace("shiny", quietly = TRUE)) {
      shiny::getShinyOption("appDir")
    } else {
      NULL
    }
  }, error = function(...) NULL)

  # Répertoire courant du fichier R/chd_engine_iramuteq.R, si disponible.
  fichier_courant <- tryCatch({
    frames <- rev(sys.frames())
    ofiles <- vapply(
      frames,
      function(fr) {
        of <- get0("ofile", envir = fr, inherits = FALSE)
        if (is.null(of)) "" else as.character(of)
      },
      FUN.VALUE = character(1)
    )
    ofiles <- ofiles[nzchar(ofiles)]
    if (length(ofiles)) ofiles[[1]] else ""
  }, error = function(...) "")
  dir_fichier_courant <- if (nzchar(fichier_courant)) dirname(normalizePath(fichier_courant, mustWork = FALSE)) else ""
  racine_depuis_fichier <- if (nzchar(dir_fichier_courant)) normalizePath(file.path(dir_fichier_courant, ".."), mustWork = FALSE) else ""

  candidats <- unique(c(
    chemin_module,
    file.path("iramuteqlite", "chd_iramuteq.R"),
    file.path("iramuteqlite", "chd_iramuteq_like.R"),
    if (nzchar(racine_depuis_fichier)) file.path(racine_depuis_fichier, "iramuteqlite", "chd_iramuteq_compat.R") else "",
    if (nzchar(racine_depuis_fichier)) file.path(racine_depuis_fichier, "iramuteqlite", "chd_iramuteq.R") else "",
    if (nzchar(racine_depuis_fichier)) file.path(racine_depuis_fichier, "iramuteqlite", "chd_iramuteq.R") else "",
    if (!is.null(racine_projet) && nzchar(racine_projet)) file.path(racine_projet, "iramuteqlite", "chd_iramuteq_compat.R") else "",
    if (!is.null(racine_projet) && nzchar(racine_projet)) file.path(racine_projet, "iramuteqlite", "chd_iramuteq.R") else "",
    if (!is.null(racine_projet) && nzchar(racine_projet)) file.path(racine_projet, "iramuteqlite", "chd_iramuteq.R") else "",
    file.path(".", "iramuteqlite", "chd_iramuteq_compat.R"),
    file.path(".", "iramuteqlite", "chd_iramuteq.R"),
    file.path(".", "iramuteqlite", "chd_iramuteq.R"),
    file.path(getwd(), "iramuteqlite", "chd_iramuteq_compat.R"),
    file.path(getwd(), "iramuteqlite", "chd_iramuteq.R"),
    file.path(getwd(), "iramuteqlite", "chd_iramuteq.R")
  ))
  candidats <- candidats[!is.na(candidats) & nzchar(candidats)]

  for (cand in candidats) {
    if (file.exists(cand)) {
      source(cand, local = env)
      fn <- get0(nom_fonction, mode = "function", inherits = TRUE)
      if (!is.null(fn)) return(fn)
    }
  }

  stop(
    "Moteur CHD IRaMuTeQ-like indisponible: ", nom_fonction,
    "() introuvable. Module recherché dans: ",
    paste(candidats, collapse = ", "),
    "."
  )
}

lancer_moteur_chd_iramuteq <- function(
  dfm_obj,
  k,
  mincl_mode = c("auto", "manuel"),
  mincl = 0,
  classif_mode = c("simple", "double"),
  svd_method = c("irlba", "svdR"),
  mode_patate = FALSE,
  libsvdc_path = NULL,
  binariser = FALSE,
  rscripts_dir = NULL,
  max_formes = 20000L
) {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  svd_method <- match.arg(svd_method)

  calculer_chd_iramuteq_fn <- .obtenir_fonction_iramuteq("calculer_chd_iramuteq", env = environment())
  reconstruire_classes_terminales_iramuteq_fn <- .obtenir_fonction_iramuteq("reconstruire_classes_terminales_iramuteq", env = environment())

  chd_obj <- calculer_chd_iramuteq_fn(
    dfm_obj = dfm_obj,
    k = k,
    mode_patate = mode_patate,
    svd_method = svd_method,
    libsvdc_path = libsvdc_path,
    binariser = binariser,
    rscripts_dir = rscripts_dir,
    max_formes = max_formes
  )

  classes_obj <- reconstruire_classes_terminales_iramuteq_fn(
    chd_obj = chd_obj,
    mincl = mincl,
    mincl_mode = mincl_mode,
    classif_mode = classif_mode,
    nb_classes_cible = NULL,
    respecter_nb_classes = FALSE
  )

  classes <- suppressWarnings(as.integer(classes_obj$classes))
  classes_valides <- unique(classes[is.finite(classes) & classes > 0L])
  fallback_mincl1 <- FALSE

  # Garde-fou: sur certains corpus, le mincl auto peut fusionner excessivement
  # les feuilles terminales et ne laisser qu'une seule classe exploitable.
  # On retente alors une reconstruction avec mincl = 1 pour conserver les
  # classes terminales sans relancer la CHD complète.
  if (length(classes_valides) < 2L) {
    classes_obj_alt <- reconstruire_classes_terminales_iramuteq_fn(
      chd_obj = chd_obj,
      mincl = 1L,
      mincl_mode = "manuel",
      classif_mode = classif_mode,
      nb_classes_cible = NULL,
      respecter_nb_classes = FALSE
    )

    classes_alt <- suppressWarnings(as.integer(classes_obj_alt$classes))
    classes_alt_valides <- unique(classes_alt[is.finite(classes_alt) & classes_alt > 0L])

    if (length(classes_alt_valides) >= 2L) {
      classes_obj <- classes_obj_alt
      fallback_mincl1 <- TRUE
    }
  }

  list(
    engine = "iramuteq-lite",
    chd = chd_obj,
    classes = classes_obj$classes,
    terminales = classes_obj$terminales,
    mincl = classes_obj$mincl,
    fallback_mincl1 = fallback_mincl1,
    dfm_utilise = chd_obj$dfm_utilise,
    max_formes_info = chd_obj$max_formes_info
  )
}
