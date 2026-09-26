# Rôle du fichier: ui_simi_iramuteq.R regroupe l'UI spécifique à l'analyse de similitudes.

ui_form_parametres_similitudes <- function() {
  tagList(
    tags$p(
      "Paramétrez l'analyse de similitudes. ",
      "Ces options prépareront la matrice et l'affichage du graphe de similitude."
    ),
    selectInput(
      "simi_method",
      "Méthode de calcul",
      choices = c(
        "Cooccurrence" = "cooc",
        "Braun-Blanquet" = "Braun-Blanquet",
        "Chi-squared" = "Chi-squared",
        "Correlation" = "correlation",
        "Cosine" = "cosine",
        "Cramer" = "Cramer",
        "Dice" = "Dice",
        "eDice" = "eDice",
        "eJaccard" = "eJaccard",
        "Fager" = "Fager",
        "Faith" = "Faith",
        "Gower" = "Gower",
        "Hamman" = "Hamman",
        "Jaccard" = "Jaccard",
        "Kulczynski1" = "Kulczynski1",
        "Kulczynski2" = "Kulczynski2",
        "Michael" = "Michael",
        "Mountford" = "Mountford",
        "Mozley" = "Mozley",
        "Ochiai" = "Ochiai",
        "Pearson" = "Pearson",
        "Phi" = "Phi",
        "Phi-squared" = "Phi-squared",
        "Russel" = "Russel",
        "Simple matching" = "simple matching",
        "Simpson" = "Simpson",
        "Stiles" = "Stiles",
        "Tanimoto" = "Tanimoto",
        "Tschuprow" = "Tschuprow",
        "Yule" = "Yule",
        "Yule2" = "Yule2"
      ),
      selected = "cooc"
    ),
    numericInput(
      "simi_seuil",
      "Seuil minimal des arêtes (laisser vide pour aucun seuil)",
      value = NA,
      min = 0,
      step = 1
    ),
    numericInput(
      "simi_top_terms",
      "Nombre de termes à conserver (plus fréquents)",
      value = 100,
      min = 5,
      step = 1
    ),
    selectizeInput(
      "simi_terms_selected",
      "Termes à analyser (triés par fréquence)",
      choices = NULL,
      selected = NULL,
      multiple = TRUE,
      options = list(
        placeholder = "Sélectionnez un ou plusieurs termes",
        plugins = list("remove_button")
      )
    ),
    checkboxInput(
      "simi_max_tree",
      "Limiter au graphe couvrant maximal (arbre de poids max)",
      value = TRUE
    ),
    selectInput(
      "simi_layout",
      "Type de layout",
      choices = c(
        "Fruchterman-Reingold" = "frutch",
        "Kamada-Kawai" = "kawa",
        "Circulaire" = "circle",
        "Aléatoire" = "random",
        "Spirale" = "spirale"
      ),
      selected = "frutch"
    ),
    selectInput(
      "simi_graph_engine",
      "Moteur de rendu du graphe",
      choices = c(
        "igraph (statique)" = "igraph",
        "visNetwork (interactif)" = "visnetwork"
      ),
      selected = "igraph"
    ),
    checkboxInput(
      "simi_edge_labels",
      "Afficher le score de l'indice (arêtes / info-bulles)",
      value = TRUE
    ),
    checkboxInput(
      "simi_edge_width_by_index",
      "Largeur des arêtes proportionnelle à l'indice",
      value = TRUE
    ),
    checkboxInput(
      "simi_vertex_text_by_freq",
      "Taille du texte des sommets proportionnelle aux fréquences",
      value = TRUE
    ),
    checkboxInput(
      "simi_communities",
      "Communautés",
      value = TRUE
    ),
    conditionalPanel(
      condition = "input.simi_communities == true",
      selectInput(
        "simi_community_method",
        "Méthode de communautés",
        choices = c(
          "edge.betweenness.community" = "edge_betweenness",
          "fastgreedy.community" = "fast_greedy",
          "label.propagation.community" = "label_propagation",
          "leading.eigenvector.community" = "leading_eigen",
          "multilevel.community" = "multilevel",
          "walktrap.community" = "walktrap"
        ),
        selected = "edge_betweenness"
      ),
      checkboxInput(
        "simi_halo",
        "Halo",
        value = TRUE
      )
    )
  )
}

ui_panel_similitudes_iramuteq <- function() {
  nav_panel(
    "Similitudes", value = "similitudes",
    tags$h3("Analyse de similitudes"),
    tags$p("Ouvrez la boîte de dialogue pour configurer les paramètres de l'analyse."),
    tags$p(
      style = "background:#f8fbff; border:1px solid #d9e2ef; border-radius:6px; padding:10px;",
      "Fonctionnement: le graphe est construit à partir du DFM de l'analyse principale. ",
      "On conserve les N mots les plus fréquents (Top termes), puis on calcule les liens selon l'indice choisi ",
      "(cooccurrence + indices du package proxy). Le seuil supprime les arêtes trop faibles."
    ),
    tags$div(
      style = "display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; align-items:center;",
      actionButton("ouvrir_param_simi", "Paramétrer l'analyse de similitudes", class = "btn-primary")
    ),
    uiOutput("ui_simi_statut"),
    tags$div(
      style = "display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; align-items:center;",
      actionButton("simi_zoom_in", "Zoom +"),
      actionButton("simi_zoom_out", "Zoom -"),
      actionButton("simi_zoom_reset", "Réinitialiser zoom")
    ),
    tags$p(
      style = "margin: 0 0 10px 0; color: #365c8d;",
      "Choisissez le moteur dans les paramètres: igraph (statique) ou visNetwork (interactif). ",
      "En mode visNetwork, ouvrez le panneau 'config' pour adapter dynamiquement le rendu du graphe ",
      "(nœuds, arêtes, physique, layout, interactions, etc.)."
    ),
    tags$div(style = "max-width: 1400px;", uiOutput("plot_simi_container"))
  )
}
