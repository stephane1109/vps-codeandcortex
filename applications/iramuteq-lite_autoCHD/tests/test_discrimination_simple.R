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

grid_base_config <- list(
  iramuteq_discrimination_simple_profile = "ciblee",
  morpho_conserver_hors_lexique = TRUE,
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
  k_iramuteq = 3L
)

grid_with_autre_forme <- construire_grille_discrimination_simple_iramuteq(c(
  grid_base_config,
  list(iramuteq_discrimination_simple_vary_autre_forme = TRUE)
))
autre_forme_values <- vapply(
  grid_with_autre_forme$candidates,
  function(candidate) isTRUE(candidate$autre_forme),
  logical(1)
)
pipeline_autre_forme_values <- vapply(
  grid_with_autre_forme$candidates,
  function(candidate) isTRUE(candidate$config$morpho_conserver_hors_lexique),
  logical(1)
)
stopifnot(
  length(grid_with_autre_forme$candidates) == 2L,
  identical(unname(autre_forme_values), c(FALSE, TRUE)),
  identical(unname(pipeline_autre_forme_values), c(FALSE, TRUE))
)

grid_fixed_autre_forme <- construire_grille_discrimination_simple_iramuteq(c(
  grid_base_config,
  list(iramuteq_discrimination_simple_vary_autre_forme = FALSE)
))
stopifnot(
  length(grid_fixed_autre_forme$candidates) == 1L,
  isTRUE(grid_fixed_autre_forme$candidates[[1]]$autre_forme)
)

default_grid_config <- grid_base_config
default_grid_config$iramuteq_discrimination_simple_vary_min_docfreq <- TRUE
default_grid_config$iramuteq_discrimination_simple_vary_k_max <- TRUE
default_grid_config$iramuteq_discrimination_simple_vary_autre_forme <- TRUE
default_grid_config$iramuteq_discrimination_simple_k_max_max <- 10L
default_grid <- construire_grille_discrimination_simple_iramuteq(default_grid_config)
stopifnot(length(default_grid$candidates) == 64L)

public_metrics <- .preparer_metrics_export_discrimination_simple(data.frame(
  autre_forme = "oui",
  k_retenu = 4L,
  k_chd_retenu = 4L,
  S = score$S
))
stopifnot(
  abs(public_metrics$separation_afc[[1]] - score$S) < 1e-9,
  identical(public_metrics$autre_forme[[1]], "oui"),
  !("separation_minimale_afc" %in% names(public_metrics))
)

cat("test_discrimination_simple.R: OK\n")
