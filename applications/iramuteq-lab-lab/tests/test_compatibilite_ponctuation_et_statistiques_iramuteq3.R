# Test des options d'élision, de ponctuation et des statistiques générales.
# Références : corpus.py, firstclean(), doapos(), gettotocc(), make_uces().
# Les deux anciens modes de segmentation conservent leur configuration.

if (!requireNamespace("quanteda", quietly = TRUE)) stop("quanteda requis.")
if (!requireNamespace("Matrix", quietly = TRUE)) stop("Matrix requis.")

source(file.path("backend", "r", "pipeline_utilitaires.R"))
source(file.path("iramuteqlite", "nettoyage_iramuteq.R"))
source(file.path("backend", "r", "pipeline_corpus.R"))
source(file.path("backend", "r", "pipeline_pretraitement.R"))

log_info <- function(...) invisible(NULL)
repo_root <- getwd()
corpus <- quanteda::corpus(
  data.frame(
    doc_id = c("doc_1", "doc_2"),
    text = c("L'auteur écrit... et parle, c'est vrai !",
             "Les enfants regardent… et répondent.")
  )
)
quanteda::docvars(corpus, "*theme") <- c("texte", "discours")
options <- list(
  source_dictionnaire = "lexique_fr",
  expression_utiliser_dictionnaire = FALSE,
  nettoyage_caracteres = FALSE,
  supprimer_chiffres = FALSE,
  supprimer_apostrophes = TRUE,
  remplacer_tirets_espaces = FALSE,
  labbe_pretraitement_iramuteq = FALSE,
  filtrage_morpho = FALSE,
  retirer_stopwords = FALSE,
  lexique_utiliser_lemmes = FALSE,
  supprimer_ponctuation = TRUE,
  min_docfreq = 1L,
  mode_segmentation = "iramuteq_3"
)

# L'élision reste comptée, contrairement à l'ancien traitement effaçant l'.
prep <- preparer_corpus_avant_segmentation_iramuteq3(corpus, options)
txt <- as.character(prep$corpus)[[1L]]
stopifnot(grepl("l auteur", txt, fixed = TRUE))
stopifnot(grepl("c est", txt, fixed = TRUE))
stopifnot(grepl("£$£", txt, fixed = TRUE))
stopifnot(identical(quanteda::docvars(prep$corpus, "*theme"),
                    quanteda::docvars(corpus, "*theme")))

# L'option existante permet aussi de ne pas transformer les apostrophes.
options$supprimer_apostrophes <- FALSE
prep_sans_apos <- preparer_corpus_avant_segmentation_iramuteq3(corpus, options)
stopifnot(grepl("l'auteur", as.character(prep_sans_apos$corpus)[[1L]], fixed = TRUE))
options$supprimer_apostrophes <- TRUE

# firstclean() crée £$£ ; docharact() peut ensuite éliminer ce marqueur.
options$nettoyage_caracteres <- TRUE
prep_nettoye <- preparer_corpus_avant_segmentation_iramuteq3(corpus, options)
stopifnot(!grepl("£$£", as.character(prep_nettoye$corpus)[[1L]], fixed = TRUE))
options$nettoyage_caracteres <- FALSE

# Les séparateurs du logiciel sont supprimés après la recherche de coupure.
avant <- .segmenter_iramuteq_3(c("un", "deux", ".", "trois", "£$£"), 3L, FALSE)
apres <- .segmenter_iramuteq_3(c("un", "deux", ".", "trois", "£$£"), 3L, TRUE)
stopifnot(grepl("£$£", paste(avant, collapse = " "), fixed = TRUE))
stopifnot(!grepl("£$£", paste(apres, collapse = " "), fixed = TRUE))
stopifnot(!grepl(" . ", paste(apres, collapse = " "), fixed = TRUE))

# Les formes générales sont mesurées avant lemmatisation et filtrages.
tok <- quanteda::tokens(c("le chat voit le chat", "le chien voit"))
st <- calculer_statistiques_generales_corpus(tok)
stopifnot(identical(as.numeric(st$n_tokens), 8))
stopifnot(identical(as.integer(st$n_formes), 4L))
stopifnot(identical(as.integer(st$n_hapax), 1L))

# Le mode historique reste distinct, sans modification de sa segmentation.
stopifnot(identical(normaliser_mode_segmentation(NULL, TRUE),
                    "ponctuation_prioritaire"))
stopifnot(identical(normaliser_mode_segmentation(NULL, FALSE),
                    "taille_fixe"))
cat("Ponctuation, élisions et statistiques générales : OK\n")
