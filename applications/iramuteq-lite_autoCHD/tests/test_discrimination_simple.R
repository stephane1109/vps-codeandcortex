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

public_metrics <- .preparer_metrics_export_discrimination_simple(data.frame(
  k_retenu = 4L,
  k_chd_retenu = 4L,
  S = score$S
))
stopifnot(
  abs(public_metrics$separation_afc[[1]] - score$S) < 1e-9,
  !("separation_minimale_afc" %in% names(public_metrics))
)

cat("test_discrimination_simple.R: OK\n")
