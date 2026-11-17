# Représentation facultative des plans factoriels avec ggplot2 et ggrepel.
# Les coordonnées et les résultats statistiques sont calculés par FactoMineR.

dessiner_plan_ggrepel <- function(
  points, couleurs, formes, titre, axe_x, axe_y,
  limites_x, limites_y, note = NULL,
  titre_couleurs = "Variables", titre_formes = "Statut"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE) ||
      !requireNamespace("ggrepel", quietly = TRUE)) {
    stop("Les packages ggplot2 et ggrepel sont nécessaires aux plans sans chevauchement.")
  }
  # L'ordre des légendes est stable, même lorsque le filtre masque des modalités.
  points$variable <- factor(points$variable, levels = names(couleurs))
  points$type <- factor(points$type, levels = names(formes))
  graphique <- ggplot2::ggplot(
    points, ggplot2::aes(x = x, y = y, colour = variable, shape = type)
  ) +
    ggplot2::geom_hline(yintercept = 0, colour = "grey75", linetype = "dashed") +
    ggplot2::geom_vline(xintercept = 0, colour = "grey75", linetype = "dashed") +
    ggplot2::geom_point(ggplot2::aes(size = taille), na.rm = TRUE) +
    ggrepel::geom_text_repel(
      ggplot2::aes(label = libelle),
      size = 2.8, seed = 42L, max.overlaps = Inf,
      max.time = 0.8, max.iter = 2000L,
      box.padding = 0.3, point.padding = 0.15,
      min.segment.length = 0, segment.colour = "grey60",
      segment.size = 0.25, show.legend = FALSE, na.rm = TRUE
    ) +
    ggplot2::scale_colour_manual(
      values = couleurs, name = titre_couleurs, drop = TRUE
    ) +
    ggplot2::scale_shape_manual(
      values = formes, name = titre_formes, drop = TRUE
    ) +
    ggplot2::scale_size_identity() +
    ggplot2::coord_cartesian(
      xlim = limites_x, ylim = limites_y, clip = "off"
    ) +
    ggplot2::labs(
      title = titre, x = axe_x, y = axe_y, caption = note
    ) +
    ggplot2::theme_minimal(base_size = 12) +
    ggplot2::theme(
      panel.grid.minor = ggplot2::element_blank(),
      legend.position = "right",
      legend.text = ggplot2::element_text(size = 8),
      legend.title = ggplot2::element_text(size = 9),
      plot.title = ggplot2::element_text(size = 12),
      plot.caption = ggplot2::element_text(size = 8),
      plot.margin = ggplot2::margin(12, 22, 12, 12)
    )
  print(graphique)
}
