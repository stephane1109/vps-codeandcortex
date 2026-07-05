library(bslib)
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

source("nettoyage.R", encoding = "UTF-8", local = TRUE)
source("concordancier.R", encoding = "UTF-8", local = TRUE)
source("R/utils_general.R", encoding = "UTF-8", local = TRUE)
source("R/utils_logging.R", encoding = "UTF-8", local = TRUE)
source("R/segmentation_helpers.R", encoding = "UTF-8", local = TRUE)
source("R/nlp_language.R", encoding = "UTF-8", local = TRUE)
source("R/afc_chd.R", encoding = "UTF-8", local = TRUE)
source("R/chdrainette_core.R", encoding = "UTF-8", local = TRUE)
source("R/rainette_explor_native.R", encoding = "UTF-8", local = TRUE)
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

server <- function(input, output, session) {
  run_rainette_explor_page_server(input, output, session)

  rv <- reactiveValues(
    logs = "[info] Prêt.",
    statut = "En attente.",
    progression = 0,
    debug_mode = FALSE,
    corpus_importe = NULL,
    corpus_segmente = NULL,
    filtered_corpus = NULL,
    corpus_preview_text = "",
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
    rv$corpus_preview_text <- paste(utils::head(lines, 400), collapse = "\n")
    rv$statut <- "Fichier chargé. Prêt pour l'analyse."
    rv$logs <- "[info] Prêt."
    ajouter_log(rv, paste0("Fichier reçu : ", input$fichier_corpus$name %||% basename(input$fichier_corpus$datapath)))
  }, ignoreNULL = TRUE)

  observeEvent(input$lancer, {
    rv$logs <- "[info] Prêt."
    rv$statut <- "Préparation de l'analyse."
    rv$progression <- 0
    rv$debug_mode <- isTRUE(input$debug_mode)
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

    params <- list(
      mode_decoupage = as.character(input$mode_decoupage %||% "segment_size"),
      segment_size = as.integer(input$segment_size %||% 40L),
      langue_corpus = as.character(input$langue_corpus %||% "fr"),
      retirer_stopwords = isTRUE(input$retirer_stopwords),
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
      ajouter_log(rv, "Analyse CHD terminée.")
      showNotification("Analyse CHD Rainette terminée.", type = "message", duration = 5)
    }, error = function(e) {
      rv$statut <- paste0("Erreur : ", conditionMessage(e))
      ajouter_log(rv, paste0("ERREUR : ", conditionMessage(e)))
      rv$progression <- 0
      showNotification(conditionMessage(e), type = "error", duration = 8)
    })
  })

  output$statut <- renderText(rv$statut)
  output$logs <- renderText(rv$logs)

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
    if (!isTRUE(input$retirer_stopwords)) {
      return(tags$p(class = "text-muted small", "Stopwords quanteda désactivés pour cette analyse."))
    }

    sw <- obtenir_stopwords_quanteda(cfg$code, rv = NULL)
    tags$div(
      class = "input-help-box",
      tags$span(class = "input-help-label", "Stopwords quanteda"),
      tags$span(class = "input-help-value", paste0(length(sw), " termes chargés en ", cfg$libelle, "."))
    )
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

  output$ui_debug_status <- renderUI({
    badges <- list(
      tags$span(class = "debug-pill", if (isTRUE(rv$debug_mode)) "Mode debug actif" else "Mode debug standard"),
      tags$span(class = "debug-pill", paste0("Stopwords quanteda : ", if (isTRUE(input$retirer_stopwords)) "oui" else "non")),
      tags$span(class = "debug-pill", paste0("Langue : ", configurer_langue_corpus(input$langue_corpus %||% "fr")$libelle))
    )
    tags$div(class = "debug-strip", badges)
  })

  output$ui_langue_detection <- renderUI({
    textes <- NULL
    if (!is.null(rv$filtered_corpus)) {
      textes <- as.character(rv$filtered_corpus)
    } else if (nzchar(rv$corpus_preview_text)) {
      textes <- strsplit(rv$corpus_preview_text, "\n", fixed = TRUE)[[1]]
    }
    if (is.null(textes) || !length(textes)) {
      return(tags$p("Détection langue : importe et lance une analyse pour afficher une estimation."))
    }

    est <- estimer_langue_corpus(textes, rv = rv)
    if (is.na(est$code)) {
      return(tags$p("Détection langue : estimation indisponible."))
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
      return(tags$div(class = "alert alert-warning", tags$p(style = "margin:0;", paste0(message, " Langue sélectionnée : ", cfg_sel$libelle, "."))))
    }

    tags$div(class = "alert alert-success", tags$p(style = "margin:0;", paste0(message, " Langue sélectionnée : ", cfg_sel$libelle, ".")))
  })

  output$table_classes <- renderTable({
    req(rv$classes_df)
    rv$classes_df
  }, rownames = FALSE)

  output$table_stats_classe <- renderTable({
    req(rv$res_stats_df, input$classe_resultat)
    classe <- suppressWarnings(as.integer(input$classe_resultat))
    sous_df <- rv$res_stats_df %>%
      filter(Classe == classe) %>%
      arrange(desc(chi2))
    if (!nrow(sous_df)) {
      return(data.frame())
    }
    sous_df[, intersect(c("Terme", "chi2", "p", "frequency", "docprop", "lr"), names(sous_df)), drop = FALSE]
  }, rownames = FALSE)

  output$ui_afc_status <- renderUI({
    if (!is.null(rv$afc_obj)) {
      return(tags$div(class = "alert alert-success", "AFC calculée à partir des classes de la CHD."))
    }
    if (!is.null(rv$afc_error) && nzchar(rv$afc_error)) {
      return(tags$div(class = "alert alert-warning", rv$afc_error))
    }
    tags$p("Lance une analyse CHD pour calculer l'AFC classes-termes.")
  })

  output$plot_afc_classes <- renderPlot({
    req(rv$afc_obj)
    chdrainette_plot_afc_classes(rv$afc_obj)
  }, res = 160, execOnResize = TRUE)

  output$plot_afc_terms <- renderPlot({
    req(rv$afc_obj)
    chdrainette_plot_afc_terms(
      rv$afc_obj,
      top_terms = input$afc_top_terms %||% 80L,
      size_by = input$afc_size_by %||% "Chi2",
      avoid_overlap = isTRUE(input$afc_avoid_overlap)
    )
  }, res = 160, execOnResize = TRUE)

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

    cards <- lapply(seq_len(nrow(sous_df)), function(index) {
      row <- sous_df[index, , drop = FALSE]
      src <- build_resource_url(rv, row$src[[1]])
      card(
        full_screen = TRUE,
        card_header(if (identical(row$type[[1]], "chi2")) "Nuage de mots chi2" else "Nuage de mots fréquence"),
        tags$img(src = src, style = "width:100%; height:auto; display:block; border-radius:12px;")
      )
    })

    do.call(tagList, cards)
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
        style = "width:100%; min-height:720px; border:1px solid rgba(47, 36, 28, 0.08); border-radius:16px; background:#fffdf9;"
      )
    )
  })

  output$ui_exports_links <- renderUI({
    if (is.null(rv$zip_file) || !file.exists(rv$zip_file)) {
      return(tags$p("L'archive globale sera disponible ici après la fin d'une analyse."))
    }
    tagList(
      tags$p(tags$strong("Archive prête : "), basename(rv$zip_file)),
      tags$p(
        class = "text-muted small",
        "Cette archive ZIP regroupe l'ensemble des sorties produites par l'analyse : tableaux, concordancier HTML, images et fichiers Rainette."
      )
    )
  })

  output$ui_rainette_explor_frame <- renderUI({
    if (is.null(rv$bundle_file) || !file.exists(rv$bundle_file)) {
      return(tags$p("Lance une analyse pour ouvrir ici le vrai rainette_explor."))
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
        style = paste(
          "width:100%;",
          "min-height:82vh;",
          "border:1px solid rgba(31, 35, 40, 0.08);",
          "border-radius:16px;",
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
