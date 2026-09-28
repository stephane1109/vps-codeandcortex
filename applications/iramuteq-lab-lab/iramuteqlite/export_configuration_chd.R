# Exporte la configuration demandee et la configuration effectivement retenue par la CHD.

.chd_config_scalar <- function(value) {
  if (is.null(value) || !length(value)) return(NULL)
  if (is.factor(value)) value <- as.character(value)
  if (length(value) == 1L) return(value[[1]])
  as.list(value)
}

.chd_config_row_to_list <- function(row) {
  if (is.null(row) || !is.data.frame(row) || !nrow(row)) return(NULL)
  lapply(row[1, , drop = FALSE], .chd_config_scalar)
}

.chd_config_reproduction <- function(config_effective, selection) {
  replay <- config_effective
  if (is.null(selection) || !is.list(selection)) return(replay)

  selected_metrics <- selection$selected_metrics
  selected_k <- suppressWarnings(as.integer(
    selection$selected_result$auto_selection$k_chd_selected %||%
      if (is.data.frame(selected_metrics) && nrow(selected_metrics)) selected_metrics$k_chd_retenu[[1]] else NULL %||%
      if (is.data.frame(selected_metrics) && nrow(selected_metrics)) selected_metrics$k_retenu[[1]] else NULL
  ))
  if (!length(selected_k) || is.na(selected_k) || !is.finite(selected_k)) selected_k <- NULL

  replay$iramuteq_classes_mode <- "manuel"
  if (!is.null(selected_k)) replay$k_iramuteq <- selected_k
  champs_exploration <- c(
    "iramuteq_discrimination_simple_profile",
    "iramuteq_discrimination_simple_vary_mincl",
    "iramuteq_discrimination_simple_mincl_min",
    "iramuteq_discrimination_simple_mincl_max",
    "iramuteq_discrimination_simple_vary_min_docfreq",
    "iramuteq_discrimination_simple_min_docfreq_min",
    "iramuteq_discrimination_simple_min_docfreq_max",
    "iramuteq_discrimination_simple_vary_k_max",
    "iramuteq_discrimination_simple_k_max_min",
    "iramuteq_discrimination_simple_k_max_max",
    "iramuteq_discrimination_simple_score_mode"
  )
  replay[champs_exploration] <- NULL
  replay
}

.write_chd_configuration_atomic <- function(payload, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  temp_path <- tempfile(
    pattern = paste0(".", basename(path), "-"),
    tmpdir = dirname(path),
    fileext = ".tmp"
  )
  on.exit(unlink(temp_path, force = TRUE), add = TRUE)
  jsonlite::write_json(payload, temp_path, auto_unbox = TRUE, pretty = TRUE, null = "null", na = "null")
  if (!file.rename(temp_path, path)) {
    stop(paste0("Impossible de publier la configuration CHD : ", path))
  }
  path
}

exporter_configuration_chd_iramuteq <- function(config_requested,
                                                 classes_mode,
                                                 classes_mode_label,
                                                 classes_info,
                                                 classes,
                                                 input_path,
                                                 corpus_md5,
                                                 output_dir) {
  selection <- classes_info$simple_discriminant_selection %||% NULL
  config_effective <- if (is.list(selection) && is.list(selection$selected_candidate$config)) {
    selection$selected_candidate$config
  } else {
    config_requested
  }
  config_reproduction <- .chd_config_reproduction(config_effective, selection)
  classes_valides <- suppressWarnings(as.integer(classes))
  classes_valides <- classes_valides[is.finite(classes_valides) & !is.na(classes_valides) & classes_valides > 0L]
  effectifs <- if (length(classes_valides)) table(classes_valides) else integer(0)

  selected_metrics <- if (is.list(selection)) .chd_config_row_to_list(selection$selected_metrics) else NULL
  payload <- list(
    format = "iramuteq-lab-configuration-chd",
    version_format = 1L,
    genere_le = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    corpus = list(
      fichier = basename(input_path),
      md5 = as.character(corpus_md5 %||% "")
    ),
    analyse = list(
      type = "CHD",
      mode = as.character(classes_mode %||% "manuel"),
      mode_libelle = as.character(classes_mode_label %||% "Normal")
    ),
    resultat = list(
      nombre_classes = length(unique(classes_valides)),
      effectifs_classes = as.list(stats::setNames(as.integer(effectifs), paste0("Classe ", names(effectifs)))),
      mincl_applique = .chd_config_scalar(classes_info$mincl %||% NULL),
      configuration_retenue = selected_metrics
    ),
    configuration_demandee = config_requested,
    configuration_effective = config_effective,
    configuration_reproduction_mode_normal = config_reproduction,
    environnement = list(
      version_r = R.version.string,
      version_iramuteq_lab = "0_5beta"
    )
  )

  output_path <- file.path(output_dir, "configuration_chd.json")
  .write_chd_configuration_atomic(payload, output_path)
}
