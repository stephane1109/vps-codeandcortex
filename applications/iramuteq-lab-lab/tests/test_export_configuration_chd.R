`%||%` <- function(x, y) {
  if (is.null(x) || !length(x)) y else x
}

args_all <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", grep("^--file=", args_all, value = TRUE)[[1]])
app_dir <- normalizePath(file.path(dirname(file_arg), ".."), winslash = "/", mustWork = TRUE)
source(file.path(app_dir, "iramuteqlite", "export_configuration_chd.R"), local = TRUE)

output_dir <- tempfile("configuration-chd-test-")
dir.create(output_dir, recursive = TRUE)
on.exit(unlink(output_dir, recursive = TRUE, force = TRUE), add = TRUE)

requested <- list(
  iramuteq_classes_mode = "discrimination_simple",
  k_iramuteq = 10L,
  min_docfreq = 3L
)
effective <- requested
effective$min_docfreq <- 2L
effective$k_iramuteq <- 7L

selection <- list(
  selected_candidate = list(config = effective),
  selected_metrics = data.frame(
    configuration_id = "CFG005",
    k_retenu = 4L,
    k_chd_retenu = 7L,
    score_selection = 2.75,
    stringsAsFactors = FALSE
  ),
  selected_result = list(auto_selection = list(k_chd_selected = 7L))
)

path <- exporter_configuration_chd_iramuteq(
  config_requested = requested,
  classes_mode = "discrimination_simple",
  classes_mode_label = "CHD distance optimisée",
  classes_info = list(mincl = 5L, simple_discriminant_selection = selection),
  classes = c(1L, 1L, 2L, 3L),
  input_path = "corpus-test.txt",
  corpus_md5 = "abc123",
  output_dir = output_dir
)

stopifnot(file.exists(path))
payload <- jsonlite::fromJSON(path, simplifyVector = FALSE)
stopifnot(identical(payload$corpus$md5, "abc123"))
stopifnot(identical(payload$resultat$nombre_classes, 3L))
stopifnot(identical(payload$configuration_effective$min_docfreq, 2L))
stopifnot(identical(payload$configuration_reproduction_mode_normal$iramuteq_classes_mode, "manuel"))
stopifnot(identical(payload$configuration_reproduction_mode_normal$k_iramuteq, 7L))
stopifnot(identical(payload$environnement$version_iramuteq_lab, "0_6beta"))

normal_dir <- file.path(output_dir, "normal")
normal_config <- list(
  iramuteq_classes_mode = "manuel",
  k_iramuteq = 5L,
  min_docfreq = 4L
)
normal_path <- exporter_configuration_chd_iramuteq(
  config_requested = normal_config,
  classes_mode = "manuel",
  classes_mode_label = "Normal",
  classes_info = list(mincl = 5L, simple_discriminant_selection = NULL),
  classes = c(1L, 1L, 2L),
  input_path = "corpus-normal.txt",
  corpus_md5 = "normal123",
  output_dir = normal_dir
)
normal_payload <- jsonlite::fromJSON(normal_path, simplifyVector = FALSE)
stopifnot(identical(normal_payload$configuration_demandee, normal_payload$configuration_effective))
stopifnot(identical(normal_payload$resultat$nombre_classes, 2L))

cat("test_export_configuration_chd: OK\n")
