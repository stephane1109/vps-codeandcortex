# Rôle du fichier: rendu du dendrogramme CHD style IRaMuTeQ (barres à droite).

tracer_dendrogramme_iramuteq_bars <- function(edges_df,
                                              node_xy,
                                              class_tip_keys,
                                              class_by_tip,
                                              pct_par_classe,
                                              max_depth,
                                              x_vals,
                                              .palette_classes_iramuteq,
                                              .draw_tree_edge) {
  par(mar = c(1, 1, 3, 1))

  tip_keys <- class_tip_keys
  tip_pos <- vapply(tip_keys, function(k) {
    xy <- node_xy[[k]]
    if (is.null(xy)) return(NA_real_)
    as.numeric(xy[["x"]])
  }, numeric(1))
  ok_tip <- is.finite(tip_pos)
  tip_keys <- tip_keys[ok_tip]

  classes_tip <- as.integer(class_by_tip[tip_keys])
  pct_tip <- vapply(classes_tip, function(cl) {
    if (is.null(pct_par_classe)) return(NA_real_)
    suppressWarnings(as.numeric(pct_par_classe[[as.character(cl)]]))
  }, numeric(1))
  if (!length(pct_tip) || all(!is.finite(pct_tip))) {
    pct_tip <- rep(100 / max(1, length(tip_keys)), length(tip_keys))
  }
  pct_tip[!is.finite(pct_tip) | pct_tip < 0] <- 0

  cols_map <- .palette_classes_iramuteq(classes_tip)
  tip_cols <- if (length(cols_map)) unname(cols_map[as.character(classes_tip)]) else rep("#7aa6ff", length(classes_tip))
  tip_cols[is.na(tip_cols) | !nzchar(tip_cols)] <- "#7aa6ff"

  # On allonge fortement les barres pour mieux discriminer les classes.
  # Valeur = 3x le réglage d'origine (5.4).
  bar_max <- 16.2
  label_gap <- 0.32
  tip_end_pos <- vapply(tip_keys, function(k) {
    xy <- node_xy[[k]]
    if (is.null(xy)) return(NA_real_)
    as.numeric(xy[["y"]])
  }, numeric(1))
  tip_end_pos[!is.finite(tip_end_pos)] <- max_depth + 0.35

  tree_xmax <- max(c(max_depth + 0.35, tip_end_pos), na.rm = TRUE)
  x_right <- tree_xmax + bar_max + 6.2

  plot(0, 0,
       type = "n",
       xlim = c(-0.5, x_right),
       ylim = c(min(x_vals) - 0.5, max(x_vals) + 0.5),
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
      x1 = p_xy[["y"]], y1 = p_xy[["x"]],
      x2 = c_xy[["y"]], y2 = c_xy[["x"]],
      mode = "horizontal_tree",
      col = "#707070",
      lwd = 2.4,
      xpd = TRUE
    )
  }

  for (i in seq_along(tip_keys)) {
    tip <- tip_keys[[i]]
    xy <- node_xy[[tip]]
    if (is.null(xy)) next

    cl <- classes_tip[[i]]
    pct <- pct_tip[[i]]
    col_bar <- tip_cols[[i]]
    branch_tip_x <- tip_end_pos[[i]]

    width <- bar_max * (pct / 100)
    rect(
      xleft = branch_tip_x,
      ybottom = xy[["x"]] - 0.42,
      xright = branch_tip_x + width,
      ytop = xy[["x"]] + 0.42,
      col = grDevices::adjustcolor(col_bar, alpha.f = 0.95),
      border = "#6f6f6f",
      lwd = 1.2,
      xpd = TRUE
    )

    pct_lab <- paste0(format(round(pct, 1), nsmall = 1), " %")
    classe_txt <- paste0("Classe ", cl, " - ", pct_lab)
    label_x <- branch_tip_x + width + label_gap
    text(label_x, xy[["x"]], labels = classe_txt, cex = 1.02, adj = c(0, 0.5), xpd = TRUE,
         col = "#1f1f1f", font = 3)
  }

  invisible(NULL)
}

tracer_dendrogramme_iramuteq_bars_hclust <- function(hc,
                                                     classes = NULL,
                                                     main = "Dendrogramme CHD") {
  if (is.null(hc) || !inherits(hc, "hclust")) return(FALSE)

  .palette_classes <- function(ids) {
    ids <- as.integer(ids)
    ids <- ids[is.finite(ids)]
    if (!length(ids)) return(character(0))
    palette_base <- c("#F8766D", "#7CAE00", "#00BFC4", "#C77CFF", "#00BA38", "#619CFF", "#F564E3", "#B79F00")
    uniq <- sort(unique(ids))
    stats::setNames(rep_len(palette_base, length(uniq)), as.character(uniq))
  }

  pct_par_classe <- NULL
  if (!is.null(classes)) {
    classes_int <- suppressWarnings(as.integer(classes))
    classes_int <- classes_int[is.finite(classes_int) & classes_int > 0]
    if (length(classes_int)) pct_par_classe <- prop.table(table(classes_int)) * 100
  }

  dnd <- tryCatch(as.dendrogram(hc), error = function(e) NULL)
  if (is.null(dnd)) return(FALSE)

  leaf_idx <- 0L
  edges <- data.frame(px = numeric(0), py = numeric(0), cx = numeric(0), cy = numeric(0))

  .walk <- function(node) {
    if (is.leaf(node)) {
      leaf_idx <<- leaf_idx + 1L
      lbl <- as.character(attr(node, "label"))
      return(list(x = 0, y = as.numeric(leaf_idx), labels = lbl, ys = as.numeric(leaf_idx)))
    }

    kids <- lapply(node, .walk)
    x_parent <- as.numeric(attr(node, "height"))
    y_parent <- mean(vapply(kids, function(k) k$y, numeric(1)))

    for (k in kids) {
      edges <<- rbind(
        edges,
        data.frame(px = x_parent, py = y_parent, cx = x_parent, cy = k$y),
        data.frame(px = x_parent, py = k$y, cx = k$x, cy = k$y)
      )
    }

    list(
      x = x_parent,
      y = y_parent,
      labels = unlist(lapply(kids, function(k) k$labels), use.names = FALSE),
      ys = unlist(lapply(kids, function(k) k$ys), use.names = FALSE)
    )
  }

  root <- .walk(dnd)
  if (!length(root$labels) || !length(root$ys)) return(FALSE)

  labels_ord <- root$labels
  y_pos <- root$ys
  classes_tip <- suppressWarnings(as.integer(sub("^\\s*Classe\\s+([0-9]+).*$", "\\1", labels_ord, perl = TRUE)))
  classes_tip[!is.finite(classes_tip)] <- seq_along(classes_tip)[!is.finite(classes_tip)]

  pct_tip <- vapply(classes_tip, function(cl) {
    if (is.null(pct_par_classe)) return(NA_real_)
    suppressWarnings(as.numeric(pct_par_classe[[as.character(cl)]]))
  }, numeric(1))
  if (!length(pct_tip) || all(!is.finite(pct_tip))) pct_tip <- rep(100 / max(1, length(classes_tip)), length(classes_tip))
  pct_tip[!is.finite(pct_tip) | pct_tip < 0] <- 0

  cols_map <- .palette_classes(classes_tip)
  tip_cols <- if (length(cols_map)) unname(cols_map[as.character(classes_tip)]) else rep("#7aa6ff", length(classes_tip))
  tip_cols[is.na(tip_cols) | !nzchar(tip_cols)] <- "#7aa6ff"

  max_h <- max(c(1, hc$height), na.rm = TRUE)
  bar_space <- max_h * 1.42
  # Valeur = 3x le réglage d'origine (0.48).
  bar_max <- bar_space * 1.44
  label_gap <- max_h * 0.07
  label_space <- max_h * 0.95
  x_right <- -(bar_max + label_gap + label_space)

  old_mar <- par("mar")
  on.exit(par(mar = old_mar), add = TRUE)
  par(mar = c(1, 1, 3, 8))

  plot(0, 0,
       type = "n",
       xlim = c(max_h * 1.05, x_right),
       ylim = c(min(y_pos) - 0.8, max(y_pos) + 0.8),
       axes = FALSE,
       xlab = "", ylab = "",
       main = main
  )

  if (nrow(edges)) {
    segments(edges$px, edges$py, edges$cx, edges$cy, col = "#1f1f1f", lwd = 1.4, xpd = TRUE)
  }

  for (i in seq_along(classes_tip)) {
    cl <- classes_tip[[i]]
    pct <- pct_tip[[i]]
    col_bar <- tip_cols[[i]]
    y <- y_pos[[i]]

    width <- bar_max * (pct / 100)
    rect(-width, y - 0.36, 0, y + 0.36,
         col = grDevices::adjustcolor(col_bar, alpha.f = 0.95), border = "#6f6f6f", lwd = 1.1, xpd = TRUE)

    pct_lab <- paste0(format(round(pct, 1), nsmall = 1), " %")
    label_x <- -width - label_gap
    text(label_x,
         y,
         labels = paste0("Classe ", cl, " - ", pct_lab),
         adj = c(0, 0.5),
         cex = 0.86,
         col = "#1f1f1f",
         font = 3,
         xpd = TRUE)
  }

  TRUE
}
