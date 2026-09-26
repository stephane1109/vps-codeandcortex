source(file.path("iramuteqlite", "autoCHD.R"))

config <- list(
  iramuteq_discrimination_simple_profile = "ciblee",
  iramuteq_discrimination_simple_vary_min_docfreq = TRUE,
  iramuteq_discrimination_simple_min_docfreq_min = 2L,
  iramuteq_discrimination_simple_min_docfreq_max = 5L,
  iramuteq_discrimination_simple_vary_mincl = FALSE,
  iramuteq_mincl = 5L,
  min_docfreq = 3L,
  k_iramuteq = 10L,
  lexique_utiliser_lemmes = TRUE,
  retirer_stopwords = FALSE,
  supprimer_ponctuation = FALSE,
  supprimer_chiffres = FALSE
)

grid <- construire_grille_discrimination_simple_iramuteq(config)
stopifnot(length(grid$candidates) == 32L)
stopifnot(all(vapply(
  grid$candidates,
  function(candidate) identical(candidate$config$morpho_conserver_hors_lexique, TRUE),
  logical(1)
)))

lexique <- read.csv2(
  file.path("dictionnaires", "lexique_fr.csv"),
  stringsAsFactors = FALSE,
  check.names = FALSE
)
idx <- toupper(trimws(lexique$c_morpho)) %in% c("NOM", "VER")
formes_nom_ver <- unique(tolower(trimws(c(
  lexique$c_mot[idx],
  lexique$c_lemme[idx]
))))
formes_nom_ver <- formes_nom_ver[nzchar(formes_nom_ver)]

# "je" est un pronom et ne doit pas entrer dans le profil NOM+VER.
stopifnot(!("je" %in% formes_nom_ver))
# "tue" est un verbe : sa conservation est normale dans ce profil.
stopifnot("tue" %in% formes_nom_ver)

lexique_en <- utils::read.delim(
  file.path("dictionnaires", "lexique_en.txt"),
  header = FALSE,
  sep = "\t",
  quote = "",
  comment.char = "",
  col.names = c("c_mot", "c_lemme", "c_morpho"),
  stringsAsFactors = FALSE
)
idx_en <- toupper(trimws(lexique_en$c_morpho)) %in% c("NOM", "VER")
formes_nom_ver_en <- unique(tolower(trimws(c(
  lexique_en$c_mot[idx_en],
  lexique_en$c_lemme[idx_en]
))))
formes_nom_ver_en <- formes_nom_ver_en[nzchar(formes_nom_ver_en)]

# Le profil cible doit fonctionner avec les catégories minuscules du lexique anglais.
stopifnot("protect" %in% formes_nom_ver_en)
stopifnot("protection" %in% formes_nom_ver_en)
# Les pronoms et l'auxiliaire "be" ne doivent pas être réintroduits par AUTRE_FORME.
stopifnot(!("i" %in% formes_nom_ver_en))
stopifnot(!("be" %in% formes_nom_ver_en))

lexique_de_lines <- readLines(
  file.path("dictionnaires", "lexique_de.txt"),
  encoding = "UTF-8",
  warn = FALSE
)
lexique_de_connection <- textConnection(lexique_de_lines)
lexique_de <- utils::read.delim(
  lexique_de_connection,
  header = FALSE,
  sep = "\t",
  quote = "\"",
  comment.char = "",
  col.names = c("c_mot", "c_lemme", "c_morpho"),
  stringsAsFactors = FALSE
)
close(lexique_de_connection)
stopifnot(nrow(lexique_de) == 737L)
stopifnot(all(toupper(trimws(lexique_de$c_morpho)) == "SW"))
stopifnot("sein" %in% lexique_de$c_mot)

source(file.path("iramuteqlite", "afc_extremes.R"))
coords <- matrix(
  c(1, 0, -1, 0, 0, 1),
  nrow = 3,
  byrow = TRUE,
  dimnames = list(c("positif", "negatif", "autre"), c("Dim 1", "Dim 2"))
)
stats <- data.frame(
  Terme = c("positif", "negatif", "autre"),
  Classe = c("1", "1", "2"),
  p = c(0.01, 0.01, 0.02),
  chi2 = c(8, -8, 4),
  stringsAsFactors = FALSE
)
extremes <- selectionner_termes_extremes_afc(
  afc_obj = list(colcoord = coords),
  stats_df = stats,
  top_n = 3L,
  p_seuil = 0.05
)
stopifnot(!("negatif" %in% extremes$terme))
stopifnot(all(is.finite(extremes$x)) & all(is.finite(extremes$y)))

cat("Test morphosyntaxique CHD Opposition optimisée : OK\n")
