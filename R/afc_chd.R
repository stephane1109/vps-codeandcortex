# AFC classes x terms computed from the Rainette CHD partition.

chdrainette_afc_table <- function(dfm_obj, groups, max_terms = 400L) {
  if (!inherits(dfm_obj, "dfm")) {
    stop("AFC : la matrice documentaire n'est pas un objet quanteda::dfm.")
  }
  if (length(groups) != quanteda::ndoc(dfm_obj)) {
    stop("AFC : le nombre de classes ne correspond pas au nombre de segments.")
  }

  groups <- suppressWarnings(as.integer(groups))
  keep <- !is.na(groups) & groups > 0L
  if (sum(keep) < 2L || length(unique(groups[keep])) < 2L) {
    stop("AFC : au moins deux classes non vides sont n\u00e9cessaires.")
  }

  work_dfm <- dfm_obj[keep, ]
  work_groups <- groups[keep]
  max_terms <- max(2L, suppressWarnings(as.integer(max_terms)))

  if (quanteda::nfeat(work_dfm) > max_terms) {
    top <- quanteda::topfeatures(work_dfm, n = max_terms)
    work_dfm <- work_dfm[, names(top)]
  }

  grouped <- quanteda::dfm_group(work_dfm, groups = factor(work_groups))
  table <- as.matrix(grouped)
  table <- table[rowSums(table) > 0, colSums(table) > 0, drop = FALSE]
  if (nrow(table) < 2L || ncol(table) < 2L) {
    stop("AFC : la table classes-termes est trop petite apr\u00e8s filtrage.")
  }

  rownames(table) <- paste("Classe", rownames(table))
  table
}

chdrainette_afc_two_dimensions <- function(coords) {
  coords <- as.matrix(coords)
  if (ncol(coords) < 2L) {
    coords <- cbind(coords, `Dim 2` = 0)
  }
  coords[, seq_len(2L), drop = FALSE]
}

chdrainette_compute_afc <- function(dfm_obj, groups, max_terms = 400L) {
  if (!requireNamespace("FactoMineR", quietly = TRUE)) {
    stop("AFC : le package FactoMineR n'est pas install\u00e9 dans l'image.")
  }

  table <- chdrainette_afc_table(dfm_obj, groups, max_terms = max_terms)
  ca <- FactoMineR::CA(table, graph = FALSE)
  class_coords <- chdrainette_afc_two_dimensions(ca$row$coord)
  term_coords <- chdrainette_afc_two_dimensions(ca$col$coord)

  total <- sum(table)
  expected <- outer(rowSums(table), colSums(table)) / total
  residuals <- (table - expected) / sqrt(expected)
  residuals[!is.finite(residuals)] <- 0

  term_chi2 <- colSums((table - expected)^2 / pmax(expected, .Machine$double.eps))
  dominant_index <- apply(residuals, 2L, which.max)
  term_stats <- data.frame(
    Terme = colnames(table),
    Frequence = as.numeric(colSums(table)),
    Chi2 = as.numeric(term_chi2),
    p_value = stats::pchisq(term_chi2, df = max(1L, nrow(table) - 1L), lower.tail = FALSE),
    Classe = rownames(table)[dominant_index],
    Residu = residuals[cbind(dominant_index, seq_len(ncol(table)))],
    stringsAsFactors = FALSE
  )
  term_stats <- term_stats[order(-term_stats$Chi2, -term_stats$Frequence), , drop = FALSE]

  eigenvalues <- as.data.frame(ca$eig, stringsAsFactors = FALSE)
  eigenvalues$Axe <- seq_len(nrow(eigenvalues))
  eigenvalues <- eigenvalues[, c("Axe", setdiff(names(eigenvalues), "Axe")), drop = FALSE]

  list(
    table = table,
    ca = ca,
    class_coords = class_coords,
    term_coords = term_coords,
    term_stats = term_stats,
    eigenvalues = eigenvalues
  )
}

chdrainette_afc_axis_label <- function(afc, axis) {
  percentage <- NA_real_
  if (nrow(afc$eigenvalues) >= axis && ncol(afc$eigenvalues) >= 3L) {
    percentage <- suppressWarnings(as.numeric(afc$eigenvalues[axis, 3L]))
  }
  if (is.finite(percentage)) {
    paste0("Axe ", axis, " (", sprintf("%.1f", percentage), " %)")
  } else {
    paste0("Axe ", axis)
  }
}

chdrainette_afc_limits <- function(x, y, margin = 0.12) {
  values <- c(as.numeric(x), as.numeric(y))
  values <- values[is.finite(values)]
  maximum <- if (length(values)) max(abs(values)) else 1
  if (!is.finite(maximum) || maximum <= 0) maximum <- 1
  maximum <- maximum * (1 + margin)
  c(-maximum, maximum)
}

chdrainette_afc_palette <- function(classes) {
  classes <- unique(as.character(classes))
  colors <- grDevices::hcl.colors(max(3L, length(classes)), palette = "Dark 3")
  stats::setNames(colors[seq_along(classes)], classes)
}

chdrainette_afc_place_labels <- function(x, y, labels, sizes, max_iterations = 2200L, fixed_rectangles = list()) {
  x <- as.numeric(x)
  y <- as.numeric(y)
  labels <- as.character(labels)
  labels[is.na(labels)] <- ""
  if (!length(labels)) {
    return(list(x = x, y = y, rectangles = list()))
  }

  if (!length(sizes)) {
    sizes <- rep(0.9, length(labels))
  } else {
    sizes <- rep_len(as.numeric(sizes), length(labels))
  }
  sizes[!is.finite(sizes) | sizes <= 0] <- 0.9
  user <- graphics::par("usr")
  range_x <- max(.Machine$double.eps, user[2L] - user[1L])
  range_y <- max(.Machine$double.eps, user[4L] - user[3L])
  padding_x <- range_x * 0.012
  padding_y <- range_y * 0.018
  placed <- fixed_rectangles
  result_x <- x
  result_y <- y
  result_rectangles <- vector("list", length(labels))

  overlaps <- function(first, second) {
    !(first$xmax < second$xmin || second$xmax < first$xmin ||
      first$ymax < second$ymin || second$ymax < first$ymin)
  }

  overlap_area <- function(first, second) {
    width <- min(first$xmax, second$xmax) - max(first$xmin, second$xmin)
    height <- min(first$ymax, second$ymax) - max(first$ymin, second$ymin)
    if (!is.finite(width) || !is.finite(height) || width <= 0 || height <= 0) {
      return(0)
    }
    width * height
  }

  overlap_score <- function(rectangle) {
    if (!length(placed)) {
      return(0)
    }
    sum(vapply(
      placed,
      function(previous) {
        if (is.null(previous)) {
          return(0)
        }
        overlap_area(rectangle, previous)
      },
      numeric(1)
    ))
  }

  make_rectangle <- function(center_x, center_y, width, height) {
    list(
      xmin = center_x - width / 2,
      xmax = center_x + width / 2,
      ymin = center_y - height / 2,
      ymax = center_y + height / 2
    )
  }

  clamp_axis <- function(value, lower, upper) {
    if (lower > upper) {
      return((lower + upper) / 2)
    }
    min(max(value, lower), upper)
  }

  label_order <- order(-sizes, -nchar(labels))
  for (index in label_order) {
    width <- graphics::strwidth(labels[index], units = "user", cex = sizes[index]) + padding_x
    height <- graphics::strheight(labels[index], units = "user", cex = sizes[index]) + padding_y
    width <- max(width, range_x * 0.018)
    height <- max(height, range_y * 0.026)
    best <- NULL
    best_score <- Inf
    selected <- NULL

    for (iteration in 0:max_iterations) {
      if (iteration == 0L) {
        candidate_x <- x[index]
        candidate_y <- y[index]
      } else {
        angle <- iteration * 2.399963
        radius <- sqrt(iteration)
        candidate_x <- x[index] + cos(angle) * radius * range_x * 0.006
        candidate_y <- y[index] + sin(angle) * radius * range_y * 0.008
      }

      candidate_x <- clamp_axis(candidate_x, user[1L] + width / 2, user[2L] - width / 2)
      candidate_y <- clamp_axis(candidate_y, user[3L] + height / 2, user[4L] - height / 2)
      rectangle <- make_rectangle(candidate_x, candidate_y, width, height)

      collision <- any(vapply(
        placed,
        function(previous) !is.null(previous) && overlaps(rectangle, previous),
        logical(1)
      ))
      if (!collision) {
        selected <- rectangle
        result_x[index] <- candidate_x
        result_y[index] <- candidate_y
        break
      }

      score <- overlap_score(rectangle) / (range_x * range_y) +
        ((candidate_x - x[index]) / range_x)^2 * 0.002 +
        ((candidate_y - y[index]) / range_y)^2 * 0.002
      if (score < best_score) {
        best_score <- score
        best <- list(rectangle = rectangle, x = candidate_x, y = candidate_y)
      }
    }

    if (is.null(selected)) {
      selected <- best$rectangle
      result_x[index] <- best$x
      result_y[index] <- best$y
    }
    placed[[length(placed) + 1L]] <- selected
    result_rectangles[[index]] <- selected
  }

  list(x = result_x, y = result_y, rectangles = result_rectangles)
}

chdrainette_plot_afc_classes <- function(afc) {
  coords <- afc$class_coords
  limit <- chdrainette_afc_limits(coords[, 1L], coords[, 2L])
  colors <- chdrainette_afc_palette(rownames(coords))
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old_par), add = TRUE)
  graphics::par(mar = c(4.2, 4.2, 0.8, 0.8), bg = "white")

  graphics::plot(
    coords[, 1L], coords[, 2L],
    type = "n",
    asp = 1,
    xlim = limit,
    ylim = limit,
    xlab = chdrainette_afc_axis_label(afc, 1L),
    ylab = chdrainette_afc_axis_label(afc, 2L),
    main = ""
  )
  graphics::abline(h = 0, v = 0, col = "#c7c2bb", lty = 2)
  graphics::points(coords[, 1L], coords[, 2L], pch = 19, cex = 1.35, col = colors[rownames(coords)])
  label_sizes <- rep(0.95, nrow(coords))
  placed <- chdrainette_afc_place_labels(coords[, 1L], coords[, 2L], rownames(coords), label_sizes, max_iterations = 1600L)
  moved <- abs(placed$x - coords[, 1L]) + abs(placed$y - coords[, 2L]) > .Machine$double.eps
  if (any(moved)) {
    graphics::segments(
      coords[moved, 1L],
      coords[moved, 2L],
      placed$x[moved],
      placed$y[moved],
      col = grDevices::adjustcolor(colors[rownames(coords)][moved], alpha.f = 0.35)
    )
  }
  graphics::text(placed$x, placed$y, labels = rownames(coords), cex = label_sizes, col = colors[rownames(coords)])
}

chdrainette_plot_afc_terms <- function(afc, top_terms = 80L, size_by = "Chi2", avoid_overlap = TRUE) {
  stats <- afc$term_stats
  top_terms <- max(5L, suppressWarnings(as.integer(top_terms)))
  stats <- utils::head(stats, top_terms)
  stats <- stats[stats$Terme %in% rownames(afc$term_coords), , drop = FALSE]
  if (!nrow(stats)) {
    graphics::plot.new()
    graphics::text(0.5, 0.5, "Aucun terme disponible pour l'AFC.")
    return(invisible(NULL))
  }

  terms <- afc$term_coords[stats$Terme, , drop = FALSE]
  classes <- afc$class_coords
  limit <- chdrainette_afc_limits(c(terms[, 1L], classes[, 1L]), c(terms[, 2L], classes[, 2L]))
  colors <- chdrainette_afc_palette(rownames(classes))
  term_colors <- unname(colors[stats$Classe])
  term_colors[is.na(term_colors)] <- "#5f6670"

  weights <- if (identical(size_by, "Frequence")) stats$Frequence else stats$Chi2
  weights <- sqrt(pmax(0, suppressWarnings(as.numeric(weights))))
  if (!length(weights) || max(weights) == min(weights)) {
    sizes <- rep(0.9, length(weights))
  } else {
    sizes <- 0.65 + 0.8 * (weights - min(weights)) / (max(weights) - min(weights))
  }
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old_par), add = TRUE)
  graphics::par(mar = c(4.2, 4.2, 0.8, 0.8), bg = "white")

  graphics::plot(
    0, 0,
    type = "n",
    asp = 1,
    xlim = limit,
    ylim = limit,
    xlab = chdrainette_afc_axis_label(afc, 1L),
    ylab = chdrainette_afc_axis_label(afc, 2L),
    main = ""
  )
  graphics::abline(h = 0, v = 0, col = "#c7c2bb", lty = 2)
  graphics::points(classes[, 1L], classes[, 2L], pch = 19, cex = 1.45, col = colors[rownames(classes)])
  class_label_x <- classes[, 1L]
  class_label_y <- classes[, 2L]
  class_rectangles <- list()
  if (isTRUE(avoid_overlap)) {
    class_sizes <- rep(0.92, nrow(classes))
    placed_classes <- chdrainette_afc_place_labels(
      class_label_x,
      class_label_y,
      rownames(classes),
      class_sizes,
      max_iterations = 1600L
    )
    moved_classes <- abs(placed_classes$x - class_label_x) + abs(placed_classes$y - class_label_y) > .Machine$double.eps
    if (any(moved_classes)) {
      graphics::segments(
        class_label_x[moved_classes],
        class_label_y[moved_classes],
        placed_classes$x[moved_classes],
        placed_classes$y[moved_classes],
        col = grDevices::adjustcolor(colors[rownames(classes)][moved_classes], alpha.f = 0.35)
      )
    }
    class_label_x <- placed_classes$x
    class_label_y <- placed_classes$y
    class_rectangles <- placed_classes$rectangles
  }
  graphics::text(class_label_x, class_label_y, labels = rownames(classes), cex = 0.92, font = 2, col = colors[rownames(classes)])
  label_x <- terms[, 1L]
  label_y <- terms[, 2L]
  if (isTRUE(avoid_overlap)) {
    placed <- chdrainette_afc_place_labels(label_x, label_y, stats$Terme, sizes, fixed_rectangles = class_rectangles)
    moved <- abs(placed$x - label_x) + abs(placed$y - label_y) > .Machine$double.eps
    if (any(moved)) {
      graphics::segments(label_x[moved], label_y[moved], placed$x[moved], placed$y[moved], col = grDevices::adjustcolor(term_colors[moved], alpha.f = 0.35))
    }
    label_x <- placed$x
    label_y <- placed$y
  }
  graphics::points(terms[, 1L], terms[, 2L], pch = 16, cex = 0.45, col = term_colors)
  graphics::text(label_x, label_y, labels = stats$Terme, cex = sizes, col = term_colors)
}

chdrainette_export_afc <- function(afc, export_dir) {
  afc_dir <- file.path(export_dir, "afc")
  dir.create(afc_dir, recursive = TRUE, showWarnings = FALSE)

  utils::write.csv(afc$table, file.path(afc_dir, "table_classes_termes.csv"), fileEncoding = "UTF-8")
  utils::write.csv(afc$class_coords, file.path(afc_dir, "coordonnees_classes.csv"), fileEncoding = "UTF-8")
  utils::write.csv(afc$term_coords, file.path(afc_dir, "coordonnees_termes.csv"), fileEncoding = "UTF-8")
  utils::write.csv(afc$term_stats, file.path(afc_dir, "statistiques_termes.csv"), row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(afc$eigenvalues, file.path(afc_dir, "valeurs_propres.csv"), row.names = FALSE, fileEncoding = "UTF-8")

  classes_png <- file.path(afc_dir, "afc_classes.png")
  grDevices::png(classes_png, width = 1800, height = 1500, res = 180)
  tryCatch(chdrainette_plot_afc_classes(afc), finally = grDevices::dev.off())

  terms_png <- file.path(afc_dir, "afc_classes_termes.png")
  grDevices::png(terms_png, width = 2200, height = 1800, res = 180)
  tryCatch(chdrainette_plot_afc_terms(afc, top_terms = 80L, size_by = "Chi2", avoid_overlap = TRUE), finally = grDevices::dev.off())

  list(directory = afc_dir, classes_png = classes_png, terms_png = terms_png)
}
