# Rôle du fichier: iramuteq-lite/ui_options_iramuteq.R définit les options UI
# spécifiques au mode IRaMuTeQ-like.

ui_options_iramuteq <- function(defaults = NULL) {
  valeur_defaut <- function(id, fallback) {
    if (is.null(defaults) || is.null(defaults[[id]]) || (length(defaults[[id]]) == 1 && is.na(defaults[[id]]))) {
      return(fallback)
    }
    defaults[[id]]
  }
  tagList(
    tags$div(class = "sidebar-section-title", "Paramètres CHD (IRaMuTeQ-lite)"),
    numericInput("k_iramuteq", "Nombre de classes terminales de la phase 1", value = valeur_defaut("k_iramuteq", 10), min = 2, step = 1),
    numericInput(
      "iramuteq_max_formes",
      "Nombre maximum de forme analysées",
      value = valeur_defaut("iramuteq_max_formes", 20000),
      min = 1,
      step = 100
    ),
    radioButtons(
      "iramuteq_mincl_mode",
      tagList(
        "Nombre minimum d'UCE par classe terminale (mincl)",
        tags$div(
          style = "color: #c00; font-size: 0.9em; margin-top: 4px;",
          "Ce paramètre définit le seuil minimal d'UCE pour conserver une classe terminale."
        )
      ),
      choices = c("Automatique" = "auto", "Manuel" = "manuel"),
      selected = valeur_defaut("iramuteq_mincl_mode", "auto"),
      inline = FALSE
    ),
    conditionalPanel(
      condition = "input.iramuteq_mincl_mode == 'manuel'",
      numericInput("iramuteq_mincl", "mincl (manuel)", value = valeur_defaut("iramuteq_mincl", 5), min = 1, step = 1)
    ),
    radioButtons(
      "iramuteq_classif_mode",
      "Type de classification terminale",
      choices = c("Simple" = "simple", "Double" = "double"),
      selected = valeur_defaut("iramuteq_classif_mode", "simple"),
      inline = FALSE
    ),
    conditionalPanel(
      condition = "input.iramuteq_classif_mode == 'double'",
      numericInput("iramuteq_rst1", "Taille de rst1", value = valeur_defaut("iramuteq_rst1", 12), min = 2, step = 1),
      numericInput("iramuteq_rst2", "Taille de rst2", value = valeur_defaut("iramuteq_rst2", 14), min = 2, step = 1)
    ),
    selectInput(
      "iramuteq_svd_method",
      "Méthode SVD",
      choices = c("irlba" = "irlba", "svdR" = "svdR"),
      selected = valeur_defaut("iramuteq_svd_method", "irlba")
    ),
    selectInput(
      "iramuteq_stats_mode",
      "Calcul des statistiques CHD",
      choices = choix_mode_stats_chd_iramuteq(),
      selected = valeur_defaut("iramuteq_stats_mode", "vectorise")
    )
  )
}
