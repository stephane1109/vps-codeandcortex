ticket_env_int <- function(name, default) {
  value <- suppressWarnings(as.integer(Sys.getenv(name, unset = as.character(default))))
  if (is.na(value)) {
    return(default)
  }
  value
}


ticket_env_bool <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (!nzchar(value)) {
    return(default)
  }
  !(tolower(trimws(value)) %in% c("0", "false", "no", "off"))
}


ticket_mask_redis_url <- function(value) {
  if (is.null(value) || !nzchar(trimws(value))) {
    return("(absente)")
  }
  sub("://([^@/]+)@", "://***@", trimws(value))
}


ticket_first_diagnostic_line <- function(value, fallback = "Diagnostic d'environnement Redis CHD Rainette.") {
  text <- trimws(value %||% "")
  if (!nzchar(text)) {
    return(fallback)
  }
  lines <- trimws(strsplit(text, "\n", fixed = TRUE)[[1]])
  lines <- lines[nzchar(lines)]
  if (!length(lines)) {
    return(fallback)
  }
  lines[[1]]
}


ticket_error_summary <- function() {
  redis_url <- ticket_mask_redis_url(Sys.getenv("REDIS_URL", unset = ""))
  app_id <- Sys.getenv("APP_TICKET_ID", unset = "(absent)")
  helper <- Sys.getenv("APP_TICKET_REDIS_HELPER", unset = "/app/backend/redis_ticket_cli.py")
  helper_status <- if (file.exists(helper)) "helper présent" else sprintf("helper absent: %s", helper)
  sprintf("REDIS_URL=%s | APP_TICKET_ID=%s | %s", redis_url, app_id, helper_status)
}


ticket_runtime_diagnostic <- function(cfg, base_message = "") {
  redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
  redis_cli <- Sys.which("redis-cli")
  python3 <- Sys.which("python3")
  redis_helper <- ticket_redis_helper_path()
  details <- c(
    if (nzchar(trimws(base_message))) trimws(base_message),
    sprintf("APP_TICKET_ID=%s", cfg$app_id),
    sprintf("REDIS_URL=%s", ticket_mask_redis_url(redis_url)),
    sprintf("python3=%s", if (nzchar(python3)) python3 else "(absent)"),
    sprintf("redis-helper=%s", if (file.exists(redis_helper)) redis_helper else sprintf("(absent: %s)", redis_helper)),
    sprintf("redis-cli=%s", if (nzchar(redis_cli)) redis_cli else "(absent)"),
    sprintf("APP_TICKET_ENFORCED=%s", if (isTRUE(cfg$enabled)) "1" else "0")
  )
  paste(details, collapse = "\n")
}


ticket_safe_runtime_diagnostic <- function(cfg, base_message = "") {
  tryCatch(
    {
      diagnostic <- ticket_runtime_diagnostic(cfg, base_message)
      if (nzchar(trimws(diagnostic))) {
        return(diagnostic)
      }
      stop("Diagnostic Redis vide.", call. = FALSE)
    },
    error = function(exc) {
      redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
      configured_helper <- trimws(Sys.getenv("APP_TICKET_REDIS_HELPER", unset = ""))
      default_helper <- "/app/backend/redis_ticket_cli.py"
      fallback_helper <- if (nzchar(configured_helper)) configured_helper else default_helper
      paste(
        c(
          if (nzchar(trimws(base_message))) trimws(base_message),
          sprintf("Erreur pendant la construction du diagnostic Redis : %s", conditionMessage(exc)),
          sprintf("APP_TICKET_ID=%s", cfg$app_id %||% "(inconnu)"),
          sprintf("REDIS_URL=%s", ticket_mask_redis_url(redis_url)),
          sprintf("python3=%s", if (nzchar(Sys.which("python3"))) Sys.which("python3") else "(absent)"),
          sprintf("redis-helper=%s", if (file.exists(fallback_helper)) fallback_helper else sprintf("(absent: %s)", fallback_helper)),
          sprintf("redis-cli=%s", if (nzchar(Sys.which("redis-cli"))) Sys.which("redis-cli") else "(absent)"),
          sprintf("APP_TICKET_ENFORCED=%s", Sys.getenv("APP_TICKET_ENFORCED", unset = "(absent)"))
        ),
        collapse = "\n"
      )
    }
  )
}


ticket_environment_diagnostic <- function(base_message = "") {
  redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
  configured_helper <- trimws(Sys.getenv("APP_TICKET_REDIS_HELPER", unset = ""))
  default_helper <- "/app/backend/redis_ticket_cli.py"
  fallback_helper <- if (nzchar(configured_helper)) configured_helper else default_helper
  paste(
    c(
      sprintf("REDIS_URL=%s", ticket_mask_redis_url(redis_url)),
      sprintf("APP_TICKET_ID=%s", Sys.getenv("APP_TICKET_ID", unset = "(absent)")),
      sprintf("python3=%s", if (nzchar(Sys.which("python3"))) Sys.which("python3") else "(absent)"),
      sprintf("redis-helper=%s", if (file.exists(fallback_helper)) fallback_helper else sprintf("(absent: %s)", fallback_helper)),
      sprintf("redis-cli=%s", if (nzchar(Sys.which("redis-cli"))) Sys.which("redis-cli") else "(absent)"),
      sprintf("APP_TICKET_ENFORCED=%s", Sys.getenv("APP_TICKET_ENFORCED", unset = "(absent)")),
      sprintf("APP_TICKET_MAX_ACTIVE=%s", Sys.getenv("APP_TICKET_MAX_ACTIVE", unset = "(absent)")),
      sprintf("APP_TICKET_COST=%s", Sys.getenv("APP_TICKET_COST", unset = "(absent)")),
      sprintf("CAPACITE_SERVEUR=%s", Sys.getenv("CAPACITE_SERVEUR", unset = "(absent)")),
      sprintf("APP_TICKET_TTL_SECONDS=%s", Sys.getenv("APP_TICKET_TTL_SECONDS", unset = "(absent)")),
      sprintf("APP_TICKET_RELEASE_URL=%s", Sys.getenv("APP_TICKET_RELEASE_URL", unset = "(absent)")),
      "Diagnostic direct depuis l'interface CHD Rainette.",
      if (nzchar(trimws(base_message))) trimws(base_message)
    ),
    collapse = "\n"
  )
}


ticket_random_id <- function(length = 32L) {
  alphabet <- c(letters[1:6], as.character(0:9))
  paste(sample(alphabet, size = length, replace = TRUE), collapse = "")
}


ticket_config <- function(default_app_id, app_label) {
  ttl_seconds <- max(60L, ticket_env_int("APP_TICKET_TTL_SECONDS", 300L))
  wait_stale_default <- min(ttl_seconds, 120L)
  list(
    enabled = ticket_env_bool("APP_TICKET_ENFORCED", TRUE),
    # #### APP_TICKET_FAIL_OPEN
    # 0 = mode normal VPS : Redis est obligatoire et la home voit l'occupation.
    # 1 = secours exceptionnel : l'app reste utilisable si Redis tombe, mais la
    # home ne peut pas synchroniser l'état de cette session.
    fail_open = ticket_env_bool("APP_TICKET_FAIL_OPEN", FALSE),
    app_id = trimws(Sys.getenv("APP_TICKET_ID", unset = default_app_id)) %||% default_app_id,
    app_label = app_label,
    max_active = max(1L, ticket_env_int("APP_TICKET_MAX_ACTIVE", 1L)),
    cost = max(0L, ticket_env_int("APP_TICKET_COST", 4L)),
    global_capacity = max(1L, ticket_env_int("CAPACITE_SERVEUR", 6L)),
    ttl_seconds = ttl_seconds,
    max_waiting = max(0L, ticket_env_int("APP_TICKET_MAX_WAITING", 20L)),
    wait_refresh_ms = max(2000L, ticket_env_int("APP_TICKET_WAIT_REFRESH_MS", 10000L)),
    heartbeat_ms = max(30000L, ticket_env_int("APP_TICKET_HEARTBEAT_MS", 30000L)),
    release_url = trimws(Sys.getenv("APP_TICKET_RELEASE_URL", unset = "")),
    hidden_release_seconds = max(0L, ticket_env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 0L)),
    wait_stale_seconds = max(30L, ticket_env_int("APP_TICKET_WAIT_STALE_SECONDS", wait_stale_default))
  )
}


ticket_redis_helper_path <- function() {
  configured <- trimws(Sys.getenv("APP_TICKET_REDIS_HELPER", unset = ""))
  if (nzchar(configured)) {
    return(configured)
  }
  default_path <- "/app/backend/redis_ticket_cli.py"
  if (file.exists(default_path)) {
    return(default_path)
  }
  "backend/redis_ticket_cli.py"
}


ticket_python3 <- function() {
  python3 <- Sys.which("python3")
  if (!nzchar(python3)) {
    stop("python3 absent : installe python3 dans l'image Docker CHD Rainette.", call. = FALSE)
  }
  python3
}


ticket_redis_cli <- function() {
  redis_cli <- Sys.which("redis-cli")
  if (!nzchar(redis_cli)) {
    stop("redis-cli absent : installe le package redis-tools dans l'image Docker.", call. = FALSE)
  }
  redis_cli
}


ticket_redis_url <- function() {
  redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
  if (!nzchar(redis_url)) {
    stop("REDIS_URL absent : configure une URL Redis complète avec mot de passe dans Coolify.", call. = FALSE)
  }
  redis_url
}


ticket_redis_exec_python <- function(args) {
  helper_path <- ticket_redis_helper_path()
  if (!file.exists(helper_path)) {
    stop(sprintf("Helper Redis Python absent : %s", helper_path), call. = FALSE)
  }
  output <- tryCatch(
    system2(
      ticket_python3(),
      c(helper_path, args),
      stdout = TRUE,
      stderr = TRUE
    ),
    error = function(exc) structure(c(conditionMessage(exc)), status = 1L)
  )
  status <- attr(output, "status")
  if (is.null(status)) {
    status <- 0L
  }
  if (!identical(as.integer(status), 0L)) {
    stop(sprintf("Connexion Redis impossible via le helper Python : %s", paste(output, collapse = "\n")), call. = FALSE)
  }
  output
}


ticket_redis_exec_cli <- function(args) {
  output <- tryCatch(
    system2(
      ticket_redis_cli(),
      c("-u", ticket_redis_url(), "--raw", args),
      stdout = TRUE,
      stderr = TRUE
    ),
    error = function(exc) structure(c(conditionMessage(exc)), status = 1L)
  )
  status <- attr(output, "status")
  if (is.null(status)) {
    status <- 0L
  }
  if (!identical(as.integer(status), 0L)) {
    stop(sprintf("Connexion Redis impossible via REDIS_URL : %s", paste(output, collapse = "\n")), call. = FALSE)
  }
  output
}


ticket_redis_exec <- function(args) {
  python_error <- NULL
  python_output <- tryCatch(
    ticket_redis_exec_python(args),
    error = function(exc) {
      python_error <<- conditionMessage(exc)
      NULL
    }
  )
  if (!is.null(python_output)) {
    return(python_output)
  }

  cli_output <- tryCatch(
    ticket_redis_exec_cli(args),
    error = function(exc) {
      stop(
        sprintf(
          "Redis indisponible. Erreur helper Python : %s\nErreur redis-cli : %s",
          python_error %||% "(non disponible)",
          conditionMessage(exc)
        ),
        call. = FALSE
      )
    }
  )
  cli_output
}


ticket_gate_cli_path <- function() {
  configured <- trimws(Sys.getenv("APP_TICKET_GATE_CLI", unset = ""))
  if (nzchar(configured)) {
    return(configured)
  }
  default_path <- "/app/backend/ticket_gate_cli.py"
  if (file.exists(default_path)) {
    return(default_path)
  }
  "backend/ticket_gate_cli.py"
}


ticket_cli_exec_json <- function(args) {
  cli_path <- ticket_gate_cli_path()
  if (!file.exists(cli_path)) {
    stop(sprintf("Helper ticket Python absent : %s", cli_path), call. = FALSE)
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Package R jsonlite absent : installe r-cran-jsonlite dans l'image Docker.", call. = FALSE)
  }
  output <- tryCatch(
    system2(
      ticket_python3(),
      c(cli_path, args),
      stdout = TRUE,
      stderr = TRUE
    ),
    error = function(exc) structure(c(conditionMessage(exc)), status = 1L)
  )
  status <- attr(output, "status")
  if (is.null(status)) {
    status <- 0L
  }
  json_line <- tail(grep("^\\{.*\\}$", output, value = TRUE), 1L)
  if (!identical(as.integer(status), 0L) || !length(json_line)) {
    stop(sprintf("Ticket Python indisponible : %s", paste(output, collapse = "\n")), call. = FALSE)
  }
  jsonlite::fromJSON(json_line, simplifyVector = FALSE)
}


ticket_snapshot_from_python <- function(cfg, raw) {
  list(
    enabled = isTRUE(raw$enabled %||% TRUE),
    app_id = cfg$app_id,
    local_fallback = isTRUE(raw$local_fallback %||% FALSE),
    ticket_id = raw$ticket_id %||% NULL,
    statut = trimws(raw$statut %||% "inconnu"),
    position = raw$position %||% NULL,
    active = ticket_safe_int(raw$active %||% 0L, 0L),
    queued = ticket_safe_int(raw$queued %||% 0L, 0L),
    max_active = ticket_safe_int(raw$max_active %||% cfg$max_active, cfg$max_active),
    wait_refresh_ms = ticket_safe_int(raw$wait_refresh_ms %||% cfg$wait_refresh_ms, cfg$wait_refresh_ms),
    heartbeat_ms = ticket_safe_int(raw$heartbeat_ms %||% cfg$heartbeat_ms, cfg$heartbeat_ms),
    message = trimws(raw$message %||% "")
  )
}


ticket_python_claim_or_refresh <- function(cfg, session_id) {
  raw <- ticket_cli_exec_json(c(
    "claim",
    "--session-id",
    session_id,
    "--app-label",
    cfg$app_label
  ))
  ticket_snapshot_from_python(cfg, raw)
}


ticket_python_release <- function(cfg, session_id) {
  raw <- ticket_cli_exec_json(c(
    "release",
    "--session-id",
    session_id,
    "--app-label",
    cfg$app_label
  ))
  ticket_snapshot_from_python(cfg, raw)
}


ticket_safe_int <- function(value, default = 0L) {
  parsed <- suppressWarnings(as.integer(value))
  if (is.na(parsed)) {
    default
  } else {
    parsed
  }
}


ticket_keys <- function(app_id) {
  list(
    active = sprintf("app:%s:tickets:actifs", app_id),
    waiting = sprintf("app:%s:tickets:attente", app_id)
  )
}


ticket_ticket_key <- function(ticket_id) {
  sprintf("ticket:%s", ticket_id)
}


ticket_session_key <- function(app_id, session_id) {
  sprintf("session:%s:%s:ticket", app_id, session_id)
}


ticket_global_active_key <- function() {
  "tickets:global:actifs"
}


ticket_exists <- function(key) {
  ticket_safe_int(ticket_redis_exec(c("EXISTS", key))[1], 0L) > 0L
}


ticket_get <- function(key) {
  value <- ticket_redis_exec(c("GET", key))
  if (!length(value)) {
    return("")
  }
  trimws(value[1])
}


ticket_setex <- function(key, ttl_seconds, value) {
  invisible(ticket_redis_exec(c("SETEX", key, as.character(ttl_seconds), as.character(value))))
}


ticket_expire <- function(key, ttl_seconds) {
  invisible(ticket_redis_exec(c("EXPIRE", key, as.character(ttl_seconds))))
}


ticket_del <- function(...) {
  keys <- Filter(nzchar, unlist(list(...), use.names = FALSE))
  if (!length(keys)) {
    return(invisible(NULL))
  }
  invisible(ticket_redis_exec(c("DEL", keys)))
}


ticket_zrem <- function(key, member) {
  invisible(ticket_redis_exec(c("ZREM", key, member)))
}


ticket_zadd <- function(key, score, member) {
  invisible(ticket_redis_exec(c("ZADD", key, format(score, scientific = FALSE, trim = TRUE), member)))
}


ticket_list_members <- function(key) {
  values <- ticket_redis_exec(c("ZRANGE", key, "0", "-1"))
  values[nzchar(values)]
}


ticket_zcard <- function(key) {
  ticket_safe_int(ticket_redis_exec(c("ZCARD", key))[1], 0L)
}


ticket_hgetall <- function(key) {
  raw <- ticket_redis_exec(c("HGETALL", key))
  if (!length(raw)) {
    return(list())
  }
  raw <- raw[nzchar(raw)]
  if (!length(raw)) {
    return(list())
  }
  result <- list()
  for (index in seq(1L, length(raw), by = 2L)) {
    field <- raw[index]
    value <- if (index + 1L <= length(raw)) raw[index + 1L] else ""
    result[[field]] <- value
  }
  result
}


ticket_hset_map <- function(key, mapping) {
  flat <- as.vector(rbind(names(mapping), unname(as.character(mapping))))
  invisible(ticket_redis_exec(c("HSET", key, flat)))
}


ticket_timeout_seconds <- function(cfg, status) {
  if (identical(status, "attente")) {
    return(cfg$wait_stale_seconds)
  }
  cfg$ttl_seconds
}


ticket_drop <- function(cfg, ticket_id) {
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  session_id <- trimws(data$session_id %||% "")
  keys <- ticket_keys(cfg$app_id)
  ticket_zrem(keys$active, ticket_id)
  ticket_zrem(keys$waiting, ticket_id)
  ticket_zrem(ticket_global_active_key(), ticket_id)
  ticket_del(ticket_ticket_key(ticket_id))
  if (nzchar(session_id)) {
    ticket_del(ticket_session_key(cfg$app_id, session_id))
  }
}


ticket_cleanup_expired <- function(cfg) {
  keys <- ticket_keys(cfg$app_id)
  now <- as.integer(Sys.time())
  seen <- character()
  for (key in c(keys$active, keys$waiting, ticket_global_active_key())) {
    members <- ticket_list_members(key)
    for (ticket_id in members) {
      if (ticket_id %in% seen) {
        next
      }
      seen <- c(seen, ticket_id)
      hash_key <- ticket_ticket_key(ticket_id)
      if (!ticket_exists(hash_key)) {
        ticket_zrem(keys$active, ticket_id)
        ticket_zrem(keys$waiting, ticket_id)
        ticket_zrem(ticket_global_active_key(), ticket_id)
        next
      }
      data <- ticket_hgetall(hash_key)
      status <- trimws(data$status %||% "")
      if (!nzchar(status)) {
        status <- "attente"
      }
      heartbeat_at <- ticket_safe_int(data$updated_at %||% data$created_at %||% now, now)
      if ((now - heartbeat_at) > ticket_timeout_seconds(cfg, status)) {
        ticket_drop(cfg, ticket_id)
      }
    }
  }
}


ticket_active_count <- function(cfg) {
  ticket_zcard(ticket_keys(cfg$app_id)$active)
}


ticket_waiting_count <- function(cfg) {
  ticket_zcard(ticket_keys(cfg$app_id)$waiting)
}


ticket_active_load <- function() {
  total <- 0L
  for (ticket_id in ticket_list_members(ticket_global_active_key())) {
    data <- ticket_hgetall(ticket_ticket_key(ticket_id))
    if (length(data)) {
      total <- total + ticket_safe_int(data$cost %||% 0L, 0L)
    }
  }
  total
}


ticket_waiting_position <- function(cfg, ticket_id) {
  waiting <- ticket_list_members(ticket_keys(cfg$app_id)$waiting)
  if (!(ticket_id %in% waiting)) {
    return(NULL)
  }
  match(ticket_id, waiting)
}


ticket_can_activate <- function(cfg) {
  ticket_active_count(cfg) < cfg$max_active && (ticket_active_load() + cfg$cost <= cfg$global_capacity)
}


ticket_promote_waiting <- function(cfg) {
  keys <- ticket_keys(cfg$app_id)
  for (ticket_id in ticket_list_members(keys$waiting)) {
    if (!ticket_can_activate(cfg)) {
      break
    }
    hash_key <- ticket_ticket_key(ticket_id)
    if (!ticket_exists(hash_key)) {
      ticket_zrem(keys$waiting, ticket_id)
      next
    }
    now <- as.integer(Sys.time())
    ticket_hset_map(hash_key, c(status = "actif", updated_at = now))
    ticket_expire(hash_key, cfg$ttl_seconds)
    ticket_zrem(keys$waiting, ticket_id)
    ticket_zadd(keys$active, as.numeric(now), ticket_id)
    ticket_zadd(ticket_global_active_key(), as.numeric(now), ticket_id)
  }
}


ticket_touch_existing <- function(cfg, ticket_id, session_key) {
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  status <- trimws(data$status %||% "")
  if (!nzchar(status)) {
    status <- "attente"
  }
  now <- as.integer(Sys.time())
  timeout <- ticket_timeout_seconds(cfg, status)
  ticket_hset_map(ticket_ticket_key(ticket_id), c(updated_at = now))
  ticket_expire(ticket_ticket_key(ticket_id), timeout)
  ticket_expire(session_key, timeout)
  invisible(data)
}


ticket_snapshot <- function(cfg, ticket_id = NULL, message = "") {
  active <- ticket_active_count(cfg)
  queued <- ticket_waiting_count(cfg)
  if (is.null(ticket_id) || !nzchar(ticket_id)) {
    return(list(
      enabled = TRUE,
      app_id = cfg$app_id,
      ticket_id = NULL,
      statut = "inconnu",
      position = NULL,
      active = active,
      queued = queued,
      max_active = cfg$max_active,
      wait_refresh_ms = cfg$wait_refresh_ms,
      heartbeat_ms = cfg$heartbeat_ms,
      message = message
    ))
  }
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  list(
    enabled = TRUE,
    app_id = cfg$app_id,
    ticket_id = ticket_id,
    statut = trimws(data$status %||% "inconnu"),
    position = ticket_waiting_position(cfg, ticket_id),
    active = active,
    queued = queued,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = trimws(data$message %||% message)
  )
}


ticket_disabled_snapshot <- function(cfg, message) {
  list(
    enabled = FALSE,
    app_id = cfg$app_id,
    ticket_id = NULL,
    statut = "disabled",
    position = NULL,
    active = 0L,
    queued = 0L,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = message
  )
}


ticket_error_snapshot <- function(cfg, message) {
  safe_message <- trimws(message %||% "")
  if (!nzchar(safe_message) || grepl("Diagnostic Redis non transmis", safe_message, fixed = TRUE)) {
    safe_message <- ticket_environment_diagnostic(
      "Erreur ticket sans diagnostic Redis exploitable."
    )
  }
  list(
    enabled = TRUE,
    app_id = cfg$app_id,
    ticket_id = NULL,
    statut = "erreur",
    position = NULL,
    active = 0L,
    queued = 0L,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = safe_message
  )
}


ticket_local_fallback_snapshot <- function(cfg, message) {
  list(
    enabled = TRUE,
    app_id = cfg$app_id,
    local_fallback = TRUE,
    ticket_id = NULL,
    statut = "actif",
    position = NULL,
    active = 1L,
    queued = 0L,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = trimws(message %||% "Redis indisponible : accès local de secours activé.")
  )
}


ticket_released_snapshot <- function(cfg, message) {
  active <- 0L
  queued <- 0L
  safe_counts <- tryCatch(
    list(active = ticket_active_count(cfg), queued = ticket_waiting_count(cfg)),
    error = function(...) list(active = 0L, queued = 0L)
  )
  active <- safe_counts$active
  queued <- safe_counts$queued
  list(
    enabled = TRUE,
    app_id = cfg$app_id,
    ticket_id = NULL,
    statut = "released",
    position = NULL,
    active = active,
    queued = queued,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = message
  )
}


ticket_claim_or_refresh <- function(cfg, session_id) {
  # Alignement avec IRaMuTeQ Lite : le calcul de file d'attente est fait par
  # un helper Python haut niveau qui parle directement à Redis.
  ticket_python_claim_or_refresh(cfg, session_id)
}


ticket_release <- function(cfg, session_id) {
  if (is.null(session_id) || !nzchar(session_id)) {
    return(FALSE)
  }
  tryCatch(
    {
      ticket_python_release(cfg, session_id)
      TRUE
    },
    error = function(...) FALSE
  )
}


ticket_session_id <- function(session) {
  if (is.null(session$userData$ticket_session_id) || !nzchar(session$userData$ticket_session_id)) {
    session$userData$ticket_session_id <- sprintf("%s-%s", session$token, ticket_random_id(12L))
  }
  session$userData$ticket_session_id
}


ticket_resume_session <- function(session) {
  session$userData$ticket_released <- FALSE
  session$userData$ticket_session_id <- sprintf("%s-%s", session$token, ticket_random_id(12L))
  session$userData$ticket_release_sent <- FALSE
  invisible(session$userData$ticket_session_id)
}


ticket_set_released <- function(session, value = TRUE) {
  session$userData$ticket_released <- isTRUE(value)
}


ticket_is_released <- function(session) {
  isTRUE(session$userData$ticket_released)
}


ticket_release_hook_ui <- function(cfg, session) {
  if (!cfg$enabled || !nzchar(cfg$release_url) || ticket_is_released(session)) {
    return(NULL)
  }
  session_id <- ticket_session_id(session)
  hidden_ms <- max(0L, cfg$hidden_release_seconds) * 1000L
  tags$script(HTML(sprintf(
    "(function(){const releaseUrl=%s;const applicationId=%s;const sessionId=%s;const hiddenMs=%s;
      if(!releaseUrl||!applicationId||!sessionId){return;}
      let sent=false;let hiddenTimer=null;
      function buildUrl(){const sep=releaseUrl.indexOf('?')>=0?'&':'?';return releaseUrl+sep+'application_id='+encodeURIComponent(applicationId)+'&session_id='+encodeURIComponent(sessionId);}
      function sendRelease(){if(sent){return;}sent=true;const url=buildUrl();
        try{if(navigator.sendBeacon){const ok=navigator.sendBeacon(url,new Blob([''],{type:'text/plain;charset=UTF-8'}));if(ok){return;}}}catch(error){}
        try{fetch(url,{method:'POST',mode:'no-cors',keepalive:true,body:''}).catch(()=>{});}catch(error){}
      }
      function clearHiddenTimer(){if(hiddenTimer!==null){window.clearTimeout(hiddenTimer);hiddenTimer=null;}}
      function scheduleHiddenRelease(){clearHiddenTimer();if(!hiddenMs||hiddenMs<=0){return;}hiddenTimer=window.setTimeout(function(){sendRelease();},hiddenMs);}
      document.addEventListener('visibilitychange',function(){if(document.visibilityState==='hidden'){scheduleHiddenRelease();}else{clearHiddenTimer();sent=false;}});
      window.addEventListener('pagehide',sendRelease);
      window.addEventListener('beforeunload',sendRelease);
    })();",
    shQuote(cfg$release_url, type = "sh"),
    shQuote(cfg$app_id, type = "sh"),
    shQuote(session_id, type = "sh"),
    as.character(hidden_ms)
  )))
}


ticket_parent_notify_script <- function(cfg, status) {
  app_id <- trimws(cfg$app_id %||% "")
  tags$script(HTML(sprintf(
    "(function(){try{if(window.opener&&!window.opener.closed){window.opener.postMessage({type:'codeandcortex-ticket:changed',applicationId:%s,status:%s},'*');}}catch(error){}})();",
    shQuote(app_id, type = "sh"),
    shQuote(status %||% "", type = "sh")
  )))
}


ticket_sidebar_ui <- function(snapshot) {
  status <- snapshot$statut %||% "erreur"
  local_fallback <- isTRUE(snapshot$local_fallback)
  diagnostic_message <- trimws(snapshot$message %||% "")
  if (status %in% c("refuse", "erreur")) {
    diagnostic_base <- if (
      nzchar(diagnostic_message) &&
        !grepl("Diagnostic Redis non transmis", diagnostic_message, fixed = TRUE)
    ) {
      diagnostic_message
    } else {
      "Diagnostic d'environnement Redis CHD Rainette."
    }
    diagnostic_message <- ticket_environment_diagnostic(
      diagnostic_base
    )
  }
  diagnostic_summary <- if (status %in% c("refuse", "erreur")) {
    ticket_error_summary()
  } else {
    ticket_first_diagnostic_line(diagnostic_message)
  }
  card_class <- switch(
    status,
    disabled = "ticket-status-card is-disabled",
    actif = "ticket-status-card is-active",
    attente = "ticket-status-card is-waiting",
    refuse = "ticket-status-card is-error",
    released = "ticket-status-card is-released",
    "ticket-status-card is-error"
  )
  dot_class <- switch(
    status,
    disabled = "ticket-status-dot is-disabled",
    actif = "ticket-status-dot is-active",
    attente = "ticket-status-dot is-waiting",
    released = "ticket-status-dot is-released",
    "ticket-status-dot is-error"
  )
  title <- switch(
    status,
    disabled = "Accès libre",
    actif = "Application active",
    attente = "Application occupée",
    refuse = "File d'attente pleine",
    released = "Accès libéré",
    "Accès indisponible"
  )
  detail <- switch(
    status,
    disabled = "Le contrôle d'accès n'est pas appliqué pour cette application.",
    actif = if (local_fallback) {
      "Redis est indisponible : accès local de secours activé, l'application reste utilisable."
    } else {
      sprintf("%s utilisateur(s) actif(s) sur %s autorisé(s).", snapshot$active, snapshot$max_active)
    },
    attente = sprintf("Position actuelle dans la file : %s.", snapshot$position %||% "?"),
    refuse = "Impossible d'ajouter un nouvel utilisateur pour le moment.",
    released = "Cette page n'occupe plus l'application.",
    sprintf("Le ticket courant n'a pas pu être validé : %s", diagnostic_summary)
  )
  note <- switch(
    status,
    disabled = "Contrôle d'accès désactivé pour cette application.",
    actif = if (local_fallback) {
      "Contrôle Redis indisponible : le ticket n'est pas bloquant sur cette session."
    } else {
      sprintf("Accès actif (%s / %s).", snapshot$active, snapshot$max_active)
    },
    attente = sprintf("Application occupée. Position dans la file : %s.", snapshot$position %||% "?"),
    refuse = "File d'attente pleine pour cette application.",
    released = "Accès libéré pour cette page.",
    "Contrôle d'accès temporairement indisponible. Le diagnostic Redis complet est affiché ci-dessous."
  )
  actions <- switch(
    status,
    actif = if (local_fallback) NULL else tags$div(
      class = "ticket-actions",
      actionButton("ticket_release_btn", "Libérer l'accès", class = "btn-primary")
    ),
    attente = tags$div(
      class = "ticket-actions",
      actionButton("ticket_leave_waiting_btn", "Quitter la file d'attente", class = "btn-secondary")
    ),
    released = tags$div(
      class = "ticket-actions",
      actionButton("ticket_resume_btn", "Reprendre l'accès", class = "btn-primary")
    ),
    NULL
  )

  tags$div(
    class = "sidebar-group ticket-access-group",
    tags$h3(class = "ticket-access-title", "Accès utilisateur"),
    tags$div(
      class = "ticket-status-shell",
      tags$div(
        class = card_class,
        tags$span(class = dot_class),
        tags$div(
          class = "ticket-status-meta",
          tags$strong(title),
          tags$br(),
          detail
        )
      ),
      tags$p(class = "ticket-status-note", note),
      if (nzchar(diagnostic_message) && status %in% c("refuse", "erreur")) {
        tags$div(
          class = "ticket-status-message",
          tags$strong("Diagnostic Redis"),
          tags$pre(diagnostic_message)
        )
      },
      actions
    ),
    if (status %in% c("actif", "attente", "released")) {
      ticket_parent_notify_script(snapshot, status)
    }
  )
}
