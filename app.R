library(dplyr)
library(htmltools)
library(quanteda)
library(quanteda.textstats)
library(rainette)
library(shiny)
library(wordcloud)
library(RColorBrewer)

options(
  shiny.maxRequestSize = 300 * 1024^2,
  bspm.sudo = TRUE,
  stringsAsFactors = FALSE
)

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) {
    return(right)
  }
  left
}

DISPLAY_MAX_TABLE_ROWS <- 300L
DISPLAY_MAX_LOG_LINES <- 250L
DISPLAY_MAX_PREVIEW_LINES <- 30L

format_count_fr <- function(value) {
  format(as.integer(value), big.mark = " ", scientific = FALSE, trim = TRUE)
}

limit_display_rows <- function(df, max_rows = DISPLAY_MAX_TABLE_ROWS) {
  if (!is.data.frame(df)) {
    df <- as.data.frame(df, stringsAsFactors = FALSE)
  }
  utils::head(df, max_rows)
}

sanitize_cache_token <- function(value) {
  value <- paste(as.character(value), collapse = "_")
  value <- gsub("[^A-Za-z0-9_-]+", "_", value)
  value <- gsub("_+", "_", value)
  value <- gsub("^_|_$", "", value)
  if (!nzchar(value)) {
    return("value")
  }
  value
}

afc_screen_cache_dir <- function(rv) {
  base_dir <- rv$export_dir
  if (is.null(base_dir) || !nzchar(base_dir)) {
    base_dir <- tempdir()
  }
  cache_dir <- file.path(base_dir, "afc", "screen_cache")
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  cache_dir
}

render_afc_png_once <- function(path, plot_expr, width = 1800L, height = 1300L, res = 120L) {
  if (!file.exists(path)) {
    dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
    grDevices::png(path, width = width, height = height, res = res)
    tryCatch(force(plot_expr), finally = grDevices::dev.off())
  }
  path
}

image_response <- function(path, alt) {
  list(
    src = path,
    contentType = "image/png",
    width = "100%",
    alt = alt
  )
}

source("nettoyage.R", encoding = "UTF-8", local = TRUE)
source("concordancier.R", encoding = "UTF-8", local = TRUE)
source("R/utils_general.R", encoding = "UTF-8", local = TRUE)
source("R/utils_logging.R", encoding = "UTF-8", local = TRUE)
source("R/segmentation_helpers.R", encoding = "UTF-8", local = TRUE)
source("R/nlp_language.R", encoding = "UTF-8", local = TRUE)
source("R/afc_chd.R", encoding = "UTF-8", local = TRUE)
source("R/chdrainette_core.R", encoding = "UTF-8", local = TRUE)
source("R/rainette_explor_native.R", encoding = "UTF-8", local = TRUE)
source("R/ticket_gate.R", encoding = "UTF-8", local = TRUE)
source("ui.R", encoding = "UTF-8", local = TRUE)

ui <- function(request) {
  if (isTRUE(chdrainette_is_rainette_explor_request(request))) {
    return(chdrainette_rainette_explor_ui(request))
  }
  build_main_ui()
}

render_markdown_or_message <- function(path, fallback) {
  if (file.exists(path)) {
    return(includeMarkdown(path))
  }
  tags$p(fallback)
}

ensure_exports_resource_path <- function(rv) {
  if (is.null(rv$export_dir) || !nzchar(rv$export_dir)) {
    return(FALSE)
  }
  if (is.null(rv$exports_prefix) || !nzchar(rv$exports_prefix)) {
    return(FALSE)
  }
  if (!(rv$exports_prefix %in% names(shiny::resourcePaths()))) {
    shiny::addResourcePath(rv$exports_prefix, rv$export_dir)
  }
  TRUE
}

build_resource_url <- function(rv, relative_path) {
  if (is.null(rv$exports_prefix) || !nzchar(rv$exports_prefix)) {
    return(NULL)
  }
  paste0(rv$exports_prefix, "/", relative_path)
}

nom_fichier_corpus <- function(fichier_corpus) {
  if (is.null(fichier_corpus)) {
    return(NULL)
  }
  nom <- fichier_corpus$name %||% basename(fichier_corpus$datapath %||% "")
  nom <- as.character(nom)
  if (!length(nom) || !nzchar(nom[[1]])) {
    return(NULL)
  }
  nom[[1]]
}

decrire_nettoyage_lexical <- function(mode_nettoyage_lexical,
                                      langue_corpus,
                                      lexique_utiliser_lemmes,
                                      pos_lexique_a_conserver,
                                      morpho_conserver_hors_lexique,
                                      morpho_exclure_etre_verbe) {
  mode_nettoyage_lexical <- as.character(mode_nettoyage_lexical %||% "stopwords_quanteda")
  if (!mode_nettoyage_lexical %in% c("stopwords_quanteda", "lexique_iramuteq", "aucun")) {
    mode_nettoyage_lexical <- "stopwords_quanteda"
  }

  cfg <- configurer_langue_corpus(langue_corpus %||% "fr")
  if (identical(mode_nettoyage_lexical, "stopwords_quanteda")) {
    sw <- obtenir_stopwords_quanteda(cfg$code, rv = NULL)
    return(paste0(
      "Nettoyage sélectionné : stopwords quanteda (",
      cfg$libelle,
      ", ",
      length(sw),
      " termes)."
    ))
  }

  if (identical(mode_nettoyage_lexical, "lexique_iramuteq")) {
    lex_info <- tryCatch(
      {
        lexique <- charger_lexique_fr_iramuteq(rv = NULL)
        paste0(format_count_fr(nrow(lexique)), " entrées lexique_fr")
      },
      error = function(e) paste0("lexique indisponible : ", conditionMessage(e))
    )
    categories <- normaliser_selection_morpho_iramuteq(pos_lexique_a_conserver)
    lemmes <- if (isTRUE(lexique_utiliser_lemmes)) "lemmatisation active" else "lemmatisation désactivée"
    hors_lexique <- if (isTRUE(morpho_conserver_hors_lexique)) {
      "formes hors lexique conservées"
    } else {
      "formes hors lexique exclues"
    }
    exclusion_etre <- if (isTRUE(morpho_exclure_etre_verbe)) {
      "; formes du verbe être exclues"
    } else {
      ""
    }
    note_langue <- if (!identical(cfg$code, "fr")) {
      " Attention : lexique_fr est un dictionnaire français."
    } else {
      ""
    }

    return(paste0(
      "Nettoyage sélectionné : dictionnaire IRaMuTeQ-lite (",
      lex_info,
      "; ",
      lemmes,
      "; catégories ",
      paste(categories, collapse = ", "),
      "; ",
      hors_lexique,
      exclusion_etre,
      ").",
      note_langue
    ))
  }

  "Nettoyage sélectionné : aucun nettoyage lexical supplémentaire."
}

rafraichir_logs_configuration <- function(rv, input) {
  rv$logs <- "[info] Prêt."
  nom_fichier <- nom_fichier_corpus(input$fichier_corpus)
  if (!is.null(nom_fichier)) {
    ajouter_log(rv, paste0("Fichier reçu : ", nom_fichier))
  }
  ajouter_log(
    rv,
    decrire_nettoyage_lexical(
      mode_nettoyage_lexical = input$mode_nettoyage_lexical,
      langue_corpus = input$langue_corpus,
      lexique_utiliser_lemmes = input$lexique_utiliser_lemmes,
      pos_lexique_a_conserver = input$pos_lexique_a_conserver,
      morpho_conserver_hors_lexique = input$morpho_conserver_hors_lexique,
      morpho_exclure_etre_verbe = input$morpho_exclure_etre_verbe
    )
  )
}

server <- function(input, output, session) {
  run_rainette_explor_page_server(input, output, session)

  ticket_cfg <- ticket_config("chdrainette", "CHD Rainette")
  ticket_snapshot_state <- reactiveVal(list(
    enabled = ticket_cfg$enabled,
    ticket_id = NULL,
    statut = "boot",
    position = NULL,
    active = 0L,
    queued = 0L,
    max_active = ticket_cfg$max_active,
    wait_refresh_ms = ticket_cfg$wait_refresh_ms,
    heartbeat_ms = ticket_cfg$heartbeat_ms,
    message = "Initialisation du contrôle d'accès."
  ))

  rv <- reactiveValues(
    logs = "[info] Prêt.",
    statut = "En attente.",
    progression = 0,
    debug_mode = FALSE,
    corpus_importe = NULL,
    corpus_segmente = NULL,
    filtered_corpus = NULL,
    corpus_preview_text = "",
    analyse_en_cours = FALSE,
    dfm = NULL,
    res = NULL,
    res_stats_df = NULL,
    classes_df = NULL,
    clusters = integer(0),
    base_dir = NULL,
    export_dir = NULL,
    exports_prefix = paste0("exports_", session$token),
    file_stem = "chdrainette",
    segments_file = NULL,
    stats_file = NULL,
    html_file = NULL,
    zip_file = NULL,
    bundle_file = NULL,
    bundle_script_file = NULL,
    wordclouds = NULL,
    afc_obj = NULL,
    afc_error = NULL,
    afc_files = NULL,
    params_used = NULL
  )

  refresh_ticket_snapshot <- function(force_resume = FALSE) {
    if (!isTRUE(ticket_cfg$enabled)) {
      snap <- ticket_disabled_snapshot(ticket_cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0.")
      ticket_snapshot_state(snap)
      return(snap)
    }

    if (force_resume) {
      ticket_set_released(session, FALSE)
    } else if (ticket_is_released(session)) {
      snap <- ticket_released_snapshot(ticket_cfg, "Accès libéré pour cette page.")
      ticket_snapshot_state(snap)
      return(snap)
    }

    snap <- tryCatch(
      ticket_claim_or_refresh(ticket_cfg, ticket_session_id(session)),
      error = function(exc) {
        diagnostic <- ticket_safe_runtime_diagnostic(ticket_cfg, conditionMessage(exc))
        if (isTRUE(ticket_cfg$fail_open)) {
          ticket_local_fallback_snapshot(ticket_cfg, diagnostic)
        } else {
          ticket_error_snapshot(ticket_cfg, diagnostic)
        }
      }
    )
    ticket_snapshot_state(snap)
    snap
  }

  output$ui_ticket_sidebar <- renderUI({
    ticket_sidebar_ui(ticket_snapshot_state())
  })

  output$ui_ticket_release_hook <- renderUI({
    ticket_snapshot_state()
    ticket_release_hook_ui(ticket_cfg, session)
  })

  refresh_ticket_snapshot()

  ticket_refresh_timer <- reactiveTimer(max(2000L, min(ticket_cfg$wait_refresh_ms, ticket_cfg$heartbeat_ms)), session)

  observe({
    ticket_refresh_timer()
    snap <- isolate(ticket_snapshot_state())
    if (!isTRUE(ticket_cfg$enabled)) {
      return(invisible(NULL))
    }
    if (identical(snap$statut, "released")) {
      return(invisible(NULL))
    }
    refresh_ticket_snapshot()
  })

  observeEvent(input$ticket_release_btn, {
    released <- ticket_release(ticket_cfg, ticket_session_id(session))
    if (isTRUE(released)) {
      ticket_set_released(session, TRUE)
      ticket_snapshot_state(ticket_released_snapshot(ticket_cfg, "Accès libéré pour cette page."))
      showNotification("Accès libéré.", type = "message", duration = 4)
    } else {
      showNotification("Impossible de libérer le ticket courant pour le moment.", type = "warning", duration = 6)
    }
  })

  observeEvent(input$ticket_leave_waiting_btn, {
    released <- ticket_release(ticket_cfg, ticket_session_id(session))
    if (isTRUE(released)) {
      ticket_set_released(session, TRUE)
      ticket_snapshot_state(ticket_released_snapshot(ticket_cfg, "File d'attente quittée pour cette page."))
      showNotification("File d'attente quittée.", type = "message", duration = 4)
    } else {
      showNotification("Impossible de quitter la file d'attente pour le moment.", type = "warning", duration = 6)
    }
  })

  observeEvent(input$ticket_resume_btn, {
    ticket_resume_session(session)
    refresh_ticket_snapshot(force_resume = TRUE)
  })

  session$onSessionEnded(function() {
    try(ticket_release(ticket_cfg, ticket_session_id(session)), silent = TRUE)
  })

  observeEvent(input$fichier_corpus, {
    req(input$fichier_corpus$datapath)
    if (!file.exists(input$fichier_corpus$datapath)) {
      rv$corpus_preview_text <- ""
      rv$statut <- "Fichier introuvable après sélection."
      return(invisible(NULL))
    }
    lines <- tryCatch(
      readLines(input$fichier_corpus$datapath, warn = FALSE, encoding = "UTF-8"),
      error = function(e) character(0)
    )
    rv$corpus_preview_text <- paste(utils::head(lines, DISPLAY_MAX_PREVIEW_LINES), collapse = "\n")
    rv$statut <- "Fichier chargé. Prêt pour l'analyse."
    rafraichir_logs_configuration(rv, input)
  }, ignoreNULL = TRUE)

  observeEvent({
    list(
      input$mode_nettoyage_lexical,
      input$langue_corpus,
      input$lexique_utiliser_lemmes,
      input$pos_lexique_a_conserver,
      input$morpho_conserver_hors_lexique,
      input$morpho_exclure_etre_verbe
    )
  }, {
    if (isTRUE(rv$analyse_en_cours)) {
      return(invisible(NULL))
    }
    if (is.null(input$fichier_corpus) || is.null(input$fichier_corpus$datapath)) {
      return(invisible(NULL))
    }
    rv$statut <- "Paramètres mis à jour. Prêt pour l'analyse."
    rafraichir_logs_configuration(rv, input)
  }, ignoreInit = TRUE)

  observeEvent(input$lancer, {
    current_ticket <- isolate(ticket_snapshot_state())
    if (isTRUE(ticket_cfg$enabled) && !identical(current_ticket$statut, "actif")) {
      rv$statut <- "Attente du ticket utilisateur."
      showNotification("L'application n'est pas encore disponible pour cette session.", type = "warning", duration = 6)
      return(invisible(NULL))
    }

    rv$logs <- "[info] Prêt."
    rv$statut <- "Préparation de l'analyse."
    rv$progression <- 0
    rv$debug_mode <- isTRUE(input$debug_mode)
    rv$analyse_en_cours <- FALSE
    rv$corpus_importe <- NULL
    rv$corpus_segmente <- NULL
    rv$filtered_corpus <- NULL
    rv$dfm <- NULL
    rv$res <- NULL
    rv$res_stats_df <- NULL
    rv$classes_df <- NULL
    rv$clusters <- integer(0)
    rv$segments_file <- NULL
    rv$stats_file <- NULL
    rv$html_file <- NULL
    rv$zip_file <- NULL
    rv$bundle_file <- NULL
    rv$bundle_script_file <- NULL
    rv$wordclouds <- NULL
    rv$afc_obj <- NULL
    rv$afc_error <- NULL
    rv$afc_files <- NULL
    rv$params_used <- NULL

    if (is.null(input$fichier_corpus) || is.null(input$fichier_corpus$datapath) || !file.exists(input$fichier_corpus$datapath)) {
      rv$statut <- "Aucun fichier texte n'a été importé."
      showNotification("Importe un corpus texte avant de lancer l'analyse.", type = "error", duration = 6)
      return(invisible(NULL))
    }

    mode_nettoyage_lexical <- as.character(input$mode_nettoyage_lexical %||% "stopwords_quanteda")
    if (!mode_nettoyage_lexical %in% c("stopwords_quanteda", "lexique_iramuteq", "aucun")) {
      mode_nettoyage_lexical <- "stopwords_quanteda"
    }

    params <- list(
      mode_decoupage = as.character(input$mode_decoupage %||% "segment_size"),
      segment_size = as.integer(input$segment_size %||% 40L),
      langue_corpus = as.character(input$langue_corpus %||% "fr"),
      mode_nettoyage_lexical = mode_nettoyage_lexical,
      retirer_stopwords = identical(mode_nettoyage_lexical, "stopwords_quanteda"),
      lexique_utiliser_lemmes = isTRUE(input$lexique_utiliser_lemmes),
      pos_lexique_a_conserver = input$pos_lexique_a_conserver %||% c("NOM", "VER", "ADJ"),
      morpho_conserver_hors_lexique = isTRUE(input$morpho_conserver_hors_lexique),
      morpho_exclure_etre_verbe = isTRUE(input$morpho_exclure_etre_verbe),
      debug_mode = isTRUE(input$debug_mode),
      nettoyage_caracteres = isTRUE(input$nettoyage_caracteres),
      supprimer_ponctuation = isTRUE(input$supprimer_ponctuation),
      supprimer_chiffres = isTRUE(input$supprimer_chiffres),
      supprimer_apostrophes = isTRUE(input$supprimer_apostrophes),
      forcer_minuscules_avant = isTRUE(input$forcer_minuscules_avant),
      k = as.integer(input$k %||% 6L),
      min_segment_size = as.integer(input$min_segment_size %||% 0L),
      min_split_members = as.integer(input$min_split_members %||% 10L),
      min_docfreq = as.integer(input$min_docfreq %||% 1L),
      max_p = as.numeric(input$max_p %||% 0.05),
      top_n = as.integer(input$top_n %||% 20L)
    )

    ajouter_log(rv, paste0("Fichier analysé : ", nom_fichier_corpus(input$fichier_corpus) %||% basename(input$fichier_corpus$datapath)))
    ajouter_log(
      rv,
      decrire_nettoyage_lexical(
        mode_nettoyage_lexical = params$mode_nettoyage_lexical,
        langue_corpus = params$langue_corpus,
        lexique_utiliser_lemmes = params$lexique_utiliser_lemmes,
        pos_lexique_a_conserver = params$pos_lexique_a_conserver,
        morpho_conserver_hors_lexique = params$morpho_conserver_hors_lexique,
        morpho_exclure_etre_verbe = params$morpho_exclure_etre_verbe
      )
    )

    rv$analyse_en_cours <- TRUE
    tryCatch({
      result <- run_chdrainette_analysis(
        input_path = input$fichier_corpus$datapath,
        original_name = input$fichier_corpus$name %||% basename(input$fichier_corpus$datapath),
        params = params,
        rv = rv,
        session_token = session$token
      )

      rv$corpus_importe <- result$corpus_importe
      rv$corpus_segmente <- result$corpus_segmente
      rv$filtered_corpus <- result$filtered_corpus
      rv$dfm <- result$dfm
      rv$res <- result$res
      rv$res_stats_df <- result$res_stats_df
      rv$classes_df <- result$classes_df
      rv$clusters <- result$clusters
      rv$base_dir <- result$base_dir
      rv$export_dir <- result$export_dir
      rv$file_stem <- result$file_stem
      rv$segments_file <- result$segments_file
      rv$stats_file <- result$stats_file
      rv$html_file <- result$html_file
      rv$zip_file <- result$zip_file
      rv$bundle_file <- result$bundle_file
      rv$bundle_script_file <- result$bundle_script_file
      rv$wordclouds <- result$wordclouds
      rv$afc_obj <- result$afc_obj
      rv$afc_error <- result$afc_error
      rv$afc_files <- result$afc_files
      rv$params_used <- result$params_used

      ensure_exports_resource_path(rv)

      if (length(rv$clusters) > 0) {
        updateSelectInput(session, "classe_resultat", choices = as.character(rv$clusters), selected = as.character(rv$clusters[[1]]))
      }

      rv$progression <- 100
      rv$statut <- "Analyse terminée."
      rv$analyse_en_cours <- FALSE
      ajouter_log(rv, "Analyse CHD terminée.")
      showNotification("Analyse CHD Rainette terminée.", type = "message", duration = 5)
    }, error = function(e) {
      rv$statut <- paste0("Erreur : ", conditionMessage(e))
      rv$analyse_en_cours <- FALSE
      ajouter_log(rv, paste0("ERREUR : ", conditionMessage(e)))
      rv$progression <- 0
      showNotification(conditionMessage(e), type = "error", duration = 8)
    })
  })

  output$statut <- renderText(rv$statut)
  output$logs <- renderText({
    logs <- rv$logs %||% ""
    lines <- strsplit(logs, "\n", fixed = TRUE)[[1]]
    if (length(lines) <= DISPLAY_MAX_LOG_LINES) {
      return(logs)
    }
    paste(
      c(
        paste0("[affichage limité aux ", DISPLAY_MAX_LOG_LINES, " dernières lignes pour garder l'interface réactive]"),
        utils::tail(lines, DISPLAY_MAX_LOG_LINES)
      ),
      collapse = "\n"
    )
  })

  output$barre_progression <- renderUI({
    valeur <- max(0, min(100, as.integer(rv$progression %||% 0L)))
    tags$div(
      class = "progress-wrapper",
      tags$div(class = "progress-label", paste0("Progression : ", valeur, " %")),
      tags$div(
        class = "progress-shell",
        tags$div(class = "progress-bar-custom", style = paste0("width:", valeur, "%;"))
      )
    )
  })

  output$corpus_meta <- renderUI({
    req(input$fichier_corpus)
    size_kb <- round(as.numeric(input$fichier_corpus$size %||% 0) / 1024, 1)
    tagList(
      tags$p(tags$strong("Fichier : "), input$fichier_corpus$name),
      tags$p(tags$strong("Taille : "), paste0(size_kb, " Ko")),
      tags$p(tags$strong("Documents importés : "), if (is.null(rv$corpus_importe)) "—" else quanteda::ndoc(rv$corpus_importe))
    )
  })

  output$corpus_preview <- renderText({
    if (!nzchar(rv$corpus_preview_text)) {
      return("Importe un corpus texte pour afficher ici l’aperçu du fichier.")
    }
    rv$corpus_preview_text
  })

  output$help_main <- renderUI({
    render_markdown_or_message("help/help.md", "Le fichier help/help.md est introuvable.")
  })

  output$ui_stopwords_info <- renderUI({
    cfg <- configurer_langue_corpus(input$langue_corpus %||% "fr")
    mode_nettoyage <- as.character(input$mode_nettoyage_lexical %||% "stopwords_quanteda")
    if (identical(mode_nettoyage, "stopwords_quanteda")) {
      sw <- obtenir_stopwords_quanteda(cfg$code, rv = NULL)
      return(
        tags$div(
          class = "input-help-box",
          tags$span(class = "input-help-label", "Stopwords quanteda"),
          tags$span(class = "input-help-value", paste0(length(sw), " termes chargés en ", cfg$libelle, "."))
        )
      )
    }

    if (identical(mode_nettoyage, "lexique_iramuteq")) {
      lex_info <- tryCatch(
        {
          lexique <- charger_lexique_fr_iramuteq(rv = NULL)
          paste0(nrow(lexique), " entrées lexique_fr chargées.")
        },
        error = function(e) paste0("Lexique indisponible : ", conditionMessage(e))
      )
      note_langue <- if (!identical(cfg$code, "fr")) {
        " Attention : lexique_fr est un dictionnaire français."
      } else {
        ""
      }
      return(
        tags$div(
          class = "input-help-box",
          tags$span(class = "input-help-label", "Dictionnaire IRaMuTeQ-lite"),
          tags$span(class = "input-help-value", paste0(lex_info, note_langue))
        )
      )
    }

    tags$p(class = "text-muted small", "Aucun nettoyage lexical supplémentaire pour cette analyse.")
  })

  output$metric_docs <- renderText({
    if (is.null(rv$corpus_importe)) return("—")
    quanteda::ndoc(rv$corpus_importe)
  })

  output$metric_segments <- renderText({
    if (is.null(rv$corpus_segmente)) return("—")
    quanteda::ndoc(rv$corpus_segmente)
  })

  output$metric_analyzed <- renderText({
    if (is.null(rv$filtered_corpus)) return("—")
    quanteda::ndoc(rv$filtered_corpus)
  })

  output$metric_classes <- renderText({
    if (!length(rv$clusters)) return("—")
    length(rv$clusters)
  })

  output$ui_langue_detection <- renderUI({
    textes <- NULL
    if (!is.null(rv$filtered_corpus)) {
      textes <- as.character(rv$filtered_corpus)
    } else if (nzchar(rv$corpus_preview_text)) {
      textes <- strsplit(rv$corpus_preview_text, "\n", fixed = TRUE)[[1]]
    }
    if (is.null(textes) || !length(textes)) {
      return(tags$p(class = "language-detection-note", "Détection de la langue : importe puis lance une analyse pour afficher une estimation."))
    }

    est <- estimer_langue_corpus(textes, rv = rv)
    if (is.na(est$code)) {
      return(tags$p(class = "language-detection-note", "Détection de la langue : estimation indisponible."))
    }

    cfg_est <- configurer_langue_corpus(est$code)
    cfg_sel <- configurer_langue_corpus(input$langue_corpus %||% "fr")
    message <- paste0(
      "Langue estimée : ", cfg_est$libelle,
      " (FR=", sprintf("%.3f", est$scores[["fr"]]),
      ", EN=", sprintf("%.3f", est$scores[["en"]]),
      ", ES=", sprintf("%.3f", est$scores[["es"]]), ")."
    )

    if (!identical(cfg_est$code, cfg_sel$code)) {
      return(tags$p(class = "language-detection-note is-warning", paste0(message, " Langue sélectionnée : ", cfg_sel$libelle, ".")))
    }

    tags$p(class = "language-detection-note is-ok", paste0(message, " Langue sélectionnée : ", cfg_sel$libelle, "."))
  })

  output$table_classes <- renderTable({
    req(rv$classes_df)
    rv$classes_df
  }, rownames = FALSE)

  stats_classe_display <- reactive({
    req(rv$res_stats_df, input$classe_resultat)
    classe <- suppressWarnings(as.integer(input$classe_resultat))
    stats_df <- rv$res_stats_df
    sous_df <- stats_df[stats_df$Classe == classe, , drop = FALSE]
    if (!nrow(sous_df)) {
      return(data.frame())
    }
    if ("chi2" %in% names(sous_df)) {
      sous_df <- sous_df[order(-suppressWarnings(as.numeric(sous_df$chi2))), , drop = FALSE]
    }
    columns <- intersect(c("Terme", "chi2", "p", "frequency", "docprop", "lr"), names(sous_df))
    sous_df[, columns, drop = FALSE]
  })

  output$ui_resultats_perf_note <- renderUI({
    req(rv$res_stats_df)
    total <- nrow(rv$res_stats_df)
    tags$p(
      class = "result-note",
      paste0(
        "Affichage rapide : les tableaux longs sont limités à ",
        format_count_fr(DISPLAY_MAX_TABLE_ROWS),
        " lignes à l'écran. Les exports CSV/ZIP restent complets",
        if (!is.null(rv$stats_file) && nzchar(rv$stats_file)) paste0(" (", basename(rv$stats_file), ").") else "."
      ),
      tags$br(),
      paste0("Statistiques complètes calculées : ", format_count_fr(total), " lignes.")
    )
  })

  output$ui_table_stats_note <- renderUI({
    data <- stats_classe_display()
    total <- nrow(data)
    if (!total) {
      return(tags$p(class = "result-note", "Aucune statistique disponible pour cette classe."))
    }
    displayed <- min(total, DISPLAY_MAX_TABLE_ROWS)
    tags$p(
      class = "result-note",
      paste0(
        "Classe ",
        input$classe_resultat,
        " : ",
        format_count_fr(displayed),
        " lignes affichées sur ",
        format_count_fr(total),
        "."
      )
    )
  })

  output$table_stats_classe <- renderTable({
    limit_display_rows(stats_classe_display())
  }, rownames = FALSE)

  output$ui_afc_status <- renderUI({
    if (!is.null(rv$afc_obj)) {
      return(tags$p(class = "afc-status-note is-ok", "AFC calculée à partir des classes de la CHD."))
    }
    if (!is.null(rv$afc_error) && nzchar(rv$afc_error)) {
      return(tags$div(class = "alert alert-warning", rv$afc_error))
    }
    tags$p("Lancez une analyse CHD pour calculer l'AFC classes-termes.")
  })

  output$plot_afc_classes <- renderImage({
    req(rv$afc_obj)
    path <- NULL
    if (!is.null(rv$afc_files$classes_png) && file.exists(rv$afc_files$classes_png)) {
      path <- rv$afc_files$classes_png
    } else {
      path <- file.path(afc_screen_cache_dir(rv), "afc_classes_screen.png")
      render_afc_png_once(path, chdrainette_plot_afc_classes(rv$afc_obj), width = 1600L, height = 1200L)
    }
    image_response(path, "Projection des classes AFC")
  }, deleteFile = FALSE)

  output$plot_afc_terms <- renderImage({
    req(rv$afc_obj)
    top_terms <- max(5L, suppressWarnings(as.integer(input$afc_top_terms %||% 80L)))
    size_by <- as.character(input$afc_size_by %||% "Chi2")
    avoid_overlap <- isTRUE(input$afc_avoid_overlap)

    if (
      identical(top_terms, 80L) &&
        identical(size_by, "Chi2") &&
        isTRUE(avoid_overlap) &&
        !is.null(rv$afc_files$terms_png) &&
        file.exists(rv$afc_files$terms_png)
    ) {
      return(image_response(rv$afc_files$terms_png, "Projection des classes et des termes AFC"))
    }

    path <- file.path(
      afc_screen_cache_dir(rv),
      paste0(
        "afc_terms_",
        sanitize_cache_token(c(top_terms, size_by, avoid_overlap)),
        ".png"
      )
    )
    render_afc_png_once(
      path,
      chdrainette_plot_afc_terms(
        rv$afc_obj,
        top_terms = top_terms,
        size_by = size_by,
        avoid_overlap = avoid_overlap
      ),
      width = 1900L,
      height = 1350L
    )
    image_response(path, "Projection des classes et des termes AFC")
  }, deleteFile = FALSE)

  outputOptions(output, "plot_afc_classes", suspendWhenHidden = TRUE)
  outputOptions(output, "plot_afc_terms", suspendWhenHidden = TRUE)

  output$table_afc_eigenvalues <- renderTable({
    req(rv$afc_obj)
    rv$afc_obj$eigenvalues
  }, rownames = FALSE, digits = 3)

  output$ui_wordclouds <- renderUI({
    req(rv$wordclouds, input$classe_resultat)
    ensure_exports_resource_path(rv)

    classe <- as.character(input$classe_resultat)
    wc_df <- rv$wordclouds
    sous_df <- wc_df[wc_df$classe == classe, , drop = FALSE]
    if (!nrow(sous_df)) {
      return(tags$p("Aucun nuage de mots disponible pour cette classe."))
    }

    sections <- lapply(seq_len(nrow(sous_df)), function(index) {
      row <- sous_df[index, , drop = FALSE]
      src <- build_resource_url(rv, row$src[[1]])
      tags$section(
        class = "plain-section graph-full-page-section wordcloud-full-page",
        tags$h2(
          class = "section-title",
          if (identical(row$type[[1]], "chi2")) "Nuage de mots chi2" else "Nuage de mots fréquence"
        ),
        tags$img(src = src, class = "full-page-image", style = "width:100%; height:auto; display:block; border-radius:0;")
      )
    })

    do.call(tagList, sections)
  })

  output$ui_concordancier <- renderUI({
    req(rv$html_file)
    ensure_exports_resource_path(rv)
    html_name <- basename(rv$html_file)
    src <- build_resource_url(rv, html_name)

    tagList(
      tags$p(
        tags$a(href = src, target = "_blank", rel = "noopener noreferrer", "Ouvrir le concordancier dans un nouvel onglet")
      ),
      tags$iframe(
        src = src,
        class = "full-page-iframe",
        style = "width:100%; min-height:calc(100vh - 11rem); border:0; border-radius:0; background:#ffffff;"
      )
    )
  })

  output$ui_exports_links <- renderUI({
    if (is.null(rv$zip_file) || !file.exists(rv$zip_file)) {
      return(tags$p(class = "archive-placeholder", "L'archive globale sera disponible ici après la fin d'une analyse."))
    }
    tagList(
      tags$p(tags$strong("Archive prête : "), basename(rv$zip_file)),
      tags$p(
        class = "text-muted small",
        "Cette archive ZIP regroupe l'ensemble des sorties produites par l'analyse : tableaux, concordancier HTML, images et fichiers Rainette."
      ),
      tags$div(
        class = "archive-download-action",
        downloadButton("dl_zip", "Télécharger l'archive")
      )
    )
  })

  output$ui_rainette_explor_frame <- renderUI({
    if (is.null(rv$bundle_file) || !file.exists(rv$bundle_file)) {
      return(tags$p(class = "rainette-explor-placeholder", "Lancez une analyse pour ouvrir ici le vrai rainette_explor."))
    }

    src <- chdrainette_rainette_explor_url(rv$bundle_file)
    if (is.null(src) || !nzchar(src)) {
      return(tags$p("Le bundle Rainette n'a pas pu être préparé pour l'explorateur natif."))
    }

    tagList(
      tags$p(
        tags$a(
          href = src,
          target = "_blank",
          rel = "noopener noreferrer",
          "Ouvrir rainette_explor dans un nouvel onglet"
        )
      ),
      tags$iframe(
        src = src,
        class = "full-page-iframe",
        style = paste(
          "width:100%;",
          "min-height:calc(100vh - 11rem);",
          "border:0;",
          "border-radius:0;",
          "background:#ffffff;"
        )
      )
    )
  })

  output$dl_zip <- downloadHandler(
    filename = function() paste0(rv$file_stem %||% "chdrainette", "_exports.zip"),
    content = function(file) file.copy(rv$zip_file, file, overwrite = TRUE)
  )
}

shinyApp(ui, server)
