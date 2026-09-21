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

cat("Test morphosyntaxique CHD Opposition optimisée : OK\n")
