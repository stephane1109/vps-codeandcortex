# Rôle du fichier: chd_iramuteq.R introduit une base "IRaMuTeQ-lite" pour la CHD.
# Ce module prépare les entrées de CHD en respectant les options de nettoyage de l'application,
# expose des utilitaires pour le calcul de mincl (convention IRaMuTeQ texte),
# et fournit un calcul CHD réel en s'appuyant sur les scripts R historiques d'IRaMuTeQ.

# Valeur mincl automatique (mode texte IRaMuTeQ):
# mincl = round(n_uce / ind), avec ind = nbcl * 2 (double) sinon nbcl.

calculer_mincl_auto_iramuteq <- function(n_uce, nbcl, classif_mode = c("double", "simple")) {
  classif_mode <- match.arg(classif_mode)
  n_uce <- as.integer(n_uce)
  nbcl <- as.integer(nbcl)
  
  if (!is.finite(n_uce) || is.na(n_uce) || n_uce < 1) {
    stop("mincl auto IRaMuTeQ: n_uce invalide.")
  }
  if (!is.finite(nbcl) || is.na(nbcl) || nbcl < 1) {
    stop("mincl auto IRaMuTeQ: nbcl invalide.")
  }
  
  ind <- if (identical(classif_mode, "double")) nbcl * 2L else nbcl
  mincl <- round(n_uce / ind)
  as.integer(max(1L, mincl))
}

# Normalise une liste d'options de nettoyage selon les clés utilisées dans l'UI.
normaliser_options_nettoyage_iramuteq <- function(options_nettoyage = list()) {
  opts <- list(
    nettoyage_caracteres = isTRUE(options_nettoyage$nettoyage_caracteres),
    forcer_minuscules_avant = TRUE,
    supprimer_chiffres = isTRUE(options_nettoyage$supprimer_chiffres),
    supprimer_apostrophes = isTRUE(options_nettoyage$supprimer_apostrophes),
    remplacer_tirets_espaces = isTRUE(options_nettoyage$remplacer_tirets_espaces),
    supprimer_ponctuation = isTRUE(options_nettoyage$supprimer_ponctuation),
    retirer_stopwords = isTRUE(options_nettoyage$retirer_stopwords)
  )
  opts
}

# Prépare textes/tokens/dfm en tenant compte des options de nettoyage existantes de l'application.
preparer_entrees_chd_iramuteq <- function(
    textes,
    langue = "fr",
    options_nettoyage = list(),
    appliquer_nettoyage_fun = NULL
) {
  if (!is.character(textes)) {
    textes <- as.character(textes)
  }
  textes[is.na(textes)] <- ""
  
  opts <- normaliser_options_nettoyage_iramuteq(options_nettoyage)
  
  if (is.null(appliquer_nettoyage_fun)) {
    if (exists("appliquer_nettoyage_et_minuscules", mode = "function", inherits = TRUE)) {
      appliquer_nettoyage_fun <- get("appliquer_nettoyage_et_minuscules", mode = "function", inherits = TRUE)
    } else {
      appliquer_nettoyage_fun <- function(textes,
                                          activer_nettoyage = FALSE,
                                          forcer_minuscules = FALSE,
                                          supprimer_chiffres = FALSE,
                                          supprimer_apostrophes = FALSE,
                                          remplacer_tirets_espaces = FALSE) {
        x <- as.character(textes)
        if (isTRUE(forcer_minuscules)) x <- tolower(x)
        x
      }
    }
  }
  
  textes_prep <- appliquer_nettoyage_fun(
    textes = textes,
    activer_nettoyage = opts$nettoyage_caracteres,
    forcer_minuscules = TRUE,
    supprimer_chiffres = opts$supprimer_chiffres,
    supprimer_apostrophes = opts$supprimer_apostrophes,
    remplacer_tirets_espaces = opts$remplacer_tirets_espaces
  )
  
  if (!requireNamespace("quanteda", quietly = TRUE)) {
    stop("CHD IRaMuTeQ-like: package quanteda requis pour préparer les entrées.")
  }
  
  tok <- quanteda::tokens(
    textes_prep,
    remove_punct = opts$supprimer_ponctuation,
    remove_numbers = opts$supprimer_chiffres
  )
  
  if (opts$retirer_stopwords) {
    sw <- quanteda::stopwords(language = langue)
    tok <- quanteda::tokens_remove(tok, pattern = sw)
  }
  
  dfm_obj <- quanteda::dfm(tok)
  # CHD : contrairement à l'AFC classes × termes, il n'y a pas ici de plafond
  # global type "top 400". Le vocabulaire est conservé selon les filtres amont
  # (nettoyage, stopwords éventuels, puis min_docfreq appliqué ailleurs dans le pipeline).
  # NB: la p-value n'intervient pas dans l'algorithme de partition CHD historique;
  # elle est calculée ensuite dans les statistiques classe × terme pour filtrage/affichage.
  list(textes = textes_prep, tok = tok, dfm = dfm_obj, options = opts)
}

.trouver_fichier_insensible_casse <- function(dir_path, filename) {
  if (!dir.exists(dir_path)) return(NA_character_)
  files <- list.files(dir_path, full.names = TRUE)
  if (length(files) == 0) return(NA_character_)
  bn <- basename(files)
  idx <- which(tolower(bn) == tolower(filename))
  if (length(idx) == 0) return(NA_character_)
  files[idx[1]]
}

.trouver_rscripts_iramuteq <- function(base_dir = NULL) {
  scripts <- c("anacor.R", "CHD.R", "chdtxt.R")
  candidats_bruts <- unique(c(
    base_dir,
    "iramuteqlite",
    file.path(getwd(), "iramuteqlite")
  ))
  candidats <- candidats_bruts[
    !is.na(candidats_bruts) &
      nzchar(candidats_bruts) &
      dir.exists(candidats_bruts)
  ]
  
  for (cand in candidats) {
    paths <- vapply(scripts, function(sc) .trouver_fichier_insensible_casse(cand, sc), FUN.VALUE = character(1))
    if (all(!is.na(paths))) {
      return(unname(paths))
    }
  }
  
  stop(
    "CHD IRaMuTeQ-like: scripts R introuvables. Répertoires testés: ",
    if (length(candidats)) paste(candidats, collapse = ", ") else "(aucun répertoire existant)",
    ". Fichiers attendus: ",
    paste(scripts, collapse = ", "),
    "."
  )
}

.charger_scripts_iramuteq_chd <- function(base_dir = NULL) {
  paths <- .trouver_rscripts_iramuteq(base_dir)
  for (p in paths) {
    source(p, local = .GlobalEnv)
  }
  invisible(paths)
}

.normaliser_n1_chd <- function(n1) {
  if (is.null(n1)) return(NULL)
  if (is.data.frame(n1)) n1 <- as.matrix(n1)
  if (is.vector(n1)) {
    n1 <- matrix(as.integer(n1), ncol = 1)
  }
  if (!is.matrix(n1)) return(NULL)
  if (nrow(n1) < 1 || ncol(n1) < 1) return(NULL)
  n1
}

# Calcul CHD IRaMuTeQ-like (algorithme historique via scripts R IRaMuTeQ).
calculer_chd_iramuteq <- function(
    dfm_obj,
    k = 3,
    mode_patate = FALSE,
    svd_method = c("irlba", "svdR"),
    libsvdc_path = NULL,
    binariser = FALSE,
    rscripts_dir = NULL,
    max_formes = 20000L
) {
  svd_method <- match.arg(svd_method)
  
  if (is.null(dfm_obj)) stop("CHD IRaMuTeQ-like: dfm_obj manquant.")
  if (!is.finite(k) || is.na(k) || as.integer(k) < 2) stop("CHD IRaMuTeQ-like: k doit être >= 2.")
  
  .charger_scripts_iramuteq_chd(rscripts_dir)
  
  max_formes_use <- suppressWarnings(as.integer(max_formes))
  if (is.na(max_formes_use) || max_formes_use < 1L) max_formes_use <- 20000L
  
  n_feat_avant_max <- quanteda::nfeat(dfm_obj)
  dfm_utilise <- dfm_obj
  if (n_feat_avant_max > max_formes_use) {
    freq_globales <- Matrix::colSums(dfm_obj)
    idx_top <- order(freq_globales, decreasing = TRUE)[seq_len(max_formes_use)]
    formes_top <- names(freq_globales)[idx_top]
    dfm_utilise <- quanteda::dfm_select(
      dfm_obj,
      pattern = formes_top,
      selection = "keep",
      valuetype = "fixed",
      case_insensitive = FALSE
    )
  }
  
  mat <- as.matrix(dfm_utilise)
  if (nrow(mat) < 2 || ncol(mat) < 2) {
    stop("CHD IRaMuTeQ-like: matrice trop pauvre (>=2 lignes et >=2 colonnes requises).")
  }
  
  if (isTRUE(binariser)) {
    mat <- ifelse(mat > 0, 1, 0)
  }
  
  rownames(mat) <- as.character(seq_len(nrow(mat)))
  
  nb_tours <- as.integer(k) - 1L
  if (nb_tours < 1) nb_tours <- 1L
  
  # Le moteur CHD historique écrit de nombreux print() et peut ouvrir un device
  # graphique implicite (Rplots.pdf) dans certains environnements headless.
  # On encapsule l'appel pour:
  # 1) rediriger stdout/stderr vers des fichiers temporaires,
  # 2) forcer un device temporaire inscriptible,
  # 3) supprimer ce PDF temporaire en sortie.
  chd <- local({
    log_out <- tempfile("chd_stdout_", fileext = ".log")
    log_msg <- tempfile("chd_messages_", fileext = ".log")
    pdf_tmp <- tempfile("chd_plot_", fileext = ".pdf")
    
    con_out <- file(log_out, open = "wt")
    con_msg <- file(log_msg, open = "wt")
    
    n_out_before <- sink.number(type = "output")
    n_msg_before <- sink.number(type = "message")
    
    sink(con_out, type = "output")
    sink(con_msg, type = "message")
    grDevices::pdf(pdf_tmp)
    
    on.exit({
      while (sink.number(type = "message") > n_msg_before) sink(type = "message")
      while (sink.number(type = "output") > n_out_before) sink(type = "output")
      try(grDevices::dev.off(), silent = TRUE)
      try(close(con_out), silent = TRUE)
      try(close(con_msg), silent = TRUE)
      try(unlink(c(pdf_tmp, log_out, log_msg), force = TRUE), silent = TRUE)
    }, add = TRUE)
    
    suppressWarnings(
      CHD(
        data.in = mat,
        x = nb_tours,
        mode.patate = isTRUE(mode_patate),
        svd.method = svd_method,
        libsvdc.path = libsvdc_path
      )
    )
  })
  
  n1 <- .normaliser_n1_chd(chd$n1)
  if (is.null(n1) || nrow(n1) != nrow(mat)) {
    stop("CHD IRaMuTeQ-like: sortie CHD invalide.")
  }
  
  chd$n1 <- n1
  chd$dfm_utilise <- dfm_utilise
  chd$max_formes_info <- list(
    max_formes = max_formes_use,
    n_feat_avant = n_feat_avant_max,
    n_feat_apres = quanteda::nfeat(dfm_utilise)
  )
  
  chd
}

# Reconstitue des classes finales depuis la sortie CHD et le principe find.terminales.
reconstruire_classes_terminales_iramuteq <- function(
    chd_obj,
    mincl = 0,
    mincl_mode = c("auto", "manuel"),
    classif_mode = c("simple", "double"),
    nb_classes_cible = NULL,
    respecter_nb_classes = TRUE
) {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  
  n1 <- .normaliser_n1_chd(chd_obj$n1)
  list_mere <- chd_obj$list_mere
  list_fille <- chd_obj$list_fille
  
  if (is.null(n1) || is.null(list_mere) || is.null(list_fille)) {
    stop("CHD IRaMuTeQ-like: objet chd incomplet.")
  }
  
  nbcl <- length(unique(n1[, ncol(n1)]))
  nbcl <- max(2L, as.integer(nbcl))
  
  if (mincl_mode == "auto") {
    mincl_use <- calculer_mincl_auto_iramuteq(
      n_uce = nrow(n1),
      nbcl = nbcl,
      classif_mode = classif_mode
    )
  } else {
    mincl_use <- as.integer(mincl)
    if (!is.finite(mincl_use) || is.na(mincl_use) || mincl_use < 1) mincl_use <- 1L
  }
  
  terminales <- find.terminales(n1, list_mere, list_fille, mincl = mincl_use)
  if (is.character(terminales) && length(terminales) == 1 && terminales == "no clusters") {
    stop("CHD IRaMuTeQ-like: aucune classe terminale retenue.")
  }
  
  feuilles <- unique(as.integer(n1[, ncol(n1)]))
  
  if (isTRUE(respecter_nb_classes) && !is.null(nb_classes_cible) && is.finite(nb_classes_cible)) {
    nb_classes_cible <- as.integer(nb_classes_cible)
    if (nb_classes_cible >= 2 && length(feuilles) == nb_classes_cible && length(unique(terminales)) != nb_classes_cible) {
      terminales <- sort(feuilles)
      mincl_use <- 1L
    }
  }
  
  classes_finales <- rep(0L, nrow(n1))
  feuilles_docs <- suppressWarnings(as.integer(n1[, ncol(n1)]))
  
  # Reproduction fidèle de iramuteq_clone_v3/Rscripts/chdtxt.R::make.classes
  # (sans la partie manipulation du tree, non nécessaire au calcul des classes docs).
  cl_names <- seq_along(terminales)
  for (i in seq_along(terminales)) {
    cl <- suppressWarnings(as.integer(terminales[[i]]))
    if (!is.finite(cl)) next
    
    if (cl %in% feuilles) {
      classes_finales[which(feuilles_docs == cl)] <- cl_names[[i]]
    } else {
      filles <- suppressWarnings(as.integer(getfille(list_fille, cl, NULL)))
      tochange <- intersect(filles, feuilles)
      for (cl_fille in tochange) {
        classes_finales[which(feuilles_docs == cl_fille)] <- cl_names[[i]]
      }
    }
  }
  
  classes_finales[which(is.na(classes_finales))] <- 0L
  list(
    classes = classes_finales,
    terminales = as.integer(terminales),
    mincl = mincl_use
  )
}

# Calcule une table de statistiques par classe dans l'esprit des sorties IRaMuTeQ.
construire_stats_classes_iramuteq <- function(dfm_obj, classes, max_p = 1, stats_mode = c("vectorise", "classique")) {
  if (is.null(dfm_obj)) stop("Stats IRaMuTeQ-like: dfm_obj manquant.")
  if (is.null(classes)) stop("Stats IRaMuTeQ-like: classes manquantes.")
  
  if (exists("normaliser_mode_stats_chd_iramuteq", mode = "function", inherits = TRUE)) {
    stats_mode <- normaliser_mode_stats_chd_iramuteq(stats_mode)
  } else {
    stats_mode <- match.arg(stats_mode)
  }
  
  mat <- tryCatch(
    methods::as(dfm_obj, "dgCMatrix"),
    error = function(e) as(as.matrix(dfm_obj), "matrix")
  )
  if (nrow(mat) != length(classes)) {
    stop("Stats IRaMuTeQ-like: longueur de classes incohérente avec le DFM.")
  }
  
  classes <- as.integer(classes)
  ok_docs <- !is.na(classes) & classes > 0L
  mat <- mat[ok_docs, , drop = FALSE]
  classes <- classes[ok_docs]
  
  if (nrow(mat) < 2 || ncol(mat) < 1) return(data.frame())
  
  if (inherits(mat, "dgCMatrix")) {
    mat_bin <- mat
    if (length(mat_bin@x) > 0) mat_bin@x[] <- 1
    col_sums <- Matrix::colSums
    row_sums <- Matrix::rowSums
  } else {
    mat_bin <- ifelse(mat > 0, 1L, 0L)
    col_sums <- base::colSums
    row_sums <- base::rowSums
  }
  
  docs_par_terme <- col_sums(mat_bin)
  occ_par_terme <- col_sums(mat)
  occ_par_doc <- row_sums(mat)
  
  occ_par_classe <- tapply(as.numeric(occ_par_doc), classes, sum)
  occ_totales <- sum(occ_par_terme)
  
  calc_chi_sign_vectorise <- function(a, b, c, d) {
    n <- a + b + c + d
    denom <- (a + b) * (c + d) * (a + c) * (b + d)
    
    chi_abs <- rep(0, length(a))
    idx_ok <- is.finite(denom) & denom > 0 & is.finite(n) & n > 0
    if (any(idx_ok)) {
      chi_abs[idx_ok] <- (n[idx_ok] * ((a[idx_ok] * d[idx_ok] - b[idx_ok] * c[idx_ok])^2)) / denom[idx_ok]
    }
    chi_abs[!is.finite(chi_abs) | is.na(chi_abs)] <- 0
    
    exp11 <- rep(0, length(a))
    idx_exp <- is.finite(n) & n > 0
    if (any(idx_exp)) {
      exp11[idx_exp] <- ((a[idx_exp] + b[idx_exp]) * (a[idx_exp] + c[idx_exp])) / n[idx_exp]
    }
    exp11[!is.finite(exp11) | is.na(exp11)] <- 0
    
    signe <- ifelse(a >= exp11, 1, -1)
    chi_sign <- chi_abs * signe
    pval <- stats::pchisq(chi_abs, df = 1, lower.tail = FALSE)
    pval[!is.finite(pval) | is.na(pval)] <- 1
    
    list(chi2 = chi_sign, p = pval)
  }
  
  calc_chi_sign_classique <- function(a, b, c, d) {
    chi_mat <- mapply(function(ai, bi, ci, di) {
      tb <- matrix(c(ai, bi, ci, di), nrow = 2, byrow = TRUE)
      chi <- suppressWarnings(stats::chisq.test(tb, correct = FALSE))
      stat <- suppressWarnings(as.numeric(chi$statistic))
      pval <- suppressWarnings(as.numeric(chi$p.value))
      exp11 <- suppressWarnings(as.numeric(chi$expected[1, 1]))
      
      if (!is.finite(stat) || is.na(stat)) stat <- 0
      if (!is.finite(pval) || is.na(pval)) pval <- 1
      if (!is.finite(exp11) || is.na(exp11)) exp11 <- ai
      
      signe <- ifelse(ai >= exp11, 1, -1)
      c(chi2 = stat * signe, p = pval)
    }, a, b, c, d)
    
    list(
      chi2 = as.numeric(chi_mat["chi2", ]),
      p = as.numeric(chi_mat["p", ])
    )
  }
  
  calc_lr_vectorise <- function(a, b, c, d) {
    n <- a + b + c + d
    r1 <- a + b
    r2 <- c + d
    c1 <- a + c
    c2 <- b + d
    
    expected11 <- ifelse(n > 0, r1 * c1 / n, 0)
    expected12 <- ifelse(n > 0, r1 * c2 / n, 0)
    expected21 <- ifelse(n > 0, r2 * c1 / n, 0)
    expected22 <- ifelse(n > 0, r2 * c2 / n, 0)
    
    lr <- rep(0, length(a))
    
    idx11 <- a > 0 & expected11 > 0
    if (any(idx11)) lr[idx11] <- lr[idx11] + a[idx11] * log(a[idx11] / expected11[idx11])
    
    idx12 <- b > 0 & expected12 > 0
    if (any(idx12)) lr[idx12] <- lr[idx12] + b[idx12] * log(b[idx12] / expected12[idx12])
    
    idx21 <- c > 0 & expected21 > 0
    if (any(idx21)) lr[idx21] <- lr[idx21] + c[idx21] * log(c[idx21] / expected21[idx21])
    
    idx22 <- d > 0 & expected22 > 0
    if (any(idx22)) lr[idx22] <- lr[idx22] + d[idx22] * log(d[idx22] / expected22[idx22])
    
    lr <- 2 * lr
    lr[!is.finite(lr) | is.na(lr)] <- 0
    lr
  }
  
  classes_uniques <- sort(unique(classes))
  sorties <- vector("list", length(classes_uniques))
  
  for (i in seq_along(classes_uniques)) {
    cl <- classes_uniques[[i]]
    in_cl <- classes == cl
    
    docs_cl <- sum(in_cl)
    if (docs_cl < 1) next
    
    docs_terme_cl <- col_sums(mat_bin[in_cl, , drop = FALSE])
    docs_terme_hors <- pmax(0, docs_par_terme - docs_terme_cl)
    
    occ_terme_cl <- col_sums(mat[in_cl, , drop = FALSE])
    occ_terme_hors <- pmax(0, occ_par_terme - occ_terme_cl)
    occ_classe <- as.numeric(occ_par_classe[as.character(cl)])
    occ_hors_classe <- pmax(0, occ_totales - occ_classe)
    
    n11 <- as.numeric(occ_terme_cl)
    n12 <- as.numeric(occ_terme_hors)
    n21 <- as.numeric(pmax(0, occ_classe - occ_terme_cl))
    n22 <- as.numeric(pmax(0, occ_hors_classe - occ_terme_hors))
    
    if (identical(stats_mode, "classique")) {
      chi_p <- calc_chi_sign_classique(n11, n12, n21, n22)
    } else {
      chi_p <- calc_chi_sign_vectorise(n11, n12, n21, n22)
    }
    
    freq_cl <- occ_terme_cl
    docprop_cl <- if (docs_cl > 0) docs_terme_cl / docs_cl else rep(0, ncol(mat))
    lr <- calc_lr_vectorise(n11, n12, n21, n22)
    
    df <- data.frame(
      Terme = colnames(mat),
      chi2 = as.numeric(chi_p$chi2),
      lr = as.numeric(lr),
      frequency = as.numeric(freq_cl),
      docprop = as.numeric(docprop_cl),
      # Alignement IRaMuTeQ: "eff. s.t." / "eff. total" sont des effectifs
      # documentaires (nombre de segments contenant le terme), pas des occurrences.
      eff_st = as.numeric(docs_terme_cl),
      eff_total = as.numeric(docs_par_terme),
      pourcentage = as.numeric(ifelse(docs_par_terme > 0, 100 * docs_terme_cl / docs_par_terme, 0)),
      eff_docs_st = as.numeric(docs_terme_cl),
      eff_docs_total = as.numeric(docs_par_terme),
      occ_st = as.numeric(freq_cl),
      occ_total = as.numeric(occ_par_terme),
      p = as.numeric(chi_p$p),
      Classe = as.integer(cl),
      stringsAsFactors = FALSE
    )
    
    df <- df[is.finite(df$chi2) & !is.na(df$chi2), , drop = FALSE]
    # Filtrage p-value appliqué aux sorties statistiques uniquement (post-CHD).
    if (is.finite(max_p) && !is.na(max_p) && max_p < 1) {
      df <- df[df$p <= max_p, , drop = FALSE]
    }
    df <- df[order(-df$chi2, -df$frequency, -occ_par_terme[df$Terme]), , drop = FALSE]
    sorties[[i]] <- df
  }
  
  out <- dplyr::bind_rows(sorties)
  if (!nrow(out)) return(out)
  
  out$Classe_brut <- as.character(out$Classe)
  out$p_value <- out$p
  out$p_value_filter <- ifelse(out$p <= max_p, paste0("≤ ", max_p), paste0("> ", max_p))
  out
}

# Dendrogramme CHD basé sur la structure hiérarchique IRaMuTeQ (list_mere/list_fille).
tracer_dendrogramme_chd_iramuteq <- function(chd_obj,
                                             terminales = NULL,
                                             classes = NULL,
                                             res_stats_df = NULL,
                                             top_n_terms = 4,
                                             orientation = c("vertical", "horizontal"),
                                             style_affichage = c("iramuteq_bars", "factoextra"),
                                             edge_style = c("diagonal", "orthogonal"),
                                             edge_lwd = 1.6) {
  orientation <- match.arg(orientation)
  style_affichage <- match.arg(style_affichage)
  edge_style <- match.arg(edge_style)
  edge_lwd <- suppressWarnings(as.numeric(edge_lwd))
  if (!is.finite(edge_lwd) || is.na(edge_lwd) || edge_lwd <= 0) edge_lwd <- 1.6
  
  .tracer_dendrogramme_hclust <- function(res_stats_df, classes, top_n_terms, orientation, style_affichage = "iramuteq_bars") {
    if (is.null(res_stats_df) || !is.data.frame(res_stats_df)) return(FALSE)
    if (!all(c("Classe", "Terme") %in% names(res_stats_df))) return(FALSE)
    
    df <- res_stats_df
    df$Classe <- suppressWarnings(as.integer(df$Classe))
    df$Terme <- as.character(df$Terme)
    df <- df[is.finite(df$Classe) & df$Classe > 0 & nzchar(df$Terme), , drop = FALSE]
    if (!nrow(df)) return(FALSE)
    
    poids <- if ("frequency" %in% names(df)) suppressWarnings(as.numeric(df$frequency)) else rep(1, nrow(df))
    poids[!is.finite(poids) | is.na(poids) | poids < 0] <- 0
    df$poids <- poids
    
    mat <- stats::xtabs(poids ~ Classe + Terme, data = df)
    if (nrow(mat) < 2 || ncol(mat) < 2) return(FALSE)
    
    # Colonnes constantes retirées pour stabiliser dist/hclust.
    vars <- apply(mat, 2, stats::sd)
    vars[!is.finite(vars)] <- 0
    mat <- mat[, vars > 0, drop = FALSE]
    if (nrow(mat) < 2 || ncol(mat) < 2) return(FALSE)
    
    dist_obj <- stats::dist(mat, method = "euclidean")
    if (!inherits(dist_obj, "dist") || length(dist_obj) == 0) return(FALSE)
    
    hc <- stats::hclust(dist_obj, method = "ward.D2")
    clusternb <- nrow(mat)
    if (!is.finite(clusternb) || clusternb < 2) return(FALSE)
    
    # Libellés des feuilles: "Classe X (Y %)" quand les proportions sont disponibles.
    labels_classes <- rownames(mat)
    if (is.null(labels_classes) || !length(labels_classes)) labels_classes <- as.character(seq_len(clusternb))
    ids_cl <- suppressWarnings(as.integer(labels_classes))
    pct_par_classe <- NULL
    if (!is.null(classes)) {
      classes_int <- suppressWarnings(as.integer(classes))
      classes_int <- classes_int[is.finite(classes_int) & classes_int > 0]
      if (length(classes_int)) pct_par_classe <- prop.table(table(classes_int)) * 100
    }
    labels_txt <- vapply(seq_along(labels_classes), function(i) {
      cl_id <- ids_cl[[i]]
      if (!is.finite(cl_id)) return(paste0("Classe ", labels_classes[[i]]))
      pct <- if (!is.null(pct_par_classe)) suppressWarnings(as.numeric(pct_par_classe[[as.character(cl_id)]])) else NA_real_
      if (is.finite(pct)) {
        paste0("Classe ", cl_id, " (", format(round(pct, 1), nsmall = 1), " %)")
      } else {
        paste0("Classe ", cl_id)
      }
    }, character(1))
    hc$labels <- labels_txt
    
    if (identical(style_affichage, "factoextra") && requireNamespace("factoextra", quietly = TRUE)) {
      ok_facto <- tryCatch({
        p <- factoextra::fviz_dend(
          hc,
          k = clusternb,
          horiz = identical(orientation, "horizontal"),
          cex = 0.70,
          k_colors = NULL,
          color_labels_by_k = FALSE,
          rect = TRUE,
          rect_border = "#7a7a7a",
          rect_fill = FALSE,
          main = "Dendrogramme CHD (factoextra)",
          xlab = "",
          ylab = ""
        )
        p <- p + ggplot2::theme(
          axis.title = ggplot2::element_blank(),
          axis.text = ggplot2::element_blank(),
          axis.ticks = ggplot2::element_blank(),
          axis.line = ggplot2::element_blank(),
          panel.border = ggplot2::element_blank(),
          panel.grid = ggplot2::element_blank(),
          legend.position = "none",
          plot.margin = grid::unit(c(10, 180, 10, 10), "pt")
        )
        if (!is.null(p$coordinates)) {
          p$coordinates$clip <- "off"
        }
        print(p)
        TRUE
      }, error = function(e) FALSE)
      
      if (isTRUE(ok_facto)) return(TRUE)
      # Si le rendu factoextra échoue, on signale l'échec (pas de tracé CHD legacy).
    }

    if (identical(style_affichage, "iramuteq_bars")) {
      ok_bars <- tryCatch(
        isTRUE(tracer_dendrogramme_iramuteq_bars_hclust(
          hc = hc,
          classes = classes,
          main = "Dendrogramme CHD"
        )),
        error = function(e) FALSE
      )
      if (isTRUE(ok_bars)) return(TRUE)
    }

    FALSE
  }
  
  n1 <- .normaliser_n1_chd(chd_obj$n1)
  list_fille <- chd_obj$list_fille
  has_chd_tree <- !is.null(n1) && is.list(list_fille) && length(list_fille) > 0
  
  # Option 1: rendu hclust/factoextra (si disponible et demandé).
  if (.tracer_dendrogramme_hclust(
    res_stats_df = res_stats_df,
    classes = classes,
    top_n_terms = top_n_terms,
    orientation = orientation,
    style_affichage = style_affichage
  )) {
    return(invisible(NULL))
  }
  
  if (style_affichage %in% c("factoextra", "ape", "dendextend", "ggdendro")) {
    plot.new()
    text(0.5, 0.5, paste0("Impossible de tracer le dendrogramme avec le style '", style_affichage, "'."), cex = 1.0)
    return(invisible(NULL))
  }
  
  # Option 2: rendu CHD natif (arbre historique list_mere/list_fille).
  if (!isTRUE(has_chd_tree)) {
    plot.new()
    text(0.5, 0.5, "Dendrogramme CHD indisponible.", cex = 1.0)
    return(invisible(NULL))
  }
  
  noms <- names(list_fille)
  if (is.null(noms) || any(!nzchar(noms))) noms <- as.character(seq_along(list_fille))
  map_filles <- stats::setNames(lapply(list_fille, function(x) as.integer(x)), noms)
  
  terminales <- suppressWarnings(as.integer(terminales))
  terminales <- terminales[is.finite(terminales)]
  terminales <- unique(terminales)
  
  edges_df <- do.call(rbind, lapply(names(map_filles), function(mere_name) {
    mere <- suppressWarnings(as.integer(mere_name))
    filles <- suppressWarnings(as.integer(map_filles[[mere_name]]))
    filles <- filles[is.finite(filles)]
    if (!is.finite(mere) || !length(filles)) return(NULL)
    cbind(parent = rep.int(mere, length(filles)), child = filles)
  }))
  
  if (is.null(edges_df) || !nrow(edges_df)) {
    plot.new()
    text(0.5, 0.5, "Dendrogramme CHD indisponible (arbre vide).", cex = 1.1)
    return(invisible(NULL))
  }
  
  edges_df <- unique(as.data.frame(edges_df))
  all_nodes <- sort(unique(c(edges_df$parent, edges_df$child)))
  parent_nodes <- sort(unique(edges_df$parent))
  detected_tips <- setdiff(all_nodes, parent_nodes)
  
  if (!length(detected_tips)) {
    plot.new()
    text(0.5, 0.5, "Aucune classe terminale exploitable.", cex = 1.1)
    return(invisible(NULL))
  }
  
  # Conserver toutes les feuilles détectées pour le placement du tree,
  # sinon certaines branches peuvent disparaître si `terminales` est incomplet.
  tip_nodes <- detected_tips
  
  # Les classes affichées restent strictement celles des terminales CHD.
  # On n'invente pas de classes de fallback pour préserver la fidélité au découpage.
  class_by_tip <- stats::setNames(rep(NA_integer_, length(tip_nodes)), as.character(tip_nodes))
  if (length(terminales)) {
    # Les identifiants de classes suivent la numérotation CHD (ordre des terminales).
    class_ids <- seq_along(terminales)
    for (i in seq_along(terminales)) {
      node <- as.character(terminales[[i]])
      if (node %in% names(class_by_tip)) class_by_tip[[node]] <- class_ids[[i]]
    }
  }
  class_tip_keys <- names(class_by_tip)[is.finite(class_by_tip)]
  if (!length(class_tip_keys)) {
    # Repli minimal si l'objet CHD ne fournit pas de mapping terminales exploitable.
    class_by_tip[] <- seq_along(class_by_tip)
    class_tip_keys <- names(class_by_tip)
  }
  
  pct_par_classe <- NULL
  if (!is.null(classes)) {
    classes <- suppressWarnings(as.integer(classes))
    classes <- classes[is.finite(classes) & classes > 0]
    if (length(classes)) pct_par_classe <- prop.table(table(classes)) * 100
  }
  
  .palette_classes_iramuteq <- function(ids) {
    ids <- suppressWarnings(as.integer(ids))
    ids <- ids[is.finite(ids) & ids > 0]
    if (!length(ids)) return(character(0))
    
    base_cols <- c(
      "#f1261c", # rouge
      "#64f041", # vert
      "#d432f0", # magenta
      "#66d8dd", # cyan
      "#1225f5", # bleu
      "#6f6f6f", # gris
      "#ff9800", # orange
      "#8bc34a"  # vert clair
    )
    
    idx <- ((ids - 1L) %% length(base_cols)) + 1L
    stats::setNames(base_cols[idx], as.character(ids))
  }
  
  top_n_terms <- suppressWarnings(as.integer(top_n_terms))
  if (!is.finite(top_n_terms) || is.na(top_n_terms) || top_n_terms < 1L) top_n_terms <- 1L
  termes_par_classe <- list()
  if (!is.null(res_stats_df) && is.data.frame(res_stats_df) && all(c("Classe", "Terme") %in% names(res_stats_df))) {
    df_terms <- res_stats_df
    df_terms$Classe <- suppressWarnings(as.integer(df_terms$Classe))
    df_terms <- df_terms[is.finite(df_terms$Classe) & nzchar(as.character(df_terms$Terme)), , drop = FALSE]
    for (cl in unique(as.integer(class_by_tip[class_tip_keys]))) {
      sous <- df_terms[df_terms$Classe == cl, , drop = FALSE]
      if (!nrow(sous)) next
      if ("chi2" %in% names(sous)) {
        chi <- suppressWarnings(as.numeric(sous$chi2))
        chi[!is.finite(chi)] <- -Inf
        sous <- sous[order(chi, decreasing = TRUE), , drop = FALSE]
      }
      termes <- unique(as.character(sous$Terme))
      termes <- termes[nzchar(termes)]
      if (length(termes)) termes_par_classe[[as.character(cl)]] <- paste(utils::head(termes, top_n_terms), collapse = ", ")
    }
  }
  
  tip_label <- vapply(class_tip_keys, function(node) {
    cl <- class_by_tip[[node]]
    pct <- if (!is.null(pct_par_classe)) suppressWarnings(as.numeric(pct_par_classe[[as.character(cl)]])) else NA_real_
    pct_txt <- if (is.finite(pct)) paste0(" (", format(round(pct, 1), nsmall = 1), " %)") else ""
    termes_txt <- termes_par_classe[[as.character(cl)]]
    if (is.null(termes_txt) || !nzchar(termes_txt)) {
      paste0("Classe ", cl, pct_txt)
    } else {
      paste0("Classe ", cl, pct_txt, "\n", termes_txt)
    }
  }, FUN.VALUE = character(1))
  
  children_map <- split(edges_df$child, edges_df$parent)
  children_map <- lapply(children_map, function(x) as.integer(unique(x)))
  roots <- setdiff(parent_nodes, edges_df$child)
  if (!length(roots)) roots <- parent_nodes[1]
  
  assign_leaf_x <- function(node, state) {
    node_key <- as.character(node)
    kids <- children_map[[node_key]]
    kids <- kids[is.finite(kids)]
    
    if (!length(kids) || !(node %in% parent_nodes)) {
      if (!(node %in% tip_nodes)) return(state)
      state$x[[node_key]] <- state$next_x
      state$next_x <- state$next_x + 1
      return(state)
    }
    
    for (kid in kids) state <- assign_leaf_x(kid, state)
    kid_keys <- as.character(kids)
    kid_x <- unname(unlist(state$x[kid_keys]))
    kid_x <- kid_x[is.finite(kid_x)]
    if (length(kid_x)) state$x[[node_key]] <- mean(kid_x)
    state
  }
  
  state <- list(x = list(), next_x = 1)
  for (rt in roots) state <- assign_leaf_x(rt, state)
  x_pos <- state$x
  
  y_pos <- list()
  assign_depth <- function(node, depth = 0L) {
    node_key <- as.character(node)
    if (!is.null(y_pos[[node_key]]) && y_pos[[node_key]] <= depth) return(invisible(NULL))
    y_pos[[node_key]] <<- depth
    kids <- children_map[[node_key]]
    kids <- kids[is.finite(kids)]
    for (kid in kids) assign_depth(kid, depth + 1L)
    invisible(NULL)
  }
  for (rt in roots) assign_depth(rt, 0L)
  
  all_y <- unname(unlist(y_pos))
  max_depth <- if (length(all_y)) max(all_y, na.rm = TRUE) else 1
  if (!is.finite(max_depth) || max_depth <= 0) max_depth <- 1
  
  node_keys <- names(y_pos)
  x_vals <- vapply(node_keys, function(k) {
    val <- x_pos[[k]]
    if (!length(val)) return(NA_real_)
    as.numeric(val[[1]])
  }, numeric(1))
  y_vals <- vapply(node_keys, function(k) as.numeric(y_pos[[k]]), numeric(1))
  keep_nodes <- is.finite(x_vals) & is.finite(y_vals)
  node_keys <- node_keys[keep_nodes]
  x_vals <- x_vals[keep_nodes]
  y_vals <- y_vals[keep_nodes]
  
  if (!length(node_keys)) {
    plot.new()
    text(0.5, 0.5, "Dendrogramme CHD indisponible (coordonnées invalides).", cex = 1.1)
    return(invisible(NULL))
  }
  
  node_xy <- stats::setNames(vector("list", length(node_keys)), node_keys)
  for (i in seq_along(node_keys)) {
    node_xy[[node_keys[[i]]]] <- c(x = x_vals[[i]], y = y_vals[[i]])
  }
  
  .draw_tree_edge <- function(x1, y1, x2, y2, mode = c("vertical_tree", "horizontal_tree"), lwd = 2.3, col = "#808080", ...) {
    mode <- match.arg(mode)
    if (!is.finite(x1) || !is.finite(y1) || !is.finite(x2) || !is.finite(y2)) return(invisible(NULL))
    
    if (identical(mode, "vertical_tree")) {
      segments(x1, y1, x2, y1, lwd = lwd, col = col, ...)
      segments(x2, y1, x2, y2, lwd = lwd, col = col, ...)
      return(invisible(NULL))
    }
    
    segments(x1, y1, x1, y2, lwd = lwd, col = col, ...)
    segments(x1, y2, x2, y2, lwd = lwd, col = col, ...)
    invisible(NULL)
  }
  
  old_mar <- par("mar")
  on.exit(par(mar = old_mar), add = TRUE)
  
  if (identical(orientation, "vertical")) {
    par(mar = c(2, 1, 3, 1))
    plot(0, 0,
         type = "n",
         xlim = c(min(x_vals) - 0.5, max(x_vals) + 0.5),
         ylim = c(max_depth + 0.8, -0.5),
         axes = FALSE,
         xlab = "", ylab = "",
         main = "Dendrogramme CHD"
    )
    
    for (i in seq_len(nrow(edges_df))) {
      p_key <- as.character(edges_df$parent[[i]])
      c_key <- as.character(edges_df$child[[i]])
      p_xy <- node_xy[[p_key]]
      c_xy <- node_xy[[c_key]]
      if (is.null(p_xy) || is.null(c_xy)) next
      .draw_tree_edge(
        x1 = p_xy[["x"]], y1 = p_xy[["y"]],
        x2 = c_xy[["x"]], y2 = c_xy[["y"]],
        mode = "vertical_tree",
        lwd = 2.3,
        col = "#5f5f5f",
        xpd = TRUE
      )
    }
    
    for (tip in class_tip_keys) {
      xy <- node_xy[[tip]]
      if (is.null(xy)) next
      lignes <- strsplit(tip_label[[tip]], "\n", fixed = TRUE)[[1]]
      classe_txt <- lignes[[1]]
      termes_txt <- if (length(lignes) > 1) lignes[[2]] else ""
      text(xy[["x"]], xy[["y"]] + 0.2, labels = classe_txt, cex = 0.75, pos = 1, xpd = TRUE)
      if (nzchar(termes_txt)) {
        termes_vec <- trimws(strsplit(termes_txt, ",", fixed = TRUE)[[1]])
        termes_vec <- termes_vec[nzchar(termes_vec)]
        if (length(termes_vec)) {
          offsets_x <- seq(-0.45, 0.45, length.out = length(termes_vec))
          offsets_y <- rep(c(-0.1, -0.2, 0), length.out = length(termes_vec))
          tailles <- seq(0.85, 0.65, length.out = length(termes_vec))
          text(xy[["x"]] + offsets_x, xy[["y"]] + 0.02 + offsets_y, labels = termes_vec, cex = tailles, xpd = TRUE)
        }
      }
    }
  } else {

    
    tracer_dendrogramme_iramuteq_bars(
      edges_df = edges_df,
      node_xy = node_xy,
      class_tip_keys = class_tip_keys,
      class_by_tip = class_by_tip,
      pct_par_classe = pct_par_classe,
      max_depth = max_depth,
      x_vals = x_vals,
      .palette_classes_iramuteq = .palette_classes_iramuteq,
      .draw_tree_edge = .draw_tree_edge
    )
  }
  
  invisible(NULL)
}
