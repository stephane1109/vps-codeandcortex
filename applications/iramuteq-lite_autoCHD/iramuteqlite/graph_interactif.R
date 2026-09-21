# Donnees de la vue AFC interactive.
# Ce module ne recalcule ni la CHD ni l'AFC : il relit les exports AFC
# et prepare uniquement les coordonnees necessaires a l'affichage SVG.

construire_donnees_graph_interactif_afc <- function(
    coords_classes_file,
    coords_termes_file,
    stats_termes_file,
    seuil_p = 0.05,
    top_termes = 120L
) {
  lire_coordonnees <- function(path) {
    if (is.null(path) || !file.exists(path)) return(NULL)
    read.csv(path, row.names = 1, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  }

  classes_df <- lire_coordonnees(coords_classes_file)
  termes_coord_df <- lire_coordonnees(coords_termes_file)
  if (is.null(classes_df) || is.null(termes_coord_df)) {
    stop("Exports de coordonnées AFC manquants pour le graphe interactif.")
  }

  extraire_xy <- function(df) {
    values <- as.data.frame(df, stringsAsFactors = FALSE)
    x <- suppressWarnings(as.numeric(values[[1]]))
    y <- if (ncol(values) >= 2) suppressWarnings(as.numeric(values[[2]])) else rep(0, nrow(values))
    data.frame(x = x, y = y, stringsAsFactors = FALSE, row.names = rownames(values))
  }

  classes_xy <- extraire_xy(classes_df)
  termes_xy <- extraire_xy(termes_coord_df)
  classes <- lapply(seq_len(nrow(classes_xy)), function(i) {
    list(
      label = rownames(classes_xy)[i],
      x = classes_xy$x[i],
      y = classes_xy$y[i]
    )
  })

  stats_df <- if (!is.null(stats_termes_file) && file.exists(stats_termes_file)) {
    read.csv(stats_termes_file, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  } else {
    data.frame()
  }

  termes <- list()
  if (nrow(stats_df) > 0 && "Terme" %in% names(stats_df)) {
    p_col <- if ("p_value" %in% names(stats_df)) "p_value" else if ("p" %in% names(stats_df)) "p" else NULL
    if (!is.null(p_col)) {
      p_values <- suppressWarnings(as.numeric(stats_df[[p_col]]))
      keep <- is.finite(p_values) & !is.na(p_values) & p_values <= seuil_p
      stats_df <- stats_df[keep, , drop = FALSE]
      stats_df$p_interactif <- p_values[keep]
    } else {
      stats_df <- stats_df[0, , drop = FALSE]
    }

    if (nrow(stats_df) > 0) {
      frequency <- if ("frequency" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$frequency)) else rep(0, nrow(stats_df))
      stats_df <- stats_df[order(-frequency, na.last = TRUE), , drop = FALSE]
      if (is.finite(top_termes) && nrow(stats_df) > top_termes) {
        stats_df <- stats_df[seq_len(top_termes), , drop = FALSE]
      }

      for (i in seq_len(nrow(stats_df))) {
        term <- as.character(stats_df$Terme[i])
        coord_index <- match(tolower(term), tolower(rownames(termes_xy)))
        if (is.na(coord_index)) next
        chi2 <- if ("chi2" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$chi2[i])) else NA_real_
        freq <- if ("frequency" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$frequency[i])) else NA_real_
        classe <- if ("Classe_max" %in% names(stats_df)) as.character(stats_df$Classe_max[i]) else ""
        termes[[length(termes) + 1L]] <- list(
          label = term,
          classe = classe,
          x = termes_xy$x[coord_index],
          y = termes_xy$y[coord_index],
          chi2 = chi2,
          p_value = stats_df$p_interactif[i],
          frequency = freq
        )
      }
    }
  }

  list(
    version = 1L,
    seuil_p = seuil_p,
    axes = list(x = "Axe 1", y = "Axe 2"),
    classes = classes,
    termes = termes
  )
}

ecrire_graph_interactif_afc <- function(
    coords_classes_file,
    coords_termes_file,
    stats_termes_file,
    output_file,
    seuil_p = 0.05,
    top_termes = 120L
) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Le package jsonlite est requis pour le graphe AFC interactif.")
  }
  payload <- construire_donnees_graph_interactif_afc(
    coords_classes_file = coords_classes_file,
    coords_termes_file = coords_termes_file,
    stats_termes_file = stats_termes_file,
    seuil_p = seuil_p,
    top_termes = top_termes
  )
  dir.create(dirname(output_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, output_file, auto_unbox = TRUE, pretty = FALSE, na = "null")
  invisible(output_file)
}

# Second renderer: a Leaflet map using the AFC plane as an abstract map.
# It does not alter the CHD/AFC calculations or the official PNG exports.
ecrire_graph_interactif_leaflet_afc <- function(
    coords_classes_file,
    coords_termes_file,
    stats_termes_file,
    output_file,
    seuil_p = 0.05,
    top_termes = 120L
) {
  if (!requireNamespace("leaflet", quietly = TRUE)) {
    stop("Le package leaflet est requis pour la carte AFC interactive.")
  }
  if (!requireNamespace("htmlwidgets", quietly = TRUE)) {
    stop("Le package htmlwidgets est requis pour la carte AFC interactive.")
  }

  payload <- construire_donnees_graph_interactif_afc(
    coords_classes_file = coords_classes_file,
    coords_termes_file = coords_termes_file,
    stats_termes_file = stats_termes_file,
    seuil_p = seuil_p,
    top_termes = top_termes
  )

  echapper_html <- function(value) {
    htmltools::htmlEscape(ifelse(is.na(value), "", as.character(value)))
  }
  classes_df <- if (length(payload$classes)) {
    do.call(rbind, lapply(payload$classes, function(row) {
      data.frame(label = row$label, x = as.numeric(row$x), y = as.numeric(row$y), stringsAsFactors = FALSE)
    }))
  } else data.frame(label = character(), x = numeric(), y = numeric())
  termes_df <- if (length(payload$termes)) {
    do.call(rbind, lapply(payload$termes, function(row) {
      data.frame(
        label = row$label,
        classe = row$classe,
        x = as.numeric(row$x),
        y = as.numeric(row$y),
        chi2 = as.numeric(row$chi2),
        p_value = as.numeric(row$p_value),
        stringsAsFactors = FALSE
      )
    }))
  } else data.frame(label = character(), classe = character(), x = numeric(), y = numeric(), chi2 = numeric(), p_value = numeric())

  palette <- c("#5b8c85", "#6f86b5", "#d77a57", "#9a78a8", "#c49a4a", "#4c8caa", "#bd6470", "#6b9b63")
  class_levels <- unique(c(classes_df$label, termes_df$classe))
  class_colors <- setNames(rep(palette, length.out = length(class_levels)), class_levels)
  termes_df$couleur <- unname(class_colors[termes_df$classe])
  termes_df$couleur[is.na(termes_df$couleur)] <- "#5b6570"

  popup_terme <- sprintf(
    "<strong>%s</strong><br>Classe : %s<br>x : %s<br>y : %s<br>χ² : %s<br>p.value : %s",
    echapper_html(termes_df$label),
    echapper_html(termes_df$classe),
    formatC(termes_df$x, format = "f", digits = 4),
    formatC(termes_df$y, format = "f", digits = 4),
    ifelse(is.finite(termes_df$chi2), formatC(termes_df$chi2, format = "f", digits = 3), "indisponible"),
    ifelse(is.finite(termes_df$p_value), formatC(termes_df$p_value, format = "e", digits = 3), "indisponible")
  )
  termes_df$label_html <- sprintf(
    "<span style=\"color:%s;font-weight:600;text-shadow:0 1px 2px rgba(255,255,255,.85)\">%s</span>",
    termes_df$couleur,
    sprintf("%s — %s", echapper_html(termes_df$label), echapper_html(termes_df$classe))
  )

  carte <- leaflet::leaflet(options = leaflet::leafletOptions(
    crs = leaflet::leafletCRS(crsClass = "L.CRS.Simple"),
    minZoom = -4,
    maxZoom = 10,
    zoomControl = TRUE,
    attributionControl = FALSE
  ))
  if (nrow(classes_df)) {
    carte <- carte |>
      leaflet::addCircleMarkers(
        data = classes_df,
        lng = ~x,
        lat = ~y,
        radius = 7,
        color = "#1f2a33",
        fillColor = "#ffffff",
        fillOpacity = 1,
        weight = 2,
        label = ~label,
        popup = ~sprintf("<strong>%s</strong><br>x : %.4f<br>y : %.4f", echapper_html(label), x, y),
        group = "Classes"
      )
  }
  if (nrow(termes_df)) {
    carte <- carte |>
      leaflet::addLabelOnlyMarkers(
        data = termes_df,
        lng = ~x,
        lat = ~y,
        label = ~label_html,
        popup = popup_terme,
        labelOptions = leaflet::labelOptions(
          noHide = TRUE,
          textOnly = TRUE,
          direction = "center",
          style = list(
            "color" = "#5b6570",
            "font-size" = "13px",
            "font-weight" = "600",
            "text-shadow" = "0 1px 2px rgba(255,255,255,.85)"
          )
        ),
        group = "Termes significatifs"
      )
  }
  if (nrow(termes_df) || nrow(classes_df)) {
    x_all <- c(classes_df$x, termes_df$x)
    y_all <- c(classes_df$y, termes_df$y)
    marge_x <- max(0.1, diff(range(x_all, finite = TRUE)) * 0.08)
    marge_y <- max(0.1, diff(range(y_all, finite = TRUE)) * 0.08)
    carte <- carte |>
      leaflet::addPolylines(
        lng = c(min(x_all) - marge_x, max(x_all) + marge_x),
        lat = c(0, 0),
        color = "#c9cdd1",
        weight = 1,
        opacity = 0.9,
        group = "Axes AFC"
      ) |>
      leaflet::addPolylines(
        lng = c(0, 0),
        lat = c(min(y_all) - marge_y, max(y_all) + marge_y),
        color = "#c9cdd1",
        weight = 1,
        opacity = 0.9,
        group = "Axes AFC"
      )
  }
  carte <- carte |>
    htmlwidgets::onRender("function(el, x) {
      var map = this;
      var group = map.layerManager.getLayerGroup('Termes significatifs', true);
      if (!group) return;

      function overlaps(a, b, gap) {
        return !(a.right + gap < b.left || a.left - gap > b.right ||
          a.bottom + gap < b.top || a.top - gap > b.bottom);
      }

      function arrangeLabels() {
        var labels = [];
        group.eachLayer(function(layer) {
          if (layer._icon) labels.push(layer._icon);
        });
        labels.forEach(function(icon) {
          var match = icon.style.transform.match(/translate3d\\([^)]*\\)/);
          icon.dataset.afcBaseTransform = match ? match[0] : icon.style.transform;
          icon.style.transform = icon.dataset.afcBaseTransform || '';
        });

        var placed = [];
        labels.sort(function(a, b) {
          return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
        });
        labels.forEach(function(icon) {
          var base = icon.dataset.afcBaseTransform || '';
          var rect = icon.getBoundingClientRect();
          var candidates = [[0, 0], [0, -rect.height - 6], [0, rect.height + 6],
            [rect.width + 8, 0], [-rect.width - 8, 0],
            [rect.width + 8, -rect.height - 6], [-rect.width - 8, -rect.height - 6]];
          var chosen = candidates[0];
          for (var i = 0; i < candidates.length; i += 1) {
            var dx = candidates[i][0];
            var dy = candidates[i][1];
            var candidate = {
              left: rect.left + dx,
              right: rect.right + dx,
              top: rect.top + dy,
              bottom: rect.bottom + dy
            };
            if (!placed.some(function(previous) { return overlaps(candidate, previous, 3); })) {
              chosen = candidates[i];
              break;
            }
          }
          icon.style.transform = base + ' translate(' + chosen[0] + 'px,' + chosen[1] + 'px)';
          var finalRect = icon.getBoundingClientRect();
          placed.push({left: finalRect.left, right: finalRect.right, top: finalRect.top, bottom: finalRect.bottom});
        });
      }

      var scheduled = false;
      function scheduleArrange() {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(function() {
          scheduled = false;
          arrangeLabels();
        });
      }
      map.on('zoomend moveend resize', scheduleArrange);
      scheduleArrange();
    }")
  carte <- carte |>
    leaflet::addLayersControl(
      overlayGroups = c("Classes", "Termes significatifs", "Axes AFC"),
      options = leaflet::layersControlOptions(collapsed = FALSE)
    )
  if (nrow(termes_df) || nrow(classes_df)) {
    x_all <- c(classes_df$x, termes_df$x)
    y_all <- c(classes_df$y, termes_df$y)
    carte <- carte |> leaflet::fitBounds(min(x_all), min(y_all), max(x_all), max(y_all))
  }
  dir.create(dirname(output_file), recursive = TRUE, showWarnings = FALSE)
  htmlwidgets::saveWidget(carte, output_file, selfcontained = TRUE)
  invisible(output_file)
}
