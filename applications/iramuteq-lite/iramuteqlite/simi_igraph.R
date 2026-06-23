# Rôle du fichier: simi_igraph.R isole le rendu igraph du graphe de similitudes
# avec un scaling explicite des tailles (mots/sommets) et des arêtes.

simi_extraire_freq_vertices <- function(g, vertex_freq = NULL) {
  if (is.null(g) || !inherits(g, "igraph") || igraph::vcount(g) == 0) {
    return(numeric(0))
  }
  vf <- suppressWarnings(as.numeric(vertex_freq))
  if (length(vf) == igraph::vcount(g) && any(is.finite(vf))) {
    vf[!is.finite(vf)] <- 0
    return(pmax(vf, 0))
  }
  vsize <- suppressWarnings(as.numeric(igraph::V(g)$size))
  if (length(vsize) == igraph::vcount(g) && any(is.finite(vsize))) {
    vsize[!is.finite(vsize)] <- median(vsize[is.finite(vsize)], na.rm = TRUE)
    return(pmax(vsize, 0))
  }
  rep(1, igraph::vcount(g))
}

simi_tailles_sommets_igraph <- function(freq, min_out = 5, max_out = 58, power = 0.9) {
  f <- suppressWarnings(as.numeric(freq))
  if (!length(f) || all(!is.finite(f))) return(rep((min_out + max_out) / 2, length(f)))
  f[!is.finite(f)] <- 0
  f <- pmax(f, 0)^power
  as.numeric(normaliser_vecteur_simi(f, min_out, max_out))
}

simi_tailles_labels_igraph <- function(freq, min_out = 0.6, max_out = 3.3, power = 0.85) {
  f <- suppressWarnings(as.numeric(freq))
  if (!length(f) || all(!is.finite(f))) return(rep((min_out + max_out) / 2, length(f)))
  f[!is.finite(f)] <- 0
  f <- pmax(f, 0)^power
  as.numeric(normaliser_vecteur_simi(f, min_out, max_out))
}

simi_largeurs_aretes_igraph <- function(weight, min_out = 0.35, max_out = 4.2, cap_out = 5.2) {
  w <- suppressWarnings(as.numeric(weight))
  if (!length(w) || all(!is.finite(w))) return(rep(1, length(w)))
  w[!is.finite(w)] <- 0
  w <- pmax(w, 0)
  wmax <- max(w, na.rm = TRUE)
  if (!is.finite(wmax) || wmax <= 0) return(rep(1, length(w)))
  # Échelle proportionnelle directe à l'indice (sans compression log).
  scaled <- (w / wmax) * max_out
  pmin(pmax(scaled, min_out), cap_out)
}

simi_etirer_layout_communautes <- function(lo,
                                          membership,
                                          g = NULL,
                                          ring_radius = NULL,
                                          within_scale = 1.18) {
  lo <- as.matrix(lo)
  membership <- suppressWarnings(as.integer(membership))
  if (!is.matrix(lo) || nrow(lo) == 0 || ncol(lo) < 2) return(lo)
  if (length(membership) != nrow(lo) || !any(is.finite(membership))) return(lo)

  lo2 <- lo[, 1:2, drop = FALSE]
  if (is.null(ring_radius) || !is.finite(ring_radius) || ring_radius <= 0) {
    # Règle proportionnelle au nombre de mots analysés.
    ring_radius <- max(2.4, 0.045 * nrow(lo2))
  }
  groups <- sort(unique(membership[is.finite(membership)]))

  # Choix du centre de l'étoile : communauté du sommet le plus "central".
  center_group <- groups[[1]]
  if (!is.null(g) && inherits(g, "igraph") && igraph::vcount(g) == nrow(lo2)) {
    s <- suppressWarnings(as.numeric(igraph::strength(g, mode = "all", weights = igraph::E(g)$weight)))
    if (length(s) == nrow(lo2) && any(is.finite(s))) {
      idx_star <- which.max(replace(s, !is.finite(s), -Inf))
      center_group <- membership[[idx_star]]
    }
  }

  outer_groups <- setdiff(groups, center_group)
  n_outer <- length(outer_groups)
  angle_map <- setNames(rep(0, length(groups)), as.character(groups))
  if (n_outer > 0) {
    angles <- seq(0, 2 * pi, length.out = n_outer + 1)[seq_len(n_outer)]
    angle_map[as.character(outer_groups)] <- angles
  }

  for (k in groups) {
    idx <- which(membership == k)
    if (!length(idx)) next
    c0 <- colMeans(lo2[idx, , drop = FALSE], na.rm = TRUE)
    if (identical(k, center_group)) {
      c1 <- c(0, 0)
    } else {
      ang <- angle_map[[as.character(k)]]
      c1 <- c(ring_radius * cos(ang), ring_radius * sin(ang))
    }
    lo2[idx, ] <- sweep(lo2[idx, , drop = FALSE], 2, c0, FUN = "-")
    lo2[idx, ] <- lo2[idx, ] * within_scale
    lo2[idx, ] <- sweep(lo2[idx, , drop = FALSE], 2, c1, FUN = "+")
  }

  lo[, 1:2] <- lo2
  lo
}

tracer_graphe_similitudes_igraph <- function(g,
                                            layout = NULL,
                                            edge_labels = TRUE,
                                            edge_width_by_index = TRUE,
                                            edge_curved = TRUE,
                                            vertex_text_by_freq = FALSE,
                                            vertex_freq = NULL,
                                            vertex_bubbles = TRUE,
                                            main = "Graphe de similitude",
                                            communities = NULL,
                                            halo = FALSE,
                                            zoom = 1,
                                            info_text = NULL) {
  if (is.null(g) || !inherits(g, "igraph") || igraph::vcount(g) == 0) {
    plot.new()
    text(0.5, 0.5, "Aucun graphe de similitude.\nCliquez sur 'Paramétrer' puis 'Lancer l'analyse de similitudes'.", cex = 1.0)
    return(invisible(NULL))
  }

  lo <- layout
  if (is.null(lo) || !is.matrix(lo) || nrow(lo) != igraph::vcount(g)) {
    lo <- igraph::layout_with_fr(g)
  }

  freq <- simi_extraire_freq_vertices(g, vertex_freq = vertex_freq)
  vertex_size <- simi_tailles_sommets_igraph(freq, min_out = 5, max_out = 58, power = 0.9)

  vertex_label_cex <- 1.0
  if (isTRUE(vertex_text_by_freq) || !isTRUE(vertex_bubbles)) {
    vertex_label_cex <- simi_tailles_labels_igraph(freq, min_out = 0.8, max_out = 2.6, power = 0.9)
  }
  if (length(vertex_label_cex) == 1L) {
    vertex_label_cex <- rep(vertex_label_cex, igraph::vcount(g))
  }
  vertex_labels <- as.character(igraph::V(g)$name)
  if (length(vertex_labels) != igraph::vcount(g)) {
    vertex_labels <- rep("", igraph::vcount(g))
  }
  vertex_labels[is.na(vertex_labels)] <- ""

  if (isTRUE(edge_width_by_index)) {
    edge_width <- simi_largeurs_aretes_igraph(igraph::E(g)$weight, min_out = 0.5, max_out = 8.5, cap_out = 10)
  } else {
    edge_width <- rep(1, igraph::ecount(g))
  }

  zoom <- suppressWarnings(as.numeric(zoom))
  if (!is.finite(zoom) || is.na(zoom) || zoom <= 0) zoom <- 1
  edge_lab <- if (isTRUE(edge_labels)) round(igraph::E(g)$weight, 3) else NA
  edge_curved_use <- if (isTRUE(edge_curved)) 0.16 else 0

  vcol <- "#2C7FB8"
  mark_groups <- NULL
  mark_col <- NULL
  mark_border <- NULL
  membership <- NULL
  if (!is.null(communities) && inherits(communities, "communities")) {
    memb <- as.integer(igraph::membership(communities))
    if (length(memb) == igraph::vcount(g) && any(is.finite(memb))) {
      membership <- memb
      ncom <- max(memb, na.rm = TRUE)
      pal <- grDevices::hcl.colors(ncom, palette = "Dark 3")
      idx <- pmax(1L, pmin(length(pal), memb))
      vcol <- pal[idx]

      if (isTRUE(halo)) {
        mark_groups <- igraph::groups(communities)
        mark_col <- grDevices::adjustcolor(pal[seq_along(mark_groups)], alpha.f = 0.22)
        mark_border <- grDevices::adjustcolor(pal[seq_along(mark_groups)], alpha.f = 0.85)
      }
    }
  }

  old_par <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old_par), add = TRUE)
  graphics::par(mar = c(1.2, 1.2, 3.2, 1.2), bg = "#E6E6E6")

  lo_mat <- as.matrix(lo)
  if (ncol(lo_mat) < 2) {
    lo_mat <- cbind(lo_mat, rep(0, nrow(lo_mat)))
  }
  if (!is.null(membership)) {
    n_words <- igraph::vcount(g)
    ring_radius_auto <- if (isTRUE(halo)) max(3.0, 0.050 * n_words) else max(2.4, 0.042 * n_words)
    within_scale_auto <- min(1.35, 1.03 + (n_words / 600))
    lo_mat <- simi_etirer_layout_communautes(
      lo_mat,
      membership = membership,
      g = g,
      ring_radius = ring_radius_auto,
      within_scale = within_scale_auto
    )
  }
  lo_plot <- lo_mat[, 1:2, drop = FALSE]
  lo_plot <- igraph::norm_coords(lo_plot, xmin = -1, xmax = 1, ymin = -1, ymax = 1)
  xlim_use <- c(-1 / zoom, 1 / zoom)
  ylim_use <- c(-1 / zoom, 1 / zoom)

  # Rendu statique attendu: pas de bulles de sommets (mots + arêtes + halos uniquement).
  # On conserve l'argument vertex_bubbles pour compatibilité d'appel.
  afficher_bulles <- FALSE
  # Sommets "tampon" invisibles pour éviter que les arêtes ne traversent les mots.
  # Les arêtes s'arrêtent au bord du sommet: on calibre donc la taille sur la taille du label.
  vertex_hitbox <- pmax(3, as.numeric(vertex_label_cex) * 4.6)

  plot(
    g,
    layout = lo_plot,
    main = main,
    vertex.label = vertex_labels,
    vertex.size = if (isTRUE(afficher_bulles)) vertex_size else vertex_hitbox,
    vertex.shape = if (isTRUE(afficher_bulles)) "circle" else "circle",
    vertex.color = if (isTRUE(afficher_bulles)) vcol else NA,
    vertex.frame.color = if (isTRUE(afficher_bulles)) "white" else NA,
    vertex.label.family = "sans",
    vertex.label.font = 1,
    vertex.label.cex = vertex_label_cex,
    vertex.label.color = "#111111",
    edge.width = edge_width,
    edge.color = grDevices::adjustcolor("#303030", alpha.f = 0.58),
    edge.label = edge_lab,
    edge.label.cex = 0.72,
    edge.label.color = "navy",
    edge.label.dist = 0.15,
    edge.curved = edge_curved_use,
    mark.groups = mark_groups,
    mark.col = mark_col,
    mark.border = mark_border,
    xlim = xlim_use,
    ylim = ylim_use
  )
  if (!is.null(info_text) && nzchar(info_text)) {
    mtext(info_text, side = 3, line = 0.3, cex = 0.82, col = "#455A64")
  }
}
