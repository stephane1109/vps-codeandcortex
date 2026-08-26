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
  classes_mode = c("manuel", "auto"),
  mincl_mode = c("auto", "manuel"),
  mincl = 0,
  classif_mode = c("simple", "double"),
  svd_method = c("irlba", "svdR"),
  mode_patate = FALSE,
  libsvdc_path = NULL,
  binariser = FALSE,
  rscripts_dir = NULL,
  max_formes = 20000L,
  auto_stats_mode = c("vectorise", "classique"),
  auto_top_n_diffusion = 20L,
  auto_p_seuil = 0.05
) {
  classes_mode <- match.arg(classes_mode)
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  svd_method <- match.arg(svd_method)
  auto_stats_mode <- match.arg(auto_stats_mode)

  calculer_chd_iramuteq_fn <- .obtenir_fonction_iramuteq("calculer_chd_iramuteq", env = environment())
  reconstruire_classes_terminales_iramuteq_fn <- .obtenir_fonction_iramuteq("reconstruire_classes_terminales_iramuteq", env = environment())
  selection_automatique_classes_iramuteq_fn <- NULL
  resoudre_borne_chd_auto_iramuteq_fn <- NULL
  if (identical(classes_mode, "auto")) {
    resoudre_borne_chd_auto_iramuteq_fn <- .obtenir_fonction_iramuteq(
      "resoudre_borne_chd_auto_iramuteq",
      chemin_module = "iramuteqlite/autoCHD.R",
      env = environment()
    )
    selection_automatique_classes_iramuteq_fn <- .obtenir_fonction_iramuteq(
      "selection_automatique_classes_iramuteq",
      chemin_module = "iramuteqlite/autoCHD.R",
      env = environment()
    )
  }

  chd_obj <- if (identical(classes_mode, "auto")) {
    resoudre_borne_chd_auto_iramuteq_fn(
      calculer_chd_fn = calculer_chd_iramuteq_fn,
      dfm_obj = dfm_obj,
      k_max = k,
      mode_patate = mode_patate,
      svd_method = svd_method,
      libsvdc_path = libsvdc_path,
      binariser = binariser,
      rscripts_dir = rscripts_dir,
      max_formes = max_formes
    )
  } else {
    calculer_chd_iramuteq_fn(
      dfm_obj = dfm_obj,
      k = k,
      mode_patate = mode_patate,
      svd_method = svd_method,
      libsvdc_path = libsvdc_path,
      binariser = binariser,
      rscripts_dir = rscripts_dir,
      max_formes = max_formes
    )
  }

  dfm_utilise <- if (!is.null(chd_obj$dfm_utilise)) chd_obj$dfm_utilise else dfm_obj
  auto_selection <- NULL
  fallback_mincl1 <- FALSE

  if (identical(classes_mode, "auto")) {
    auto_selection <- selection_automatique_classes_iramuteq_fn(
      chd_obj = chd_obj,
      dfm_obj = dfm_utilise,
      k_max = k,
      stats_mode = auto_stats_mode,
      top_n_diffusion = auto_top_n_diffusion,
      p_seuil = auto_p_seuil
    )

    classes <- suppressWarnings(as.integer(auto_selection$classes))
    classes_valides <- unique(classes[is.finite(classes) & classes > 0L])
    if (length(classes_valides) < 2L) {
      stop("IRaMuTeQ-lite Auto CHD n'a pas pu retenir au moins 2 classes exploitables.")
    }

    return(list(
      engine = "iramuteq-lite",
      chd = chd_obj,
      classes_mode = classes_mode,
      classes = auto_selection$classes,
      terminales = auto_selection$terminales,
      mincl = NA_integer_,
      fallback_mincl1 = FALSE,
      auto_selection = auto_selection,
      dfm_utilise = dfm_utilise,
      max_formes_info = chd_obj$max_formes_info
    ))
  }

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
    classes_mode = classes_mode,
    classes = classes_obj$classes,
    terminales = classes_obj$terminales,
    mincl = classes_obj$mincl,
    fallback_mincl1 = fallback_mincl1,
    auto_selection = NULL,
    dfm_utilise = dfm_utilise,
    max_formes_info = chd_obj$max_formes_info
  )
}
