source("iramuteqlite/autoCHD.R")
source("iramuteqlite/discriminationsimple.R")

# Four lexical poles: classes 1 and 2 are close, while 3 and 4 are distinct.
coords <- matrix(
  c(
    -0.1, 0, 0.1, 0,
    0.3, 0, 0.5, 0,
    4.9, 0, 5.1, 0,
    0, 4.9, 0, 5.1
  ),
  ncol = 2,
  byrow = TRUE,
  dimnames = list(
    c("a1", "a2", "b1", "b2", "c1", "c2", "d1", "d2"),
    c("x", "y")
  )
)

stats <- data.frame(
  Terme = rownames(coords),
  Classe = rep(1:4, each = 2),
  chi2 = rep(10, 8),
  p = rep(0.01, 8)
)

score <- calculer_score_discrimination_simple_iramuteq(
  afc_obj = list(colcoord = coords),
  res_stats_df = stats
)

stopifnot(
  abs(score$S - 12.5) < 1e-9,
  !("S_separation_robuste" %in% names(score)),
  !("S_separation_min" %in% names(score))
)

# The direct criterion must use the actual AFC class coordinates, without
# reconstructing lexical centres from the term coordinates.
class_coords <- matrix(
  c(
    0, 0,
    3, 4,
    0, 8
  ),
  ncol = 2,
  byrow = TRUE,
  dimnames = list(c("Classe 1", "Classe 2", "Classe 3"), c("Dim.1", "Dim.2"))
)
direct_score <- calculer_score_classes_direct_afc_iramuteq(
  afc_obj = list(rowcoord = class_coords)
)
stopifnot(
  abs(direct_score$value - 5) < 1e-9,
  length(direct_score$distances_by_pair) == 3L,
  normaliser_mode_score_discrimination_simple_iramuteq(NULL) == "afc_classes_direct",
  normaliser_mode_score_discrimination_simple_iramuteq(NA_character_) == "afc_classes_direct",
  normaliser_mode_score_discrimination_simple_iramuteq("afc_classes_direct") == "afc_classes_direct",
  etiquette_mode_score_discrimination_simple_iramuteq("afc_classes_direct") == "Distance directe des classes AFC"
)

axis_terms <- extraire_mots_reperes_axes_discrimination_simple_iramuteq(
  afc_obj = list(colcoord = coords),
  res_stats_df = stats,
  top_n = 1L
)
stopifnot(
  nrow(axis_terms) == 4L,
  all(axis_terms$terme %in% c("a1", "b2", "c2", "d2")),
  all(axis_terms$axe_dominant %in% c("Axe 1", "Axe 2")),
  all(axis_terms$amplitude > 0)
)

grid_base_config <- list(
  iramuteq_discrimination_simple_profile = "ciblee",
  morpho_conserver_hors_lexique = FALSE,
  iramuteq_discrimination_simple_vary_mincl = FALSE,
  iramuteq_discrimination_simple_mincl_min = 5L,
  iramuteq_discrimination_simple_mincl_max = 10L,
  iramuteq_mincl = 5L,
  iramuteq_mincl_mode = "manuel",
  iramuteq_discrimination_simple_vary_min_docfreq = FALSE,
  iramuteq_discrimination_simple_min_docfreq_min = 2L,
  iramuteq_discrimination_simple_min_docfreq_max = 5L,
  min_docfreq = 3L,
  iramuteq_discrimination_simple_vary_k_max = FALSE,
  iramuteq_discrimination_simple_k_max_min = 3L,
  iramuteq_discrimination_simple_k_max_max = 3L,
  iramuteq_discrimination_simple_score_mode = "afc_classes_direct",
  k_iramuteq = 3L
)

targeted_grid <- construire_grille_discrimination_simple_iramuteq(grid_base_config)
stopifnot(
  length(targeted_grid$candidates) == 1L,
  isTRUE(targeted_grid$candidates[[1]]$config$morpho_conserver_hors_lexique),
  grepl("AUTRE_FORME", targeted_grid$candidates[[1]]$profil_morpho, fixed = TRUE),
  targeted_grid$candidates[[1]]$config$iramuteq_discrimination_simple_score_mode == "afc_classes_direct"
)

default_grid_config <- grid_base_config
default_grid_config$iramuteq_discrimination_simple_vary_min_docfreq <- TRUE
default_grid_config$iramuteq_discrimination_simple_vary_k_max <- TRUE
default_grid_config$iramuteq_discrimination_simple_k_max_max <- 10L
default_grid <- construire_grille_discrimination_simple_iramuteq(default_grid_config)
stopifnot(length(default_grid$candidates) == 32L)

public_metrics <- .preparer_metrics_export_discrimination_simple(data.frame(
  k_retenu = 4L,
  k_chd_retenu = 4L,
  S = score$S,
  distance_classes_afc = direct_score$value,
  score_mode = "afc_classes_direct",
  score_label = "Distance directe des classes AFC",
  score_selection = direct_score$value
))
stopifnot(
  abs(public_metrics$score_s_lexical[[1]] - score$S) < 1e-9,
  abs(public_metrics$distance_classes_afc[[1]] - direct_score$value) < 1e-9,
  abs(public_metrics$separation_afc[[1]] - direct_score$value) < 1e-9,
  public_metrics$score_mode[[1]] == "afc_classes_direct",
  !("separation_minimale_afc" %in% names(public_metrics))
)

cat("test_discrimination_simple.R: OK\n")
