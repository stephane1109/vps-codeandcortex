# Vérifie l'ordre de traitement du mode IRaMuTeQ 3.0.
# Les anciens modes et les métadonnées des documents sont conservés.

if (!requireNamespace("quanteda", quietly = TRUE)) stop("quanteda requis.")
if (!requireNamespace("Matrix", quietly = TRUE)) stop("Matrix requis.")

source(file.path("backend", "r", "pipeline_utilitaires.R"))
source(file.path("iramuteqlite", "nettoyage_iramuteq.R"))
source(file.path("backend", "r", "pipeline_corpus.R"))
source(file.path("backend", "r", "pipeline_pretraitement.R"))

log_info <- function(...) invisible(NULL)
repo_root <- getwd()
corpus <- quanteda::corpus(
  data.frame(doc_id = "doc_1", text = "SALUT MONDE, bonjour! J'aime.")
)
quanteda::docvars(corpus, "*theme") <- "essai"
config <- list(source_dictionnaire = "lexique_fr",
               expression_utiliser_dictionnaire = FALSE,
               nettoyage_caracteres = TRUE,
               supprimer_chiffres = FALSE,
               supprimer_apostrophes = FALSE,
               remplacer_tirets_espaces = FALSE,
               labbe_pretraitement_iramuteq = FALSE,
               lexique_utiliser_lemmes = FALSE,
               filtrage_morpho = FALSE,
               retirer_stopwords = FALSE, min_docfreq = 1L)

preparation <- preparer_corpus_avant_segmentation_iramuteq3(corpus, config)
texte <- as.character(preparation$corpus)[[1L]]
stopifnot(grepl("salut monde , bonjour !", texte, fixed = TRUE))
stopifnot(grepl("j'aime .", texte, fixed = TRUE))
stopifnot(identical(as.character(corpus)[[1L]], "SALUT MONDE, bonjour! J'aime."))
segments <- split_segments(preparation$corpus, segment_size = 3L,
                           mode_segmentation = "iramuteq_3")
stopifnot(all(quanteda::docvars(segments, "*theme") == "essai"))
pipeline <- preparer_pipeline_chd(segments, config,
                                  preparation_initiale = preparation)
stopifnot("bonjour" %in% quanteda::featnames(pipeline$dfm_obj))

# Tester les expressions AVANT le découpage.
charger_expressions <- function(repo_root, source_dictionnaire = "lexique_fr") {
  data.frame(dic_mot = "salut monde", dic_norm = "salut_monde")
}
config$expression_utiliser_dictionnaire <- TRUE
expr <- preparer_corpus_avant_segmentation_iramuteq3(corpus, config)
stopifnot(grepl("salut_monde", as.character(expr$corpus)[[1L]], fixed = TRUE))
stopifnot(identical(expr$expressions_actives_df$dic_norm[[1L]], "salut_monde"))

rst <- split_segments_double_rst(preparation$corpus, rst1 = 3L,
                                  rst2 = 4L, mode_segmentation = "iramuteq_3")
stopifnot(all(quanteda::docvars(rst, "*theme") == "essai"))
stopifnot(identical(normaliser_mode_segmentation(NULL, TRUE),
                    "ponctuation_prioritaire"))
stopifnot(identical(normaliser_mode_segmentation(NULL, FALSE),
                    "taille_fixe"))
cat("Ordre nettoyages-expressions-segmentation IRaMuTeQ 3.0 : OK\n")
