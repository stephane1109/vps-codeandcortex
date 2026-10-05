#!/usr/bin/env Rscript

suppressWarnings(options(stringsAsFactors = FALSE))
invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))

script_path <- local({
  args_all <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args_all, value = TRUE)
  if (!length(file_arg)) return("")
  sub("^--file=", "", file_arg[[1]])
})

runner_dir <- if (nzchar(script_path)) {
  normalizePath(dirname(script_path), winslash = "/", mustWork = TRUE)
} else {
  normalizePath(file.path(getwd(), "backend", "r"), winslash = "/", mustWork = TRUE)
}

source(file.path(runner_dir, "pipeline_utilitaires.R"), local = TRUE)
repo_root <- normalizePath(file.path(dirname(script_path %||% ""), "..", ".."), winslash = "/", mustWork = FALSE)
if (!dir.exists(file.path(repo_root, "iramuteqlite"))) {
  repo_root <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

required_packages <- c(
  "jsonlite", "quanteda", "Matrix", "dplyr", "wordcloud", "RColorBrewer",
  "FactoMineR", "igraph", "proxy", "htmltools", "htmlwidgets", "factoextra"
)
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, quietly = TRUE, logical(1))]
if (length(missing_packages)) {
  stop(paste("Packages R manquants:", paste(missing_packages, collapse = ", ")))
}

source(file.path(repo_root, "iramuteqlite", "nettoyage_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "chd_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "autoCHD.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "discriminationsimple.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "chd_engine_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "iramuteq_bars.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "dendrogramme_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "afc_helpers_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "variables_etoilees.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "afc_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "afc_extremes.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "graph_interactif.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "wordcloud_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "concordancier-iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi_graph.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi_igraph.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "stats_chd.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "ui_chd_stats_mode_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "export_configuration_chd.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "calcul_specificites.R"), local = TRUE)
source(file.path(runner_dir, "pipeline_corpus.R"), local = TRUE)
source(file.path(runner_dir, "pipeline_pretraitement.R"), local = TRUE)
source(file.path(runner_dir, "pipeline_exports.R"), local = TRUE)
args <- parse_args(commandArgs(trailingOnly = TRUE))
input_path <- normalizePath(scalar_chr(args$input), winslash = "/", mustWork = TRUE)
config_path <- normalizePath(scalar_chr(args$config), winslash = "/", mustWork = TRUE)
output_dir <- normalizePath(scalar_chr(args[["output-dir"]]), winslash = "/", mustWork = FALSE)
status_file <- normalizePath(scalar_chr(args[["status-file"]]), winslash = "/", mustWork = FALSE)
results_file <- normalizePath(scalar_chr(args[["results-file"]]), winslash = "/", mustWork = FALSE)

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(results_file), recursive = TRUE, showWarnings = FALSE)

job_logs <- character(0)

run_batch <- function() {
  config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)
  analyses <- config$analyses %||% list(chd = TRUE, afc = TRUE, simi = TRUE)
  run_chd <- scalar_bool(analyses$chd, TRUE) || scalar_bool(analyses$afc, TRUE)
  run_afc <- scalar_bool(analyses$afc, TRUE)
  run_simi <- scalar_bool(analyses$simi, TRUE)

  artifacts <- list()

  write_status(state = "running", progress = 3, message = "Initialisation du runner batch.")
  log_info(paste0("output_dir = ", output_dir), progress = 4)
  log_info("Import du corpus.", progress = 8)
  corpus_md5 <- unname(tools::md5sum(input_path))
  log_info(paste0("MD5 fichier = ", corpus_md5), progress = 9)
  corpus_importe <- import_corpus_iramuteq(input_path)
  log_info(paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_importe)), progress = 10)

  classif_mode <- scalar_chr(config$iramuteq_classif_mode, "simple")
  if (!classif_mode %in% c("simple", "double")) classif_mode <- "simple"
  requested_classes_mode <- scalar_chr(config$iramuteq_classes_mode, "manuel")
  legacy_classes_mode <- !requested_classes_mode %in% c("manuel", "discrimination_simple")
  classes_mode <- if (legacy_classes_mode) "manuel" else requested_classes_mode
  engine_classes_mode <- switch(
    classes_mode,
    discrimination_simple = "discrimination_simple_config",
    classes_mode
  )
  classes_mode_label <- switch(
    classes_mode,
    discrimination_simple = "CHD Opposition optimisée",
    "Normal"
  )
  config_chd <- config
  auto_discriminant_score_mode <- scalar_chr(config$iramuteq_discrimination_simple_score_mode, "afc_classes_direct")
  if (!auto_discriminant_score_mode %in% c("s_lexical", "afc_classes_direct")) {
    auto_discriminant_score_mode <- "afc_classes_direct"
  }
  auto_discriminant_score_label <- if (identical(auto_discriminant_score_mode, "afc_classes_direct")) {
    "Distance directe des classes AFC"
  } else {
    "Score S lexical"
  }
  if (identical(classes_mode, "discrimination_simple")) {
    config_chd$iramuteq_classes_mode <- "discrimination_simple_config"
    config_chd$iramuteq_discrimination_simple_profile <- scalar_chr(config$iramuteq_discrimination_simple_profile, "ciblee")
    config_chd$iramuteq_auto_top_n_afc <- NULL
    config_chd$iramuteq_discrimination_simple_score_mode <- auto_discriminant_score_mode
  }
  auto_k_min <- scalar_int(config$iramuteq_auto_k_min, 2L, 2L)
  if (identical(classif_mode, "double")) {
    segmented_corpus <- split_segments_double_rst(
      corpus_importe,
      rst1 = scalar_int(config$iramuteq_rst1, 12L, 2L),
      rst2 = scalar_int(config$iramuteq_rst2, 14L, 2L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
    log_info(
      paste0(
        "Segmentation CHD double (RST): rst1=",
        scalar_int(config$iramuteq_rst1, 12L, 2L),
        " | rst2=",
        scalar_int(config$iramuteq_rst2, 14L, 2L),
        "."
      ),
      progress = 16
    )
  } else {
    segmented_corpus <- split_segments(
      corpus_importe,
      segment_size = scalar_int(config$segment_size, 40L, 1L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  }
  log_info(paste0("Corpus segmenté en ", quanteda::ndoc(segmented_corpus), " segments."), progress = 18)
  log_info(paste0("Nombre de segments analysés : ", quanteda::ndoc(segmented_corpus)), progress = 19)
  log_info(paste0("Nombre de segments après découpage : ", quanteda::ndoc(segmented_corpus)), progress = 20)

  pipeline <- preparer_pipeline_chd(segmented_corpus, config)
  filtered_corpus <- pipeline$filtered_corpus
  dfm_obj <- pipeline$dfm_obj
  tok <- pipeline$tok
  textes_indexation <- pipeline$textes_indexation
  lexique_fr_df <- pipeline$lexique_fr_df
  corpus_stats <- pipeline$corpus_stats
  log_info(paste0("DFM préparé : ", quanteda::ndoc(dfm_obj), " segments / ", quanteda::nfeat(dfm_obj), " termes."), progress = 42)
  log_info(
    "IRaMuTeQ-lite : paramètres de prétraitement / DFM (min_docfreq, stopwords, ponctuation, dictionnaire) appliqués dans backend/r/run_iramuteq_batch.R",
    progress = 43
  )
  log_info(
    paste0("Nombre de mots conservés pour l'analyse après prétraitements : ", length(unlist(tok, use.names = FALSE))),
    progress = 44
  )

  chd <- NULL
  classes_info <- NULL
  classes <- NULL
  res_stats_df <- NULL
  filtered_corpus_ok <- NULL
  dfm_ok <- NULL
  classes_ok <- NULL

  if (run_chd) {
    log_info("Calcul CHD.", progress = 52)
    log_info("Mode : classification IRaMuTeQ-lite.", progress = 52)
    if (isTRUE(legacy_classes_mode)) {
      log_info("Un ancien mode de selection des classes n'est plus disponible ; execution en mode Normal.", progress = 52)
    }
    log_info(
      paste0(
        "Paramètres IRaMuTeQ-lite : k=",
        scalar_int(config$k_iramuteq, 10L, 2L),
        " | nombre_classes_mode=",
        classes_mode_label,
        if (identical(classes_mode, "discrimination_simple")) {
          paste0(" | k_min_auto=", auto_k_min, " | critere_selection=", auto_discriminant_score_label)
        } else {
          ""
        },
        " | mincl_mode=",
        scalar_chr(config_chd$iramuteq_mincl_mode, "auto"),
        if (identical(scalar_chr(config_chd$iramuteq_mincl_mode, "auto"), "manuel")) {
          paste0(" | mincl=", scalar_int(config_chd$iramuteq_mincl, 5L, 1L))
        } else {
          ""
        },
        " | classif_mode=",
        classif_mode,
        if (identical(classif_mode, "double")) {
          paste0(
            " | rst1=",
            scalar_int(config$iramuteq_rst1, 12L, 2L),
            " | rst2=",
            scalar_int(config$iramuteq_rst2, 14L, 2L)
          )
        } else {
          ""
        },
        " | segmenter_sur_ponctuation_forte=",
        ifelse(scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE), "1", "0"),
        " | svd_method=",
        scalar_chr(config$iramuteq_svd_method, "irlba"),
        " | max_formes=",
        scalar_int(config$iramuteq_max_formes, 20000L, 1L),
        " | stats_mode=",
        scalar_chr(config$iramuteq_stats_mode, "vectorise")
      ),
      progress = 53
    )
    res_ira <- lancer_moteur_chd_iramuteq(
      dfm_obj = dfm_obj,
      k = scalar_int(config_chd$k_iramuteq, 10L, 2L),
      classes_mode = engine_classes_mode,
      mincl_mode = scalar_chr(config_chd$iramuteq_mincl_mode, "auto"),
      mincl = scalar_int(config_chd$iramuteq_mincl, 5L, 1L),
      classif_mode = classif_mode,
      svd_method = scalar_chr(config_chd$iramuteq_svd_method, "irlba"),
      mode_patate = FALSE,
      binariser = TRUE,
      rscripts_dir = file.path(repo_root, "iramuteqlite"),
      max_formes = scalar_int(config_chd$iramuteq_max_formes, 20000L, 1L),
      auto_stats_mode = scalar_chr(config_chd$iramuteq_stats_mode, "vectorise"),
      auto_k_min = auto_k_min,
      auto_top_n_afc = if (identical(classes_mode, "discrimination_simple")) NULL else scalar_int(config_chd$iramuteq_auto_top_n_afc, 20L, 2L),
      auto_discriminant_score_mode = auto_discriminant_score_mode,
      auto_discriminant_base_config = if (identical(engine_classes_mode, "discrimination_simple_config")) config_chd else NULL,
      auto_discriminant_prepare_pipeline_fn = if (identical(engine_classes_mode, "discrimination_simple_config")) {
        function(config_variant) {
          pipeline_env <- environment(preparer_pipeline_chd)
          original_log_info <- get0("log_info", envir = pipeline_env, inherits = FALSE)
          if (is.function(original_log_info)) {
            assign("log_info", function(...) invisible(NULL), envir = pipeline_env)
            on.exit(assign("log_info", original_log_info, envir = pipeline_env), add = TRUE)
          }
          preparer_pipeline_chd(segmented_corpus, config_variant)
        }
      } else {
        NULL
      },
      auto_discriminant_log_fn = if (identical(engine_classes_mode, "discrimination_simple_config")) {
        log_info
      } else {
        NULL
      }
    )
    res_ira$classes_mode <- classes_mode
    if (identical(classes_mode, "discrimination_simple") &&
        is.list(res_ira$auto_selection) &&
        is.list(res_ira$simple_discriminant_selection)) {
      res_ira$auto_selection$selected_configuration_metrics <- res_ira$simple_discriminant_selection$selected_metrics %||% NULL
      res_ira$auto_selection$search_profile <- res_ira$simple_discriminant_selection$search_profile %||% NULL
      res_ira$auto_selection$search_profile_label <- res_ira$simple_discriminant_selection$search_profile_label %||% NULL
      res_ira$auto_selection$total_configurations <- res_ira$simple_discriminant_selection$total_configurations %||% NA_integer_
      res_ira$auto_selection$successful_configurations <- res_ira$simple_discriminant_selection$successful_configurations %||% NA_integer_
      res_ira$auto_selection$unique_dfm_tested <- res_ira$simple_discriminant_selection$unique_dfm_tested %||% NA_integer_
      res_ira$auto_selection$reused_configurations <- res_ira$simple_discriminant_selection$reused_configurations %||% NA_integer_
      res_ira$auto_selection$unique_chd_tested <- res_ira$simple_discriminant_selection$unique_chd_tested %||% NA_integer_
      res_ira$auto_selection$reused_chd_configurations <- res_ira$simple_discriminant_selection$reused_chd_configurations %||% NA_integer_
    }
    chd <- res_ira$chd
    if (is.list(res_ira$selected_pipeline)) {
      filtered_corpus <- res_ira$selected_pipeline$filtered_corpus %||% filtered_corpus
      dfm_obj <- res_ira$selected_pipeline$dfm_obj %||% dfm_obj
      tok <- res_ira$selected_pipeline$tok %||% tok
      textes_indexation <- res_ira$selected_pipeline$textes_indexation %||% textes_indexation
      lexique_fr_df <- res_ira$selected_pipeline$lexique_fr_df %||% lexique_fr_df
      corpus_stats <- res_ira$selected_pipeline$corpus_stats %||% corpus_stats
      log_info(
        paste0(
          "Auto discriminante : pipeline retenu = ",
          quanteda::ndoc(dfm_obj),
          " segments / ",
          quanteda::nfeat(dfm_obj),
          " termes."
        ),
        progress = 60
      )
    }
    if (!is.null(res_ira$dfm_utilise)) {
      dfm_obj <- res_ira$dfm_utilise
    }
    if (is.list(res_ira$max_formes_info) &&
        all(c("max_formes", "n_feat_avant", "n_feat_apres") %in% names(res_ira$max_formes_info))) {
      log_info(
        paste0(
          "Nombre maximum de formes analysées appliqué (chd_iramuteq.R) = ",
          res_ira$max_formes_info$max_formes,
          " (",
          res_ira$max_formes_info$n_feat_avant,
          " -> ",
          res_ira$max_formes_info$n_feat_apres,
          ")."
        ),
        progress = 56
      )
    }
    if (is.list(res_ira$simple_discriminant_selection) &&
        is.data.frame(res_ira$simple_discriminant_selection$selected_metrics) &&
        nrow(res_ira$simple_discriminant_selection$selected_metrics)) {
      selected_discriminant <- res_ira$simple_discriminant_selection$selected_metrics[1, , drop = FALSE]
      selected_score_label <- if ("score_label" %in% names(selected_discriminant) &&
          !is.na(selected_discriminant$score_label[[1]]) && nzchar(selected_discriminant$score_label[[1]])) {
        as.character(selected_discriminant$score_label[[1]])
      } else {
        auto_discriminant_score_label
      }
      selected_score_value <- if ("score_selection" %in% names(selected_discriminant)) {
        suppressWarnings(as.numeric(selected_discriminant$score_selection[[1]]))
      } else {
        suppressWarnings(as.numeric(selected_discriminant$S[[1]] %||% NA_real_))
      }
      log_info(
        paste0(
          "Auto discriminante : configuration retenue ",
          as.character(selected_discriminant$configuration_id %||% ""),
          " (",
          as.character(selected_discriminant$profil_morpho %||% "morpho n/a"),
          ", lemmes=",
          as.character(selected_discriminant$lexique_utiliser_lemmes %||% "n/a"),
          ", stopwords=",
          as.character(selected_discriminant$retirer_stopwords %||% "n/a"),
          ", ponctuation=",
          as.character(selected_discriminant$supprimer_ponctuation %||% "n/a"),
          ", chiffres=",
          as.character(selected_discriminant$supprimer_chiffres %||% "n/a"),
          ", min_docfreq=",
          as.character(selected_discriminant$min_docfreq %||% "n/a"),
          ", classes retenues=",
          as.character(selected_discriminant$k_retenu %||% "n/a"),
          ", classes terminales phase 1=",
          as.character(selected_discriminant$k_max_explore %||% selected_discriminant$k_chd_retenu %||% "n/a"),
          ", ",
          selected_score_label,
          "=",
          format(round(selected_score_value, 4), nsmall = 4, trim = TRUE),
          ")."
        ),
        progress = 60
      )
    }
    classes <- as.integer(res_ira$classes)
    if (all(is.na(classes)) || length(unique(classes[classes > 0])) < 2) {
      stop("IRaMuTeQ-lite n'a pas pu produire au moins 2 classes exploitables.")
    }
    classes_info <- list(
      terminales = res_ira$terminales,
      mincl = res_ira$mincl,
      auto_selection = res_ira$auto_selection,
      simple_discriminant_selection = res_ira$simple_discriminant_selection
    )
    quanteda::docvars(filtered_corpus, "Classes") <- classes

    idx_ok <- !is.na(classes) & classes > 0
    nb_non_assignes <- sum(!idx_ok)
    if (nb_non_assignes > 0) {
      log_info(
        paste0(
          "Segments non assignés à une classe terminale (Classe 0 / NA) : ",
          nb_non_assignes,
          ". Exclusion des calculs CHD/AFC."
        )
      )
    }

    filtered_corpus_ok <- filtered_corpus[idx_ok]
    dfm_ok <- dfm_obj[idx_ok, ]
    classes_ok <- as.integer(quanteda::docvars(filtered_corpus_ok)$Classes)

    if (quanteda::ndoc(dfm_ok) < 2) stop("Apres classification, il reste moins de 2 segments classes (hors NA).")
    if (quanteda::nfeat(dfm_ok) < 2) stop("Apres classification, le DFM classe est trop pauvre (moins de 2 termes).")

    specificites_source <- exporter_source_specificites(
      dfm_obj = dfm_ok,
      corpus_obj = filtered_corpus_ok,
      classes = classes_ok,
      output_dir = output_dir,
      config = config
    )
    artifacts$variables_specificites <- relative_to_output(specificites_source$options)
    log_info("Données lexicales compactes préparées pour les analyses de spécificités par modalité.")

    if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE)) {
      expression_df_log <- pipeline$expressions_actives_df
      if (!is.null(expression_df_log) &&
          is.data.frame(expression_df_log) &&
          nrow(expression_df_log) > 0 &&
          "dic_norm" %in% names(expression_df_log)) {
        expr_norm <- unique(tolower(trimws(as.character(expression_df_log$dic_norm))))
        expr_norm <- expr_norm[nzchar(expr_norm)]
        if (length(expr_norm) > 0) {
          feats_ok <- tolower(trimws(as.character(quanteda::featnames(dfm_ok))))
          expr_dans_dfm_ok <- intersect(expr_norm, feats_ok)
          log_info(
            paste0(
              "Expressions (dic_norm) conservées dans le DFM final CHD/AFC : ",
              length(expr_dans_dfm_ok),
              "/",
              length(expr_norm),
              "."
            )
          )
          if ("source_expr" %in% names(expression_df_log)) {
            expr_norm_user <- unique(tolower(trimws(as.character(expression_df_log$dic_norm[expression_df_log$source_expr == "user"]))))
            expr_norm_user <- expr_norm_user[nzchar(expr_norm_user)]
            if (length(expr_norm_user) > 0) {
              expr_user_dans_dfm_ok <- intersect(expr_norm_user, feats_ok)
              log_info(
                paste0(
                  "Expressions utilisateur conservées dans le DFM final CHD/AFC : ",
                  length(expr_user_dans_dfm_ok),
                  "/",
                  length(expr_norm_user),
                  "."
                )
              )
            }
          }
        }
      }
    }

    log_info("Statistiques CHD : calcul IRaMuTeQ-lite (contingence classe x terme).", progress = 58)
    res_stats_df <- construire_stats_classes_iramuteq(
      dfm_obj = dfm_ok,
      classes = classes_ok,
      max_p = 1,
      stats_mode = scalar_chr(config$iramuteq_stats_mode, "vectorise")
    )
    res_stats_df$Classe <- normaliser_id_classe_local(res_stats_df$Classe)
    ord_stats <- with(
      res_stats_df,
      order(
        suppressWarnings(as.integer(Classe)),
        -suppressWarnings(as.numeric(chi2)),
        na.last = TRUE
      )
    )
    res_stats_df <- res_stats_df[ord_stats, , drop = FALSE]

    if (!is.null(lexique_fr_df) &&
        "Terme" %in% names(res_stats_df) &&
        exists("construire_type_lexique_fr", mode = "function", inherits = TRUE)) {
      res_stats_df$Type <- construire_type_lexique_fr(res_stats_df$Terme, lexique_fr_df)
      log_info(
        paste0(
          "Lexique ",
          infos_dictionnaire(pipeline$source_dictionnaire)$libelle,
          " utilisé pour typer les termes CHD : ",
          nrow(lexique_fr_df),
          " entrées."
        )
      )
    }
    if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE) &&
        !is.null(pipeline$expressions_actives_df) &&
        "dic_norm" %in% names(pipeline$expressions_actives_df) &&
        "Terme" %in% names(res_stats_df)) {
      expr_stats_norm <- unique(tolower(trimws(as.character(pipeline$expressions_actives_df$dic_norm))))
      expr_stats_norm <- expr_stats_norm[nzchar(expr_stats_norm)]
      stats_terms <- unique(tolower(trimws(as.character(res_stats_df$Terme))))
      stats_terms <- stats_terms[nzchar(stats_terms)]
      expr_visibles_stats <- intersect(expr_stats_norm, stats_terms)
      log_info(
        paste0(
          "Expressions visibles dans les stats CHD exportées : ",
          length(expr_visibles_stats),
          "/",
          length(expr_stats_norm),
          "."
        )
      )
      if ("source_expr" %in% names(pipeline$expressions_actives_df)) {
        expr_user_stats_norm <- unique(tolower(trimws(as.character(
          pipeline$expressions_actives_df$dic_norm[pipeline$expressions_actives_df$source_expr == "user"]
        ))))
        expr_user_stats_norm <- expr_user_stats_norm[nzchar(expr_user_stats_norm)]
        if (length(expr_user_stats_norm) > 0) {
          expr_user_visibles_stats <- intersect(expr_user_stats_norm, stats_terms)
          log_info(
            paste0(
              "Expressions utilisateur visibles dans les stats CHD exportées : ",
              length(expr_user_visibles_stats),
              "/",
              length(expr_user_stats_norm),
              "."
            )
          )
        }
      }
    }
    stats_file <- file.path(output_dir, "stats_par_classe.csv")
    p_log <- if ("p_log" %in% names(res_stats_df)) res_stats_df$p_log else NULL
    res_stats_df$p_affiche <- formatter_p_affiche_batch(res_stats_df$p)
    res_stats_df$p_scientifique <- formatter_p_scientifique_batch(res_stats_df$p, p_log)
    res_stats_df$p_seuil_01 <- formatter_p_seuil_01_batch(res_stats_df$p)
    res_stats_df$p_log <- NULL
    ecrire_csv_6_decimales(res_stats_df, stats_file, row.names = FALSE)
    artifacts$stats_par_classe <- relative_to_output(stats_file)

    segments_vec <- as.character(filtered_corpus_ok)
    ids_segments <- as.character(quanteda::docnames(filtered_corpus_ok))
    names(segments_vec) <- ids_segments
    idx_chd <- match(ids_segments, names(textes_indexation))
    ok_chd <- !is.na(idx_chd)
    if (any(ok_chd)) {
      segments_vec[ok_chd] <- as.character(textes_indexation[idx_chd[ok_chd]])
    }
    segments_by_class <- split(segments_vec, classes_ok)
    segments_file <- file.path(output_dir, "segments_par_classe.txt")
    writeLines(unlist(lapply(names(segments_by_class), function(cl) c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), ""))), segments_file)
    artifacts$segments_par_classe <- relative_to_output(segments_file)

    dendrogram_width <- clamp_int(
      scalar_int(config$chd_dendrogram_width_px, 1400L, 1200L),
      1200L,
      2400L
    )
    dendrogram_height <- clamp_int(
      scalar_int(config$chd_dendrogram_height_px, as.integer(round(dendrogram_width * 0.52)), 620L),
      620L,
      1400L
    )

    chd_png <- file.path(output_dir, "dendrogramme_chd.png")
    grDevices::png(chd_png, width = dendrogram_width, height = dendrogram_height, res = 180)
    tracer_dendrogramme_iramuteq_ui(
      rv = list(
        res = list(
          chd = chd,
          terminales = classes_info$terminales,
          classes = classes
        ),
        filtered_corpus = filtered_corpus_ok,
        res_stats_df = res_stats_df
      ),
      top_n_terms = 4,
      orientation = "horizontal",
      style_affichage = "iramuteq_bars"
    )
    grDevices::dev.off()
    artifacts$dendrogramme_chd <- relative_to_output(chd_png)
    log_info("Export du dendrogramme IRaMuTeQ terminé.", progress = 63)

    chd_factoextra_png <- file.path(output_dir, "dendrogramme_chd_factoextra.png")
    grDevices::png(chd_factoextra_png, width = dendrogram_width, height = dendrogram_height, res = 180)
    tracer_dendrogramme_iramuteq_ui(
      rv = list(
        res = list(
          chd = chd,
          terminales = classes_info$terminales,
          classes = classes
        ),
        filtered_corpus = filtered_corpus_ok,
        res_stats_df = res_stats_df
      ),
      top_n_terms = 4,
      orientation = "horizontal",
      style_affichage = "factoextra"
    )
    grDevices::dev.off()
    artifacts$dendrogramme_chd_factoextra <- relative_to_output(chd_factoextra_png)
    log_info("Export du dendrogramme factoextra terminé.", progress = 64)

    html_file <- file.path(output_dir, "segments_par_classe.html")
    textes_index_ok <- textes_indexation[quanteda::docnames(dfm_ok)]
    names(textes_index_ok) <- quanteda::docnames(dfm_ok)
    args_concordancier <- list(
      chemin_sortie = html_file,
      segments_by_class = segments_by_class,
      res_stats_df = res_stats_df,
      max_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
      filtrer_pvalue = scalar_bool(config$filtrer_affichage_pvalue, TRUE),
      textes_indexation = textes_index_ok,
      rv = list(lexique_fr_df = lexique_fr_df)
    )

    html_genere <- tryCatch(
      do.call(generer_concordancier_iramuteq_html, args_concordancier),
      error = function(e) {
        log_info(paste0("Concordancier HTML : échec de la première génération - ", e$message))
        NA_character_
      }
    )

    candidats_html <- unique(c(
      html_genere,
      html_file,
      file.path(output_dir, "concordancier.html")
    ))
    candidats_html <- candidats_html[is.character(candidats_html) & !is.na(candidats_html) & nzchar(candidats_html)]
    html_existants <- candidats_html[file.exists(candidats_html)]

    if (length(html_existants) == 0) {
      html_fallback <- file.path(output_dir, "concordancier.html")
      args_concordancier$chemin_sortie <- html_fallback
      log_info("Concordancier HTML introuvable après la première génération. Nouvelle tentative vers exports/concordancier.html.")
      html_retry <- tryCatch(
        do.call(generer_concordancier_iramuteq_html, args_concordancier),
        error = function(e) {
          log_info(paste0("Concordancier HTML : échec de la relance - ", e$message))
          NA_character_
        }
      )

      candidats_retry <- unique(c(html_retry, html_fallback, html_genere, html_file))
      candidats_retry <- candidats_retry[is.character(candidats_retry) & !is.na(candidats_retry) & nzchar(candidats_retry)]
      html_existants <- candidats_retry[file.exists(candidats_retry)]
    }

    if (length(html_existants) > 0) {
      artifacts$concordancier_html <- relative_to_output(html_existants[[1]])
      log_info(paste0("Concordancier HTML valide : ", html_existants[[1]]), progress = 66)
    } else {
      html_diag <- file.path(output_dir, "concordancier.html")
      diag_lines <- c(
        "<html><head><meta charset='utf-8'/>",
        "<style>body{font-family:Arial,sans-serif;line-height:1.5;padding:1rem 1.2rem;} code{background:#f7f7f7;padding:.1rem .3rem;border-radius:3px;}</style>",
        "</head><body>",
        "<h2>Concordancier indisponible</h2>",
        "<p>Le concordancier HTML n'a pas pu être généré automatiquement pour cette analyse.</p>",
        "<p>Vérifiez le journal de l'analyse puis relancez si nécessaire.</p>",
        paste0("<p><strong>Dossier d'exports :</strong> <code>", htmltools::htmlEscape(output_dir), "</code></p>"),
        "</body></html>"
      )
      ok_diag <- tryCatch({
        writeLines(diag_lines, html_diag, useBytes = TRUE)
        file.exists(html_diag)
      }, error = function(e) {
        log_info(paste0("Concordancier HTML : impossible d'écrire le fichier de diagnostic - ", e$message))
        FALSE
      })

      if (isTRUE(ok_diag)) {
        artifacts$concordancier_html <- relative_to_output(html_diag)
        log_info(paste0("Concordancier HTML de diagnostic généré : ", html_diag), progress = 66)
      } else {
        log_info("Concordancier HTML indisponible après toutes les tentatives.", progress = 66)
      }
    }

    wordcloud_dir <- file.path(output_dir, "wordclouds")
    dir.create(wordcloud_dir, recursive = TRUE, showWarnings = FALSE)
    classes_uniques <- sort(unique(classes_ok))
    generer_wordclouds_iramuteq(
      res_stats_df = res_stats_df,
      classes_uniques = classes_uniques,
      wordcloud_dir = wordcloud_dir,
      top_n = scalar_int(config$top_n, 20L, 5L),
      filtrer_pvalue = scalar_bool(config$filtrer_affichage_pvalue, TRUE),
      max_p = scalar_num(config$max_p, 0.05)
    )
    artifacts$wordclouds <- unname(vapply(list.files(wordcloud_dir, pattern = "\\.png$", full.names = TRUE), relative_to_output, character(1)))
    log_info("Mode IRaMuTeQ-lite : nuages de mots générés via wordcloud_iramuteq.R.", progress = 67)

    if (is.list(res_ira$simple_discriminant_selection)) {
      tryCatch({
        discrimination_simple_exports <- exporter_discrimination_simple_iramuteq(res_ira$simple_discriminant_selection, output_dir)
        artifacts$discrimination_simple <- list(
          metrics_csv = relative_to_output(discrimination_simple_exports$metrics_csv),
          summary_json = relative_to_output(discrimination_simple_exports$summary_json),
          score_png = relative_to_output(discrimination_simple_exports$score_png)
        )
        log_info("Exports Auto discriminante generes.", progress = 69)
      }, error = function(e) {
        log_info(paste0("Exports Auto discriminante indisponibles : ", e$message))
      })
    }

    log_info("Exports CHD générés.", progress = 70)
  }

  if (run_afc && !is.null(classes)) {
    log_info("Calcul AFC.", progress = 74)
    afc_dir <- file.path(output_dir, "afc")
    dir.create(afc_dir, recursive = TRUE, showWarnings = FALSE)
    termes_signif <- NULL
    if (scalar_bool(config$filtrer_affichage_pvalue, TRUE) && !is.null(res_stats_df)) {
      termes_signif <- unique(subset(res_stats_df, p <= scalar_num(config$max_p, 0.05))$Terme)
      termes_signif <- termes_signif[!is.na(termes_signif) & nzchar(termes_signif)]
      if (length(termes_signif) < 2) termes_signif <- NULL
    }
    if (identical(classes_mode, "discrimination_simple") && !is.null(termes_signif)) {
      log_info(
        paste0(
          "Auto discriminante : AFC finale construite avec les ",
          length(termes_signif),
          " termes significatifs (p.value <= ",
          scalar_num(config$max_p, 0.05),
          "), comme en mode Normal."
        ),
        progress = 75
      )
    }

    groupes_docs <- quanteda::docvars(filtered_corpus_ok)$Classes

    afc_obj <- executer_afc_classes(
      dfm_obj = dfm_ok,
      groupes = groupes_docs,
      termes_cibles = termes_signif,
      max_termes = 400,
      seuil_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
      rv = NULL
    )

    if (!is.null(afc_obj$termes_stats) && !is.null(res_stats_df)) {
      df_m <- afc_obj$termes_stats
      df_m$Classe_num <- suppressWarnings(as.numeric(gsub("^Classe\\s+", "", as.character(df_m$Classe_max))))
      rs <- res_stats_df

      rs2 <- rs[, intersect(c("Terme", "Classe", "chi2", "p", "frequency", "docprop", "lr"), names(rs)), drop = FALSE]
      rs2$Classe <- as.numeric(rs2$Classe)

      m <- merge(
        df_m,
        rs2,
        by.x = c("Terme", "Classe_num"),
        by.y = c("Terme", "Classe"),
        all.x = TRUE,
        suffixes = c("_global", "_stats")
      )

      if ("chi2" %in% names(m)) {
        df_m$chi2 <- ifelse(is.na(m$chi2), df_m$chi2, m$chi2)
      }
      if ("p" %in% names(m)) {
        df_m$p_value <- ifelse(is.na(m$p), df_m$p_value, m$p)
      }

      df_m$Classe_num <- NULL
      afc_obj$termes_stats <- df_m
    }

    afc_obj$termes_stats <- tryCatch(
      construire_segments_exemples_afc(afc_obj$termes_stats, dfm_obj = dfm_ok, corpus_obj = filtered_corpus_ok),
      error = function(e_seg) {
        log_info(paste0("AFC classes x termes : enrichissement des segments ignoré (", e_seg$message, ")."))
        afc_obj$termes_stats
      }
    )

    mots_reperes_axes_final <- NULL
    termes_reperes_axes_final <- character(0)
    if (identical(classes_mode, "discrimination_simple") &&
        is.list(res_ira$simple_discriminant_selection) &&
        !is.null(res_stats_df)) {
      mots_reperes_axes_final <- tryCatch(
        extraire_mots_reperes_axes_discrimination_simple_iramuteq(
          afc_obj = afc_obj,
          res_stats_df = res_stats_df,
          top_n = 5L,
          p_seuil = scalar_num(config$max_p, 0.05)
        ),
        error = function(e_reperes) {
          log_info(paste0("Auto discriminante : mots reperes AFC indisponibles (", e_reperes$message, ")."))
          NULL
        }
      )
      if (is.data.frame(mots_reperes_axes_final) &&
          "terme" %in% names(mots_reperes_axes_final)) {
        termes_reperes_axes_final <- unique(as.character(mots_reperes_axes_final$terme))
        termes_reperes_axes_final <- termes_reperes_axes_final[
          !is.na(termes_reperes_axes_final) & nzchar(termes_reperes_axes_final)
        ]
      }
    }

    afc_classes_png <- NULL
    afc_termes_png <- NULL
    afc_extremes_png <- NULL
    termes_extremes_afc <- tryCatch(
      selectionner_termes_extremes_afc(
        afc_obj = afc_obj,
        stats_df = res_stats_df,
        top_n = 5L,
        p_seuil = 0.05
      ),
      error = function(e_extremes) {
        log_info(paste0("AFC termes extremes indisponible : ", e_extremes$message))
        data.frame(classe = character(), terme = character(), x = numeric(), y = numeric(), distance_origine = numeric(), chi2 = numeric(), p_value = numeric(), stringsAsFactors = FALSE)
      }
    )
    if (coords_have_at_least_one_axis(afc_obj$rowcoord) && coords_have_at_least_one_axis(afc_obj$colcoord)) {
      activer_repel <- scalar_bool(config$afc_reduire_chevauchement, TRUE)
      taille_sel <- scalar_chr(config$afc_taille_mots, "frequency")
      if (!taille_sel %in% c("frequency", "chi2")) taille_sel <- "frequency"
      top_termes <- 120L

      afc_classes_png <- file.path(afc_dir, "afc_classes.png")
      afc_termes_png <- file.path(afc_dir, "afc_termes.png")
      grDevices::png(afc_classes_png, width = 1800, height = 1400, res = 180)
      tryCatch(
        tracer_afc_classes_seules(
          afc_obj,
          axes = c(1, 2),
          cex_labels = 1.05,
          top_termes = top_termes,
          termes_forces = termes_reperes_axes_final
        ),
        error = function(e) {
          plot.new()
          text(0.5, 0.5, paste0("AFC classes indisponible : ", e$message), cex = 1.0)
          log_info(paste0("AFC classes : rendu de secours utilise (", e$message, ")."))
        }
      )
      grDevices::dev.off()
      grDevices::png(afc_termes_png, width = 2000, height = 1600, res = 180)
      tryCatch(
        tracer_afc_classes_termes(
          afc_obj,
          axes = c(1, 2),
          top_termes = top_termes,
          termes_forces = termes_reperes_axes_final,
          taille_sel = taille_sel,
          activer_repel = activer_repel
        ),
        error = function(e) {
          plot.new()
          text(0.5, 0.5, paste0("AFC termes indisponible : ", e$message), cex = 1.0)
          log_info(paste0("AFC termes : rendu de secours utilise (", e$message, ")."))
        }
      )
      grDevices::dev.off()
      afc_extremes_png <- file.path(afc_dir, "afc_termes_extremes.png")
      grDevices::png(afc_extremes_png, width = 2000, height = 1600, res = 180)
      tryCatch(
        {
          # Reuse the official AFC terms renderer. Only its term list is
          # narrowed; coordinates, axes, colours and label placement stay identical.
          afc_extremes_obj <- afc_obj
          termes_extremes <- unique(as.character(termes_extremes_afc$terme))
          termes_extremes <- termes_extremes[!is.na(termes_extremes) & nzchar(termes_extremes)]
          normaliser_termes_extremes <- function(values) tolower(trimws(as.character(values)))
          keep_extremes <- normaliser_termes_extremes(afc_extremes_obj$termes_stats$Terme) %in% normaliser_termes_extremes(termes_extremes)
          afc_extremes_obj$termes_stats <- afc_extremes_obj$termes_stats[keep_extremes, , drop = FALSE]
          tracer_afc_classes_termes(
            afc_extremes_obj,
            axes = c(1, 2),
            top_termes = max(1L, length(termes_extremes)),
            termes_forces = termes_extremes,
            taille_sel = taille_sel,
            activer_repel = activer_repel
          )
        },
        error = function(e) {
          plot.new()
          text(0.5, 0.5, paste0("AFC termes extremes indisponible : ", e$message), cex = 1.0)
          log_info(paste0("AFC termes extremes : rendu de secours utilise (", e$message, ")."))
        }
      )
      grDevices::dev.off()
      if (coords_have_two_axes(afc_obj$rowcoord) && coords_have_two_axes(afc_obj$colcoord)) {
        log_info("AFC classes x termes : calcul terminé.", progress = 78)
      } else {
        log_info("AFC classes x termes : un seul axe disponible, export PNG en projection 1D.", progress = 78)
      }
    } else {
      log_info("AFC classes/termes : aucun axe exploitable, graphiques PNG ignorés.")
    }

    ecrire_csv_6_decimales(afc_obj$table, file.path(afc_dir, "table_classes_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$rowcoord, file.path(afc_dir, "coords_classes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$colcoord, file.path(afc_dir, "coords_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$termes_stats, file.path(afc_dir, "stats_termes.csv"), row.names = FALSE)
    ecrire_csv_6_decimales(termes_extremes_afc, file.path(afc_dir, "termes_extremes_afc.csv"), row.names = FALSE)
    graph_interactif_file <- file.path(afc_dir, "graph_interactif.json")
    graph_interactif_leaflet_file <- file.path(afc_dir, "graph_interactif_leaflet.html")
    tryCatch(
      ecrire_graph_interactif_afc(
        coords_classes_file = file.path(afc_dir, "coords_classes.csv"),
        coords_termes_file = file.path(afc_dir, "coords_termes.csv"),
        stats_termes_file = file.path(afc_dir, "stats_termes.csv"),
        output_file = graph_interactif_file,
        seuil_p = 0.05,
        top_termes = 120L
      ),
      error = function(e) {
        graph_interactif_file <<- NULL
        log_info(paste0("Graphe AFC interactif indisponible : ", e$message))
      }
    )
    tryCatch(
      ecrire_graph_interactif_leaflet_afc(
        coords_classes_file = file.path(afc_dir, "coords_classes.csv"),
        coords_termes_file = file.path(afc_dir, "coords_termes.csv"),
        stats_termes_file = file.path(afc_dir, "stats_termes.csv"),
        output_file = graph_interactif_leaflet_file,
        seuil_p = 0.05,
        top_termes = 120L
      ),
      error = function(e) {
        graph_interactif_leaflet_file <<- NULL
        log_info(paste0("Carte AFC Leaflet indisponible : ", e$message))
      }
    )
    if (identical(classes_mode, "discrimination_simple") &&
        is.list(res_ira$simple_discriminant_selection) &&
        is.data.frame(mots_reperes_axes_final)) {
      tryCatch(
        exporter_discrimination_simple_iramuteq(
          res_ira$simple_discriminant_selection,
          output_dir,
          mots_reperes_axes = mots_reperes_axes_final
        ),
        error = function(e_reperes_export) {
          log_info(paste0("Auto discriminante : synchronisation des mots reperes AFC ignoree (", e_reperes_export$message, ")."))
        }
      )
    }
    if (!is.null(afc_obj$ca$eig)) {
      ecrire_csv_6_decimales(as.data.frame(afc_obj$ca$eig), file.path(afc_dir, "valeurs_propres.csv"), row.names = TRUE)
    }

    artifacts$afc <- list(
      afc_classes_png = relative_to_output(afc_classes_png),
      afc_termes_png = relative_to_output(afc_termes_png),
      afc_termes_extremes_png = if (!is.null(afc_extremes_png)) relative_to_output(afc_extremes_png) else NULL,
      termes_extremes_afc_csv = relative_to_output(file.path(afc_dir, "termes_extremes_afc.csv")),
      graph_interactif_json = if (!is.null(graph_interactif_file)) relative_to_output(graph_interactif_file) else NULL,
      graph_interactif_leaflet_html = if (!is.null(graph_interactif_leaflet_file)) relative_to_output(graph_interactif_leaflet_file) else NULL,
      coords_termes_csv = relative_to_output(file.path(afc_dir, "coords_termes.csv")),
      stats_termes_csv = relative_to_output(file.path(afc_dir, "stats_termes.csv")),
      valeurs_propres_csv = relative_to_output(file.path(afc_dir, "valeurs_propres.csv"))
    )

    afc_vars_obj <- tryCatch(
      executer_afc_variables_etoilees(
        corpus_aligne = filtered_corpus_ok,
        groupes = classes_ok,
        max_modalites = 400,
        seuil_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
        variables_etoilees = as_char_vec(config$afc_variables_etoilees, character(0)),
        modalites_etoilees = as_char_vec(config$afc_modalites_etoilees, character(0)),
        rv = NULL
      ),
      error = function(e) NULL
    )
    if (!is.null(afc_vars_obj) && !is.null(afc_vars_obj$ca)) {
      activer_repel2 <- scalar_bool(config$afc_reduire_chevauchement, TRUE)
      top_mod <- 120L
      afc_vars_png <- file.path(afc_dir, "afc_variables_etoilees.png")
      grDevices::png(afc_vars_png, width = 2000, height = 1600, res = 180)
      tryCatch(
        {
          if (!coords_have_at_least_one_axis(afc_vars_obj$rowcoord) || !coords_have_at_least_one_axis(afc_vars_obj$colcoord)) {
            .tracer_modalites_etoilees_repli(
              afc_vars_obj$modalites_stats,
              top_modalites = top_mod,
              message = "Coordonnées AFC insuffisantes : affichage de secours par fréquence."
            )
          } else {
            if (!coords_have_two_axes(afc_vars_obj$rowcoord) || !coords_have_two_axes(afc_vars_obj$colcoord)) {
              log_info("AFC variables étoilées : un seul axe disponible, graphique de secours par fréquence.")
            }
            tracer_afc_variables_etoilees(
              afc_vars_obj,
              axes = c(1, 2),
              top_modalites = top_mod,
              activer_repel = activer_repel2
            )
          }
        },
        error = function(e) {
          plot.new()
          text(0.5, 0.5, paste0("AFC variables etoilees indisponible : ", e$message), cex = 1.0)
          log_info(paste0("AFC variables etoilees : rendu de secours utilise (", e$message, ")."))
          try(
            .tracer_modalites_etoilees_repli(
              afc_vars_obj$modalites_stats,
              top_modalites = top_mod,
              message = "Projection AFC indisponible : affichage de secours par fréquence."
            ),
            silent = TRUE
          )
        }
      )
      grDevices::dev.off()
      if (coords_have_at_least_one_axis(afc_vars_obj$rowcoord) && coords_have_at_least_one_axis(afc_vars_obj$colcoord)) {
        if (coords_have_two_axes(afc_vars_obj$rowcoord) && coords_have_two_axes(afc_vars_obj$colcoord)) {
          log_info("AFC variables étoilées : calcul terminé.", progress = 80)
        } else {
          log_info("AFC variables étoilées : un seul axe disponible, export PNG de secours généré.", progress = 80)
        }
      } else {
        log_info("AFC variables étoilées : coordonnées insuffisantes, export PNG de secours généré.", progress = 80)
      }
      ecrire_csv_6_decimales(afc_vars_obj$modalites_stats, file.path(afc_dir, "stats_modalites.csv"), row.names = FALSE)
      if (!is.null(afc_vars_obj$ca$eig)) {
        ecrire_csv_6_decimales(as.data.frame(afc_vars_obj$ca$eig), file.path(afc_dir, "valeurs_propres_vars.csv"), row.names = TRUE)
      }
      artifacts$afc$afc_variables_png <- relative_to_output(afc_vars_png)
      artifacts$afc$stats_modalites_csv <- relative_to_output(file.path(afc_dir, "stats_modalites.csv"))
      artifacts$afc$valeurs_propres_vars_csv <- relative_to_output(file.path(afc_dir, "valeurs_propres_vars.csv"))
    }
  }

  if (run_simi) {
    log_info("Calcul similitudes.", progress = 84)
    simi_layout_spacing <- scalar_num(config$simi_layout_spacing, 1.7)
    if (!is.finite(simi_layout_spacing) || is.na(simi_layout_spacing)) simi_layout_spacing <- 1.7
    simi_layout_spacing <- min(3, max(0.8, simi_layout_spacing))
    simi <- construire_graphe_similitudes(
      dfm_obj = dfm_obj,
      method = scalar_chr(config$simi_method, "cooc"),
      seuil = if (is.null(config$simi_seuil) || !length(config$simi_seuil) || is.na(config$simi_seuil[[1]])) NA_real_ else scalar_num(config$simi_seuil, NA_real_),
      max_tree = scalar_bool(config$simi_max_tree, TRUE),
      top_terms = scalar_int(config$simi_top_terms, 100L, 5L),
      selected_terms = as_char_vec(config$simi_terms_selected, character(0)),
      layout_type = scalar_chr(config$simi_layout, "frutch"),
      layout_spacing = simi_layout_spacing,
      communities = scalar_bool(config$simi_communities, TRUE),
      community_method = scalar_chr(config$simi_community_method, "edge_betweenness")
    )
    json_path <- file.path(output_dir, "simi_graph.json")
    simi_json <- tryCatch(
      {
        exporter_graphe_similitudes_cytoscape(
          simi = simi,
          chemin_sortie = json_path,
          edge_width_by_index = scalar_bool(config$simi_edge_width_by_index, TRUE),
          edge_labels = scalar_bool(config$simi_edge_labels, FALSE),
          halo = scalar_bool(config$simi_halo, TRUE),
          info_text = paste0("Analyse de similitudes de Vergès - espacement ", simi_layout_spacing)
        )
        log_info("Graphe de similitudes JSON Cytoscape exporté.", progress = 85)
        json_path
      },
      error = function(e) {
        primary_message <- conditionMessage(e)
        log_info(paste0("Export JSON Cytoscape avec halos indisponible : ", primary_message, ". Nouvelle tentative sans halos."))
        fallback_json <- tryCatch(
          {
            exporter_graphe_similitudes_cytoscape(
              simi = simi,
              chemin_sortie = json_path,
              edge_width_by_index = scalar_bool(config$simi_edge_width_by_index, TRUE),
              edge_labels = scalar_bool(config$simi_edge_labels, FALSE),
              halo = FALSE,
              info_text = paste0("Analyse de similitudes de Vergès - espacement ", simi_layout_spacing, " - sans halos")
            )
            log_info("Graphe de similitudes JSON Cytoscape exporté sans halos.", progress = 85)
            json_path
          },
          error = function(fallback_error) {
            diagnostic_message <- paste0(primary_message, " | repli sans halos : ", conditionMessage(fallback_error))
            log_info(paste0("Export JSON Cytoscape indisponible : ", diagnostic_message, ". Le PNG statique reste disponible."))
            if (requireNamespace("jsonlite", quietly = TRUE)) {
              diagnostic_payload <- list(
                schema = "iramuteq-lite.similitudes.cytoscape.v1",
                success = FALSE,
                error = diagnostic_message,
                nodes = list(),
                edges = list(),
                halos = list(),
                meta = list(
                  title = "Export JSON Cytoscape indisponible",
                  renderer = "cytoscape.js + cytoscape-fcose + cytoscape-bubblesets",
                  layout_spacing = simi_layout_spacing
                )
              )
              diagnostic_path <- tryCatch(
                {
                  jsonlite::write_json(diagnostic_payload, json_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
                  json_path
                },
                error = function(write_error) NULL
              )
              if (!is.null(diagnostic_path)) {
                log_info("Diagnostic JSON Cytoscape exporté.")
                return(diagnostic_path)
              }
            }
            NULL
          }
        )
        fallback_json
      }
    )
    simi_png <- file.path(output_dir, "simi_graph.png")
    simi_png_width <- as.integer(min(5200, max(2400, round(2200 * simi_layout_spacing))))
    simi_png_height <- as.integer(min(3900, max(1800, round(1650 * simi_layout_spacing))))
    grDevices::png(simi_png, width = simi_png_width, height = simi_png_height, res = 180)
    tracer_graphe_similitudes_igraph(
      g = simi$graph,
      layout = simi$layout,
      edge_labels = scalar_bool(config$simi_edge_labels, FALSE),
      edge_width_by_index = scalar_bool(config$simi_edge_width_by_index, TRUE),
      vertex_text_by_freq = scalar_bool(config$simi_vertex_text_by_freq, TRUE),
      vertex_freq = simi$vertex_freq,
      communities = simi$communities,
      halo = scalar_bool(config$simi_halo, TRUE),
      layout_spacing = simi_layout_spacing,
      info_text = paste0("Graphe de similitudes statique - espacement ", simi_layout_spacing)
    )
    grDevices::dev.off()
    artifacts$simi <- list(
      graph_json = relative_to_output(simi_json),
      graph_png = relative_to_output(simi_png)
    )
    log_info("Graphe de similitudes généré.", progress = 86)
  }

  if (isTRUE(run_chd) && is.list(classes_info)) {
    configuration_chd_path <- exporter_configuration_chd_iramuteq(
      config_requested = config,
      classes_mode = classes_mode,
      classes_mode_label = classes_mode_label,
      classes_info = classes_info,
      classes = classes_ok,
      input_path = input_path,
      corpus_md5 = corpus_md5,
      output_dir = output_dir
    )
    artifacts$configuration_chd <- relative_to_output(configuration_chd_path)
    log_info("Configuration CHD exportée dans configuration_chd.json.", progress = 94)
  }

  summary <- list(
    corpus = basename(input_path),
    n_texts = quanteda::ndoc(corpus_importe),
    n_segments = quanteda::ndoc(filtered_corpus),
    n_tokens = corpus_stats$n_tokens %||% 0,
    n_hapax = corpus_stats$n_hapax %||% 0,
    n_formes = corpus_stats$n_formes %||% 0,
    n_features = quanteda::nfeat(dfm_obj),
    n_classes = if (is.null(classes_ok)) 0L else length(unique(classes_ok)),
    classes_mode = classes_mode,
    classes_mode_label = classes_mode_label,
    auto_classes_selected = if (is.list(classes_info$auto_selection)) classes_info$auto_selection$k_selected %||% NA_integer_ else NA_integer_,
    auto_classes_min_requested = if (is.list(classes_info$auto_selection)) classes_info$auto_selection$k_min_requested %||% NA_integer_ else NA_integer_,
    auto_classes_max_requested = if (is.list(classes_info$auto_selection)) classes_info$auto_selection$k_max_requested %||% NA_integer_ else NA_integer_,
    auto_classes_max_tested = if (is.list(classes_info$auto_selection) && is.data.frame(classes_info$auto_selection$evaluation)) {
      suppressWarnings(max(as.integer(classes_info$auto_selection$evaluation$k), na.rm = TRUE))
    } else {
      NA_integer_
    },
    discrimination_simple_configuration = if (is.list(classes_info$simple_discriminant_selection) && is.data.frame(classes_info$simple_discriminant_selection$selected_metrics)) {
      classes_info$simple_discriminant_selection$selected_metrics$configuration_id[[1]] %||% NA_character_
    } else {
      NA_character_
    },
    discrimination_simple_score = if (is.list(classes_info$simple_discriminant_selection) && is.data.frame(classes_info$simple_discriminant_selection$selected_metrics)) {
      selected_metrics <- classes_info$simple_discriminant_selection$selected_metrics
      if ("score_selection" %in% names(selected_metrics)) {
        suppressWarnings(as.numeric(selected_metrics$score_selection[[1]]))
      } else {
        suppressWarnings(as.numeric(selected_metrics$S[[1]]))
      }
    } else {
      NA_real_
    },
    discrimination_simple_score_mode = if (is.list(classes_info$simple_discriminant_selection)) {
      classes_info$simple_discriminant_selection$score_mode %||% NA_character_
    } else {
      NA_character_
    },
    discrimination_simple_score_label = if (is.list(classes_info$simple_discriminant_selection)) {
      classes_info$simple_discriminant_selection$score_label %||% NA_character_
    } else {
      NA_character_
    },
    zipf = corpus_stats$zipf,
    output_dir = output_dir
  )

  log_info("Analyse terminée.", progress = 100)
  payload <- list(
    success = TRUE,
    output_dir = output_dir,
    artifacts = artifacts,
    summary = summary,
    logs = job_logs
  )
  write_json_atomic(payload, results_file)
  write_status(state = "completed", progress = 100, message = "Analyse terminée.", extra = list(summary = summary, artifacts = artifacts))
  invisible(payload)
}

preview_simi_terms_batch <- function() {
  config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)

  write_status(state = "running", progress = 3, message = "Initialisation du preview similitudes.")
  log_info(paste0("output_dir = ", output_dir), progress = 4)
  log_info("Import du corpus.", progress = 8)
  corpus_importe <- import_corpus_iramuteq(input_path)
  log_info(paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_importe)), progress = 10)

  classif_mode <- scalar_chr(config$iramuteq_classif_mode, "simple")
  if (!classif_mode %in% c("simple", "double")) classif_mode <- "simple"
  if (identical(classif_mode, "double")) {
    segmented_corpus <- split_segments_double_rst(
      corpus_importe,
      rst1 = scalar_int(config$iramuteq_rst1, 12L, 2L),
      rst2 = scalar_int(config$iramuteq_rst2, 14L, 2L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  } else {
    segmented_corpus <- split_segments(
      corpus_importe,
      segment_size = scalar_int(config$segment_size, 40L, 1L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  }

  pipeline <- preparer_pipeline_chd(segmented_corpus, config)
  simi_terms <- get_simi_terms_choices_batch(pipeline$dfm_obj)
  payload <- list(
    success = TRUE,
    terms = simi_terms$terms,
    ordered_terms = unname(as.character(simi_terms$ordered_terms)),
    logs = job_logs
  )
  write_json_atomic(payload, results_file)
  write_status(state = "completed", progress = 100, message = "Prévisualisation des similitudes terminée.")
  invisible(payload)
}

mode <- scalar_chr(args$mode, "run")
if (identical(mode, "preview_simi_terms")) {
  tryCatch(
    preview_simi_terms_batch(),
    error = function(e) {
      message <- conditionMessage(e)
      log_info(paste0("ERREUR: ", message))
      write_status(state = "failed", progress = 100, message = message)
      payload <- list(success = FALSE, message = message, logs = job_logs)
      write_json_atomic(payload, results_file)
      quit(save = "no", status = 1)
    }
  )
  quit(save = "no", status = 0)
}

tryCatch(
  run_batch(),
  error = function(e) {
    log_info(paste0("ERREUR: ", conditionMessage(e)))
    write_status(state = "failed", progress = 100, message = conditionMessage(e))
    write_json_atomic(
      list(
        success = FALSE,
        output_dir = output_dir,
        message = conditionMessage(e),
        logs = job_logs
      ),
      results_file
    )
    quit(status = 1)
  }
)
