obtenir_bridge_reticulate <- local({
  cache <- new.env(parent = emptyenv())
  cache$bridge <- NULL

  function() {
    if (!is.null(cache$bridge)) {
      return(cache$bridge)
    }

    python_candidates <- unique(Filter(
      nzchar,
      c(
        Sys.getenv("RETICULATE_PYTHON", unset = ""),
        Sys.getenv("CHDRAINETTE_PYTHON", unset = ""),
        Sys.which("python3"),
        Sys.which("python")
      )
    ))

    if (!length(python_candidates)) {
      stop("Aucun interpréteur Python n'est disponible pour reticulate.")
    }

    reticulate::use_python(python_candidates[[1]], required = FALSE)

    bridge <- new.env(parent = emptyenv())
    reticulate::source_python(normalizePath("spacy_preprocess.py", mustWork = TRUE), envir = bridge)
    reticulate::source_python(normalizePath("ner.py", mustWork = TRUE), envir = bridge)

    cache$bridge <- bridge
    bridge
  }
})
