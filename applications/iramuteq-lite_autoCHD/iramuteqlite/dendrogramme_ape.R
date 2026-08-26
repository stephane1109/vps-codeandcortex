# Rôle du fichier: rendu dendrogramme CHD via le package ape.

tracer_dendrogramme_ape <- function(hc,
                                    orientation = c("vertical", "horizontal"),
                                    main = "Dendrogramme CHD (ape)") {
  orientation <- match.arg(orientation)
  if (is.null(hc) || !inherits(hc, "hclust")) return(FALSE)
  if (!requireNamespace("ape", quietly = TRUE)) return(FALSE)

  phy <- tryCatch(ape::as.phylo(hc), error = function(e) NULL)
  if (is.null(phy)) return(FALSE)

  tryCatch({
    if (identical(orientation, "horizontal")) {
      ape::plot.phylo(
        phy,
        type = "phylogram",
        direction = "rightwards",
        show.tip.label = TRUE,
        cex = 0.78,
        main = main,
        no.margin = TRUE
      )
    } else {
      ape::plot.phylo(
        phy,
        type = "phylogram",
        direction = "upwards",
        show.tip.label = TRUE,
        cex = 0.78,
        main = main,
        no.margin = TRUE
      )
    }
    TRUE
  }, error = function(e) FALSE)
}
