# afc.R
# AFC (Analyse Factorielle des Correspondances) pour classes × termes et classes × variables étoilées
# Dépendance principale : FactoMineR (CA)
# Le fichier fournit les fonctions attendues par app.R, sans changer la logique globale :
# - calcul des tables de contingence
# - exécution de l'AFC
# - statistiques (fréquence, chi2, p-value)
# - tracés avec axes centrés (0 au centre) et limites symétriques
# - option anti-chevauchement des labels (placement en spirale + tests de collision)

verifier_factominer <- function() {
  if (!requireNamespace("FactoMineR", quietly = TRUE)) {
    stop("AFC : le package 'FactoMineR' n'est pas installé ou indisponible dans l'environnement.")
  }
}

# Limites symétriques autour de 0 pour centrer le graphe (0,0) au centre
calculer_lim_sym <- function(x, y, marge = 0.08) {
  x <- x[is.finite(x)]
  y <- y[is.finite(y)]
  if (length(x) == 0 || length(y) == 0) return(c(-1, 1))
  m <- max(abs(c(x, y)))
  if (!is.finite(m) || m == 0) m <- 1
  m <- m * (1 + marge)
  c(-m, m)
}

# Test de chevauchement rectangles
.rectangles_chevauchent <- function(r1, r2) {
  !(r1$xmax < r2$xmin || r2$xmax < r1$xmin || r1$ymax < r2$ymin || r2$ymax < r1$ymin)
}

# Placement anti-chevauchement des labels
# Technique : on place les mots un par un. Si collision avec un label déjà placé, on déplace le label le long d'une spirale
# (rayon croissant + angle) jusqu'à trouver une position non collisionnante, ou jusqu'à max_iter.
placer_labels_sans_chevauchement_spirale <- function(x, y, labels, cex_vec, max_iter = 220) {
  x <- as.numeric(x)
  y <- as.numeric(y)
  n <- length(labels)
  if (n == 0) return(list(x = x, y = y))

  if (length(cex_vec) == 1) cex_vec <- rep(cex_vec, n)
  cex_vec <- as.numeric(cex_vec)
  cex_vec[!is.finite(cex_vec)] <- 1

  usr <- par("usr")
  rx <- usr[2] - usr[1]
  ry <- usr[4] - usr[3]
  if (!is.finite(rx) || rx == 0) rx <- 1
  if (!is.finite(ry) || ry == 0) ry <- 1

  # Pas de déplacement relatif à l'étendue du graphe
  pas <- 0.012 * max(rx, ry)

  x2 <- x
  y2 <- y

  rects <- vector("list", n)

  for (i in seq_len(n)) {
    lab <- labels[i]
    cexi <- cex_vec[i]

    wi <- strwidth(lab, units = "user", cex = cexi)
    hi <- strheight(lab, units = "user", cex = cexi)

    if (!is.finite(wi) || wi == 0) wi <- 0.02 * rx
    if (!is.finite(hi) || hi == 0) hi <- 0.02 * ry

    xi <- x2[i]
    yi <- y2[i]

    ri <- list(
      xmin = xi - wi / 2, xmax = xi + wi / 2,
      ymin = yi - hi / 2, ymax = yi + hi / 2
    )

    collision <- FALSE
    if (i > 1) {
      for (j in seq_len(i - 1)) {
        if (!is.null(rects[[j]]) && .rectangles_chevauchent(ri, rects[[j]])) {
          collision <- TRUE
          break
        }
      }
    }

    if (!collision) {
      rects[[i]] <- ri
      next
    }

    # Recherche en spirale
    angle <- 0
    rayon <- pas

    trouve <- FALSE
    for (k in seq_len(max_iter)) {
      angle <- angle + 0.65
      rayon <- rayon + pas * 0.15

      xi_try <- x[i] + rayon * cos(angle)
      yi_try <- y[i] + rayon * sin(angle)

      ri_try <- list(
        xmin = xi_try - wi / 2, xmax = xi_try + wi / 2,
        ymin = yi_try - hi / 2, ymax = yi_try + hi / 2
      )

      collision2 <- FALSE
      if (i > 1) {
        for (j in seq_len(i - 1)) {
          if (!is.null(rects[[j]]) && .rectangles_chevauchent(ri_try, rects[[j]])) {
            collision2 <- TRUE
            break
          }
        }
      }

      if (!collision2) {
        x2[i] <- xi_try
        y2[i] <- yi_try
        rects[[i]] <- ri_try
        trouve <- TRUE
        break
      }
    }

    if (!trouve) {
      rects[[i]] <- ri
    }
  }

  list(x = x2, y = y2)
}

# Calcul des résidus standardisés par colonne (terme/modalité) et par classe
.calculer_residus_standardises <- function(tab) {
  tab <- as.matrix(tab)
  if (any(tab < 0, na.rm = TRUE)) stop("AFC : table de contingence invalide (valeurs négatives).")
  n <- sum(tab)
  if (!is.finite(n) || n <= 0) stop("AFC : table de contingence vide (somme nulle).")

  rs <- rowSums(tab)
  cs <- colSums(tab)
  attendu <- outer(rs, cs) / n

  # Résidus standardisés : (O - E) / sqrt(E)
  res <- (tab - attendu) / sqrt(attendu)
  res[!is.finite(res)] <- 0
  list(attendu = attendu, residus = res)
}

# Statistiques globales d'association d'une colonne (terme/modalité) avec les classes
# chi2 et p_value : test sur la distribution observée vs attendue sur les classes
.calculer_stats_colonnes <- function(tab, seuil_p = 0.05) {
  tab <- as.matrix(tab)
  n <- sum(tab)
  rs <- rowSums(tab)
  cs <- colSums(tab)
  k <- nrow(tab)

  exp_mat <- outer(rs, cs) / n
  exp_mat[!is.finite(exp_mat)] <- 0

  out <- data.frame(
    feature = colnames(tab),
    frequency = as.numeric(cs),
    chi2 = NA_real_,
    p_value = NA_real_,
    Classe_max = NA_character_,
    resid_max = NA_real_,
    stringsAsFactors = FALSE
  )

  rr <- .calculer_residus_standardises(tab)$residus

  for (j in seq_len(ncol(tab))) {
    obs <- tab[, j]
    expv <- exp_mat[, j]

    # chi2 global sur classes
    good <- expv > 0
    if (sum(good) >= 2) {
      chi2j <- sum((obs[good] - expv[good])^2 / expv[good])
      df <- max(1, sum(good) - 1)
      pv <- suppressWarnings(stats::pchisq(chi2j, df = df, lower.tail = FALSE))
    } else {
      chi2j <- NA_real_
      pv <- NA_real_
    }

    out$chi2[j] <- as.numeric(chi2j)
    out$p_value[j] <- as.numeric(pv)

    # classe de surreprésentation : max résidu standardisé
    rj <- rr[, j]
    imax <- which.max(rj)
    out$Classe_max[j] <- rownames(tab)[imax]
    out$resid_max[j] <- rj[imax]

  }

  out
}

# Construit la table Classes × Termes à partir d'un dfm quanteda
calculer_table_classes_termes <- function(dfm_obj, groupes, termes_cibles = NULL, max_termes = 400) {
  if (!inherits(dfm_obj, "dfm")) stop("AFC : dfm_obj doit être un objet quanteda::dfm.")
  if (is.null(groupes) || length(groupes) != quanteda::ndoc(dfm_obj)) stop("AFC : 'groupes' doit avoir la même longueur que ndoc(dfm_obj).")

  g <- as.character(groupes)
  g[is.na(g) | !nzchar(g)] <- NA_character_

  keep <- !is.na(g)
  dfm2 <- dfm_obj[keep, ]
  g2 <- g[keep]

  if (quanteda::ndoc(dfm2) < 2) stop("AFC : pas assez de segments classés (hors NA).")

  # Sélection des termes
  if (!is.null(termes_cibles)) {
    termes_cibles <- unique(as.character(termes_cibles))
    termes_cibles <- termes_cibles[!is.na(termes_cibles) & nzchar(termes_cibles)]
    termes_cibles <- intersect(termes_cibles, quanteda::featnames(dfm2))
    if (length(termes_cibles) >= 2) {
      dfm2 <- dfm2[, termes_cibles]
    }
  }

  if (quanteda::nfeat(dfm2) > max_termes) {
    top <- quanteda::topfeatures(dfm2, n = max_termes)
    dfm2 <- dfm2[, names(top)]
  }

  if (quanteda::nfeat(dfm2) < 2) stop("AFC : moins de 2 termes disponibles pour l'AFC.")

  dfm_g <- quanteda::dfm_group(dfm2, groups = g2)
  mat <- as.matrix(dfm_g)
  if (nrow(mat) < 2 || ncol(mat) < 2) stop("AFC : table Classes × Termes trop petite.")

  # Noms des classes pour affichage
  rn <- rownames(mat)
  rn2 <- paste0("Classe ", rn)
  rownames(mat) <- rn2

  mat
}

# Exécution AFC classes × termes
executer_afc_classes <- function(dfm_obj, groupes, termes_cibles = NULL, max_termes = 400, seuil_p = 0.05, rv = NULL) {
  verifier_factominer()

  tab <- calculer_table_classes_termes(
    dfm_obj = dfm_obj,
    groupes = groupes,
    termes_cibles = termes_cibles,
    max_termes = max_termes
  )

  ca <- FactoMineR::CA(tab, graph = FALSE)

  rowcoord <- ca$row$coord
  colcoord <- ca$col$coord

  # Stats des termes (globales sur la table AFC)
  st <- .calculer_stats_colonnes(tab, seuil_p = seuil_p)
  names(st)[names(st) == "feature"] <- "Terme"

  # Harmonisation : noms de classes déjà "Classe X"
  st$Classe_max <- as.character(st$Classe_max)
  # Dans .calculer_stats_colonnes, les classes sont rownames(tab), donc déjà "Classe X"

  list(
    table = tab,
    ca = ca,
    rowcoord = rowcoord,
    colcoord = colcoord,
    termes_stats = st,
    seuil_p = seuil_p
  )
}

# Tracé AFC des classes uniquement
tracer_afc_classes_seules <- function(obj, axes = c(1, 2), cex_labels = 1.0) {
  if (is.null(obj$ca) || is.null(obj$rowcoord)) stop("AFC classes : objet incomplet.")
  ax1 <- axes[1]
  ax2 <- axes[2]

  rc <- obj$rowcoord
  x_c <- rc[, ax1]
  y_c <- rc[, ax2]

  lim <- calculer_lim_sym(x_c, y_c)
  plot(
    0, 0,
    type = "n",
    xlab = paste0("Axe ", ax1),
    ylab = paste0("Axe ", ax2),
    xlim = lim, ylim = lim
  )
  abline(h = 0, v = 0, col = "gray80")

  points(x_c, y_c, pch = 19, cex = 1.3)
  text(x_c, y_c, labels = rownames(rc), pos = 3, cex = cex_labels)
}

# Tracé AFC classes + termes
# - couleurs des mots : selon la classe où ils sont le plus surreprésentés (Classe_max)
# - taille des mots : au choix (frequency ou chi2)
# - anti-chevauchement : option activer_repel
tracer_afc_classes_termes <- function(
  obj,
  axes = c(1, 2),
  top_termes = 120,
  taille_sel = c("frequency", "chi2"),
  activer_repel = TRUE,
  cex_min = 0.8,
  cex_max = 2.0,
  repel_max_iter = 220
) {
  if (is.null(obj$ca) || is.null(obj$rowcoord) || is.null(obj$colcoord) || is.null(obj$termes_stats)) {
    stop("AFC : objet incomplet (coordonnées / stats manquantes).")
  }

  taille_sel <- match.arg(taille_sel)
  ax1 <- axes[1]
  ax2 <- axes[2]

  rc <- obj$rowcoord
  cc <- obj$colcoord
  st <- obj$termes_stats

  st <- st[!is.na(st$Terme) & nzchar(st$Terme), , drop = FALSE]
  st <- st[order(-st$frequency), , drop = FALSE]

  if (!is.null(top_termes) && is.finite(top_termes) && nrow(st) > top_termes) {
    st <- st[seq_len(top_termes), , drop = FALSE]
  }

  st <- st[st$Terme %in% rownames(cc), , drop = FALSE]
  if (nrow(st) < 2) {
    plot.new()
    text(0.5, 0.5, "AFC : pas assez de termes à tracer.", cex = 1.1)
    return(invisible(NULL))
  }

  mots <- st$Terme
  xy_m <- cc[mots, , drop = FALSE]
  x_m <- xy_m[, ax1]
  y_m <- xy_m[, ax2]

  x_c <- rc[, ax1]
  y_c <- rc[, ax2]

  lim <- calculer_lim_sym(c(x_m, x_c), c(y_m, y_c))
  plot(
    0, 0,
    type = "n",
    xlab = paste0("Axe ", ax1),
    ylab = paste0("Axe ", ax2),
    xlim = lim, ylim = lim
  )
  abline(h = 0, v = 0, col = "gray80")

  # Note sur la technique : si activer_repel=TRUE, on applique un placement itératif en spirale
  # avec tests de collision rectangles afin de réduire le chevauchement des étiquettes.
  # Cela ne garantit pas 0 collision dans tous les cas, mais réduit fortement les superpositions.
  points(x_c, y_c, pch = 19, cex = 1.25)
  text(x_c, y_c, labels = rownames(rc), pos = 3, cex = 1.0)

  # Couleurs par classe
  classes <- sort(unique(rownames(rc)))
  ncl <- length(classes)
  pal <- if (requireNamespace("RColorBrewer", quietly = TRUE) && ncl <= 8) {
    RColorBrewer::brewer.pal(max(3, ncl), "Set2")[seq_len(ncl)]
  } else {
    grDevices::rainbow(ncl)
  }
  col_map <- setNames(pal, classes)
  col_m <- col_map[st$Classe_max]
  col_m[is.na(col_m)] <- "gray40"

  # Tailles
  poids <- if (taille_sel == "chi2") st$chi2 else st$frequency
  poids <- suppressWarnings(as.numeric(poids))
  poids[!is.finite(poids)] <- 0
  poids <- pmax(0, poids)

  if (max(poids) == min(poids)) {
    cex_vec <- rep((cex_min + cex_max) / 2, length(poids))
  } else {
    v <- sqrt(poids)
    v <- (v - min(v)) / (max(v) - min(v))
    cex_vec <- cex_min + v * (cex_max - cex_min)
  }

  if (isTRUE(activer_repel)) {
    coords <- placer_labels_sans_chevauchement_spirale(
      x = x_m, y = y_m, labels = mots, cex_vec = cex_vec, max_iter = repel_max_iter
    )
    x_lab <- coords$x
    y_lab <- coords$y
  } else {
    x_lab <- x_m
    y_lab <- y_m
  }

  points(x_lab, y_lab, pch = 16, cex = 0.5, col = col_m)
  text(x_lab, y_lab, labels = mots, cex = cex_vec, col = col_m)
}

# Fallback : extraction de modalités depuis une ligne IRaMuTeQ (si docvars vides)
.extraire_modalites_depuis_ligne_iramuteq <- function(textes) {
  if (length(textes) == 0) return(vector("list", 0))
  res <- vector("list", length(textes))
  for (i in seq_along(textes)) {
    tx <- textes[i]
    if (is.na(tx) || !nzchar(tx)) {
      res[[i]] <- character(0)
      next
    }
    # On cherche des tokens commençant par * dans les 400 premiers caractères
    head <- substr(tx, 1, 400)
    mods <- unlist(regmatches(head, gregexpr("\\*[A-Za-z0-9_\\-]+", head, perl = TRUE)), use.names = FALSE)
    mods <- unique(mods)
    mods <- mods[!is.na(mods) & nzchar(mods)]
    res[[i]] <- mods
  }
  res
}

# Construction table Classes × Modalités à partir des docvars (ou fallback texte)
calculer_table_classes_modalites <- function(corpus_aligne, groupes, max_modalites = 400) {
  if (is.null(corpus_aligne)) stop("AFC variables étoilées : corpus_aligne requis.")
  dv <- quanteda::docvars(corpus_aligne)

  g <- as.character(groupes)
  g[is.na(g) | !nzchar(g)] <- NA_character_
  keep <- !is.na(g)
  if (sum(keep) < 2) stop("AFC variables étoilées : pas assez de segments classés (hors NA).")

  dv2 <- dv[keep, , drop = FALSE]
  g2 <- g[keep]

  # Colonnes candidates : on exclut les colonnes techniques
  exclure <- c("segment_source", "Classes")
  cols <- setdiff(colnames(dv2), exclure)

  modalites_par_seg <- NULL

  if (length(cols) > 0) {
    modalites_par_seg <- vector("list", nrow(dv2))
    for (i in seq_len(nrow(dv2))) {
      mods <- character(0)
      for (cn in cols) {
        v <- dv2[i, cn]
        v <- as.character(v)
        v <- v[!is.na(v) & nzchar(v)]
        if (length(v) == 0) next
        v <- gsub("\\s+", " ", trimws(v), perl = TRUE)
        if (!nzchar(v)) next
        # Modalité de type "var=valeur"
        mods <- c(mods, paste0(cn, "=", v))
      }
      modalites_par_seg[[i]] <- unique(mods)
    }
  }

  # Fallback si aucune modalité trouvée via docvars
  if (is.null(modalites_par_seg) || all(vapply(modalites_par_seg, length, integer(1)) == 0)) {
    textes <- as.character(corpus_aligne)[keep]
    modalites_par_seg <- .extraire_modalites_depuis_ligne_iramuteq(textes)
  }

  all_mods <- unique(unlist(modalites_par_seg, use.names = FALSE))
  all_mods <- all_mods[!is.na(all_mods) & nzchar(all_mods)]
  if (length(all_mods) < 2) stop("AFC variables étoilées : aucune modalité détectée.")

  # Comptages classes × modalités (présence/absence par segment)
  classes <- unique(g2)
  classes <- classes[!is.na(classes)]
  classes <- sort(classes)

  tab <- matrix(0, nrow = length(classes), ncol = length(all_mods))
  rownames(tab) <- paste0("Classe ", classes)
  colnames(tab) <- all_mods

  # Remplissage
  for (i in seq_along(g2)) {
    cl <- g2[i]
    if (is.na(cl)) next
    mods <- modalites_par_seg[[i]]
    if (length(mods) == 0) next
    mods <- intersect(mods, all_mods)
    if (length(mods) == 0) next
    tab[paste0("Classe ", cl), mods] <- tab[paste0("Classe ", cl), mods] + 1L
  }

  # Filtrage éventuel top modalités par fréquence
  freq <- colSums(tab)
  keepm <- freq > 0
  tab <- tab[, keepm, drop = FALSE]
  if (ncol(tab) < 2) stop("AFC variables étoilées : table trop pauvre après filtrage.")

  if (ncol(tab) > max_modalites) {
    ord <- order(colSums(tab), decreasing = TRUE)
    tab <- tab[, ord[seq_len(max_modalites)], drop = FALSE]
  }

  tab
}

# Exécution AFC classes × variables étoilées
executer_afc_variables_etoilees <- function(corpus_aligne, groupes, max_modalites = 400, seuil_p = 0.05, rv = NULL) {
  verifier_factominer()

  tab <- calculer_table_classes_modalites(
    corpus_aligne = corpus_aligne,
    groupes = groupes,
    max_modalites = max_modalites
  )

  ca <- FactoMineR::CA(tab, graph = FALSE)
  rowcoord <- ca$row$coord
  colcoord <- ca$col$coord

  st <- .calculer_stats_colonnes(tab, seuil_p = seuil_p)
  names(st)[names(st) == "feature"] <- "Modalite"

  list(
    table = tab,
    ca = ca,
    rowcoord = rowcoord,
    colcoord = colcoord,
    modalites_stats = st,
    seuil_p = seuil_p
  )
}

# Tracé AFC classes + variables étoilées
tracer_afc_variables_etoilees <- function(
  obj,
  axes = c(1, 2),
  top_modalites = 120,
  activer_repel = TRUE,
  cex_min = 0.8,
  cex_max = 2.0,
  repel_max_iter = 220
) {
  if (is.null(obj$ca) || is.null(obj$rowcoord) || is.null(obj$colcoord) || is.null(obj$modalites_stats)) {
    stop("AFC variables étoilées : objet incomplet (coordonnées / stats manquantes).")
  }

  ax1 <- axes[1]
  ax2 <- axes[2]

  rc <- obj$rowcoord
  cc <- obj$colcoord
  st <- obj$modalites_stats

  st <- st[!is.na(st$Modalite) & nzchar(st$Modalite), , drop = FALSE]
  st <- st[order(-st$frequency), , drop = FALSE]

  if (!is.null(top_modalites) && is.finite(top_modalites) && nrow(st) > top_modalites) {
    st <- st[seq_len(top_modalites), , drop = FALSE]
  }

  st <- st[st$Modalite %in% rownames(cc), , drop = FALSE]
  if (nrow(st) < 2) {
    plot.new()
    text(0.5, 0.5, "AFC variables étoilées : pas assez de modalités à tracer.", cex = 1.1)
    return(invisible(NULL))
  }

  mods <- st$Modalite
  xy_m <- cc[mods, , drop = FALSE]
  x_m <- xy_m[, ax1]
  y_m <- xy_m[, ax2]

  x_c <- rc[, ax1]
  y_c <- rc[, ax2]

  lim <- calculer_lim_sym(c(x_m, x_c), c(y_m, y_c))
  plot(
    0, 0,
    type = "n",
    xlab = paste0("Axe ", ax1),
    ylab = paste0("Axe ", ax2),
    xlim = lim, ylim = lim
  )
  abline(h = 0, v = 0, col = "gray80")

  points(x_c, y_c, pch = 19, cex = 1.25)
  text(x_c, y_c, labels = rownames(rc), pos = 3, cex = 1.0)

  # Couleurs par classe (classe max)
  classes <- sort(unique(rownames(rc)))
  ncl <- length(classes)
  pal <- if (requireNamespace("RColorBrewer", quietly = TRUE) && ncl <= 8) {
    RColorBrewer::brewer.pal(max(3, ncl), "Set2")[seq_len(ncl)]
  } else {
    grDevices::rainbow(ncl)
  }
  col_map <- setNames(pal, classes)
  col_m <- col_map[st$Classe_max]
  col_m[is.na(col_m)] <- "gray40"

  # Tailles : fréquence globale des modalités
  poids <- suppressWarnings(as.numeric(st$frequency))
  poids[!is.finite(poids)] <- 0
  poids <- pmax(0, poids)

  if (max(poids) == min(poids)) {
    cex_vec <- rep((cex_min + cex_max) / 2, length(poids))
  } else {
    v <- sqrt(poids)
    v <- (v - min(v)) / (max(v) - min(v))
    cex_vec <- cex_min + v * (cex_max - cex_min)
  }

  if (isTRUE(activer_repel)) {
    coords <- placer_labels_sans_chevauchement_spirale(
      x = x_m, y = y_m, labels = mods, cex_vec = cex_vec, max_iter = repel_max_iter
    )
    x_lab <- coords$x
    y_lab <- coords$y
  } else {
    x_lab <- x_m
    y_lab <- y_m
  }

  points(x_lab, y_lab, pch = 16, cex = 0.5, col = col_m)
  text(x_lab, y_lab, labels = mods, cex = cex_vec, col = col_m)
}
