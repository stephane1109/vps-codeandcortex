# Références produites avec corpus.py::decouperlist() du logiciel IRaMuTeQ 3.0.
# Vérifie aussi la conservation de la segmentation fixe et de l'ancien mode.

if (!requireNamespace("quanteda", quietly = TRUE)) stop("Le package quanteda est requis.")
source(file.path("backend", "r", "pipeline_corpus.R"))

stopifnot(identical(normaliser_mode_segmentation("iramuteq_3", TRUE), "iramuteq_3"))
stopifnot(identical(normaliser_mode_segmentation(NULL, TRUE), "ponctuation_prioritaire"))
stopifnot(identical(normaliser_mode_segmentation(NULL, FALSE), "taille_fixe"))

# La référence officielle Python coupe après les positions 7 et 28.
tokens_44 <- paste0("mot", seq_len(44L))
tokens_44[c(7L, 12L, 25L, 28L)] <- c(".", ",", ";", "!")
attendus_44 <- c(
  paste(tokens_44[1:7], collapse = " "),
  paste(tokens_44[8:28], collapse = " "),
  paste(tokens_44[29:44], collapse = " ")
)
stopifnot(identical(.segmenter_iramuteq_3(tokens_44, 10L), attendus_44))

# La référence officielle Python coupe après les positions 23 et 72.
tokens_120 <- paste0("mot", seq_len(120L))
tokens_120[c(23L, 44L, 72L, 99L)] <- c(".", ",", ";", "!")
attendus_120 <- c(
  paste(tokens_120[1:23], collapse = " "),
  paste(tokens_120[24:72], collapse = " "),
  paste(tokens_120[73:120], collapse = " ")
)
stopifnot(identical(.segmenter_iramuteq_3(tokens_120, 40L), attendus_120))

# Si le marqueur de fin ($) est dans la fenêtre, conserver le reliquat.
tokens_20 <- paste0("mot", seq_len(20L))
stopifnot(identical(.segmenter_iramuteq_3(tokens_20, 8L),
                    paste(tokens_20, collapse = " ")))
tokens_34 <- paste0("mot", seq_len(34L))
stopifnot(identical(.segmenter_iramuteq_3(tokens_34, 10L),
                    c(paste(tokens_34[1:11], collapse = " "),
                      paste(tokens_34[12:34], collapse = " "))))

# Supprimer les ponctuations après la détection des frontières.
sans_ponctuation <- .segmenter_iramuteq_3(tokens_44, 10L,
                                         supprimer_ponctuation = TRUE)
stopifnot(length(sans_ponctuation) == 3L)
stopifnot(!any(grepl("[.!?;,]", sans_ponctuation)))

# Vérifier l'intégration au corpus quanteda, sans perdre les métadonnées.
corpus_test <- quanteda::corpus(
  data.frame(doc_id = "texte_1", text = paste(tokens_120, collapse = " "))
)
quanteda::docvars(corpus_test, "*source") <- "essai"
resultat_officiel <- split_segments(corpus_test, segment_size = 40L,
                                     mode_segmentation = "iramuteq_3")
stopifnot(identical(as.character(resultat_officiel), attendus_120))
stopifnot(all(quanteda::docvars(resultat_officiel, "*source") == "essai"))

# Les réglages historiques produisent les mêmes textes qu'avant.
ancien_ponctue <- split_segments(corpus_test, segment_size = 40L,
                                  force_split_on_strong_punct = TRUE)
mode_ponctue <- split_segments(corpus_test, segment_size = 40L,
                               mode_segmentation = "ponctuation_prioritaire")
stopifnot(identical(as.character(ancien_ponctue), as.character(mode_ponctue)))
ancien_fixe <- split_segments(corpus_test, segment_size = 40L,
                              force_split_on_strong_punct = FALSE)
mode_fixe <- split_segments(corpus_test, segment_size = 40L,
                            mode_segmentation = "taille_fixe")
stopifnot(identical(as.character(ancien_fixe), as.character(mode_fixe)))

# La double classification utilise le mode sélectionné pour RST1 et RST2.
rst <- split_segments_double_rst(corpus_test, rst1 = 12L, rst2 = 14L,
                                  mode_segmentation = "iramuteq_3")
attendus_rst <- c(
  as.character(split_segments(corpus_test, segment_size = 12L,
                              mode_segmentation = "iramuteq_3")),
  as.character(split_segments(corpus_test, segment_size = 14L,
                              mode_segmentation = "iramuteq_3"))
)
stopifnot(identical(as.character(rst), attendus_rst))
stopifnot(all(quanteda::docvars(rst, "*source") == "essai"))

cat("Segmentation IRaMuTeQ 3.0 et anciens modes : OK\n")
