# Vérifie que l'optimisation des étiquettes AFC conserve les positions
# de l'algorithme historique, sans toucher aux coordonnées de l'AFC.

source(file.path("iramuteqlite", "afc_iramuteq.R"))

placement_reference <- function(x, y, labels, cex_vec, max_iter = 220) {
  x2 <- x
  y2 <- y
  usr <- par("usr")
  rx <- usr[2] - usr[1]
  ry <- usr[4] - usr[3]
  pas <- 0.012 * max(rx, ry)
  rects <- vector("list", length(labels))
  for (i in seq_along(labels)) {
    wi <- strwidth(labels[i], units = "user", cex = cex_vec[i])
    hi <- strheight(labels[i], units = "user", cex = cex_vec[i])
    if (!is.finite(wi) || wi == 0) wi <- 0.02 * rx
    if (!is.finite(hi) || hi == 0) hi <- 0.02 * ry
    rectangle <- function(xc, yc) {
      list(xmin = xc - wi / 2, xmax = xc + wi / 2,
           ymin = yc - hi / 2, ymax = yc + hi / 2)
    }
    candidate <- rectangle(x[i], y[i])
    collision <- function(r) {
      if (i == 1L) return(FALSE)
      any(vapply(rects[seq_len(i - 1L)], function(pr) {
        !(r$xmax < pr$xmin || pr$xmax < r$xmin ||
          r$ymax < pr$ymin || pr$ymax < r$ymin)
      }, logical(1)))
    }
    if (collision(candidate)) {
      angle <- 0
      rayon <- pas
      for (k in seq_len(max_iter)) {
        angle <- angle + 0.65
        rayon <- rayon + pas * 0.15
        xi <- x[i] + rayon * cos(angle)
        yi <- y[i] + rayon * sin(angle)
        r2 <- rectangle(xi, yi)
        if (!collision(r2)) {
          x2[i] <- xi
          y2[i] <- yi
          candidate <- r2
          break
        }
      }
    }
    rects[[i]] <- candidate
  }
  list(x = x2, y = y2)
}

fichier_graphique <- tempfile(fileext = ".pdf")
grDevices::pdf(fichier_graphique, width = 10, height = 8)
on.exit <- NULL
plot(0, 0, type = "n", xlim = c(-1, 1), ylim = c(-1, 1))
x <- c(0, 0.002, 0.02, 0.01, 0.09, -0.1)
y <- c(0, 0.001, 0.02, -0.01, 0.09, 0.05)
noms <- c("violence", "manifestation", "journaliste", "représentation", "image", "discours")
tailles <- c(1, 1, 1.2, 1, 0.9, 1.1)
reference <- placement_reference(x, y, noms, tailles)
rapide <- placer_labels_sans_chevauchement_spirale(x, y, noms, tailles)
memoire <- placer_labels_sans_chevauchement_spirale(x, y, noms, tailles)
stopifnot(isTRUE(all.equal(reference$x, rapide$x, tolerance = 1e-12)))
stopifnot(isTRUE(all.equal(reference$y, rapide$y, tolerance = 1e-12)))
stopifnot(identical(rapide, memoire))
stopifnot(identical(x, c(0, 0.002, 0.02, 0.01, 0.09, -0.1)))
stopifnot(identical(y, c(0, 0.001, 0.02, -0.01, 0.09, 0.05)))
grDevices::dev.off()
unlink(fichier_graphique)
cat("Placement AFC vectorisé et mémoïsé : OK\n")
