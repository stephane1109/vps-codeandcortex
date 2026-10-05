# Fonctions generiques d'ecriture des artefacts du pipeline.
# Les fonctions sont extraites sans modification de leur comportement.

relative_to_output <- function(path) {
  if (is.null(path) || !nzchar(path) || !file.exists(path)) return(NULL)
  rel <- sub(paste0("^", normalizePath(output_dir, winslash = "/", mustWork = FALSE), "/?"), "", normalizePath(path, winslash = "/", mustWork = FALSE))
  rel
}
write_status <- function(state = "running", progress = 0, message = "", extra = list()) {
  payload <- c(
    list(
      state = state,
      progress = progress,
      message = message,
      updated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
      logs = job_logs
    ),
    extra
  )
  write_json_atomic(payload, status_file)
}

ecrire_csv_6_decimales <- function(df, path, row.names = FALSE) {
  utils::write.csv(formater_df_csv_6_decimales(df), path, row.names = row.names)
}
