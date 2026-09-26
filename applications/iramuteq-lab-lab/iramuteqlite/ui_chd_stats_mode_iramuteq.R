# Rôle du fichier: centraliser le mode de calcul des statistiques CHD (UI + normalisation).

choix_mode_stats_chd_iramuteq <- function() {
  c(
    "Mode optimisé (vectorisé, recommandé)" = "vectorise",
    "Mode classique (chisq.test par terme)" = "classique"
  )
}

normaliser_mode_stats_chd_iramuteq <- function(mode) {
  mode_chr <- tolower(trimws(as.character(mode)))
  if (!length(mode_chr) || is.na(mode_chr[[1]]) || !nzchar(mode_chr[[1]])) {
    return("vectorise")
  }
  mode_chr <- mode_chr[[1]]
  if (!mode_chr %in% c("vectorise", "classique")) {
    return("vectorise")
  }
  mode_chr
}
