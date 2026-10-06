# Rôle du fichier: assurer la compatibilité avec les anciennes configurations.

normaliser_mode_stats_chd_iramuteq <- function(mode) {
  # Le calcul vectorisé reproduit le même chi2 que chisq.test sans la boucle
  # terme par terme. L'argument est conservé pour relire les anciens exports.
  "vectorise"
}
