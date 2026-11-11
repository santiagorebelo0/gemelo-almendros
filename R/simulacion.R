# Motor de simulacion del gemelo digital del parqueadero Almendros (version R).
#
# Implementa el esquema de la Entrega 2:
#   X1  llegadas por intervalo de 15 min   ~ Poisson(lambda_k), una lambda por franja
#   X2  tiempo entre llegadas (min)        ~ Exponencial(lambda_k / 15)
#   X3  tiempo en la talanquera (s)        ~ Gamma(alfa, beta)
#   X4  vehiculos delante al llegar        ~ Geometrica(p = 1 - rho), rho = lambda * E[X3]
# y las extensiones de la Entrega 3: perfil por dia (Tabla 1 de Varela et al., 2023),
# permanencia Gamma, busqueda del cupo libre mas cercano y reparto de los desviados.
#
# El archivo simulacion.py contiene exactamente el mismo modelo en Python.
# Unidad de tiempo interna: minutos desde la hora de inicio.

PARAMETROS <- jsonlite::fromJSON("compartido/parametros.json", simplifyVector = TRUE)
LAYOUT_JSON <- paste(readLines("compartido/layout.json", warn = FALSE, encoding = "UTF-8"), collapse = "")
DIST_CUPOS <- jsonlite::fromJSON(LAYOUT_JSON)$cupos$dist   # con capacidad C existen los C primeros
DESTINOS <- names(PARAMETROS$desvio)
PASO_REJILLA <- 15

factores_por_dia <- function() {
  t <- PARAMETROS$tabla1_varela
  filas <- list(t[["5y7"]], t[["8y10"]], t[["11y1"]])
  fac <- list(Promedio = c(1, 1, 1))
  for (j in seq_along(t$dias)) {
    fac[[t$dias[j]]] <- sapply(filas, function(f) f[j] / mean(f))
  }
  fac
}

lambdas_del_dia <- function(dia) {
  round(PARAMETROS$franjas$lambda15 * factores_por_dia()[[dia]], 1)
}

escenario <- function(nombre = "Base", dia = "Promedio",
                      lambdas = PARAMETROS$franjas$lambda15,
                      capacidad = PARAMETROS$capacidad,
                      tal_media_s = PARAMETROS$talanquera$media_s,
                      tal_cv = PARAMETROS$talanquera$cv,
                      salidas = PARAMETROS$permanencia$activa,
                      perm_media_h = PARAMETROS$permanencia$media_h,
                      perm_cv = PARAMETROS$permanencia$cv,
                      vel_kmh = PARAMETROS$busqueda$velocidad_kmh,
                      maniobra_s = PARAMETROS$busqueda$maniobra_s,
                      replicas = PARAMETROS$replicas,
                      semilla = PARAMETROS$semilla) {
  list(nombre = nombre, dia = dia, lambdas = as.numeric(lambdas), capacidad = as.integer(capacidad),
       tal_media_s = tal_media_s, tal_cv = tal_cv, salidas = isTRUE(salidas),
       perm_media_h = perm_media_h, perm_cv = perm_cv, vel_kmh = vel_kmh,
       maniobra_s = maniobra_s, replicas = as.integer(replicas), semilla = as.integer(semilla))
}

alfa_x3 <- function(esc) 1 / esc$tal_cv^2                 # forma de X3
beta_x3 <- function(esc) alfa_x3(esc) / esc$tal_media_s   # tasa de X3 (1/s)
rho_franjas <- function(esc) esc$lambdas / 15 / 60 * esc$tal_media_s

horizonte_min <- function() (PARAMETROS$horario$fin_h - PARAMETROS$horario$inicio_h) * 60
rejilla_horas <- function() PARAMETROS$horario$inicio_h + seq(0, horizonte_min(), by = PASO_REJILLA) / 60

# Tiempos de llegada con tiempos entre llegadas exponenciales (X2), franja por franja.
# Al cambiar de franja el reloj se reinicia en el limite: por la falta de memoria de la
# exponencial esto equivale a un proceso de Poisson con tasa lambda_k en cada franja.
generar_llegadas <- function(esc) {
  h0 <- PARAMETROS$horario$inicio_h
  fr <- PARAMETROS$franjas
  tiempos <- numeric(0); entre <- numeric(0); franja <- integer(0)
  for (k in seq_len(nrow(fr))) {
    tasa <- esc$lambdas[k] / 15
    if (tasa <= 0) next
    ini <- (fr$inicio_h[k] - h0) * 60
    dur <- (fr$fin_h[k] - fr$inicio_h[k]) * 60
    n_max <- ceiling(tasa * dur + 8 * sqrt(tasa * dur) + 30)
    gaps <- rexp(n_max, rate = tasa)
    t <- cumsum(gaps)
    dentro <- t < dur
    tiempos <- c(tiempos, ini + t[dentro])
    entre <- c(entre, gaps[dentro])
    franja <- c(franja, rep(k, sum(dentro)))
  }
  list(t = tiempos, entre = entre, franja = franja)
}

simular_dia <- function(esc, detalle = FALSE) {
  H <- horizonte_min()
  rej <- seq(0, H, by = PASO_REJILLA)
  n_int <- length(rej) - 1
  C <- esc$capacidad
  orden <- order(DIST_CUPOS[seq_len(C)])   # rango de cercania -> id del cupo
  dist <- DIST_CUPOS[orden]

  ll <- generar_llegadas(esc)
  lleg <- ll$t
  n <- length(lleg)

  # X3: tiempo en la talanquera (s) -> minutos
  serv_s <- rgamma(n, shape = alfa_x3(esc), rate = beta_x3(esc))
  serv <- serv_s / 60
  # Una talanquera, orden de llegada: fin_i = max(lleg_i, fin_{i-1}) + serv_i
  acum <- cumsum(serv)
  fin <- acum + cummax(lleg - (acum - serv))
  ini <- fin - serv
  espera_s <- (ini - lleg) * 60
  # X4: vehiculos en el sistema de la talanquera delante del que llega
  x4 <- (seq_len(n) - 1) - findInterval(lleg, fin)

  # Permanencia (h) ~ Gamma
  if (esc$salidas) {
    forma_p <- 1 / esc$perm_cv^2
    perm <- rgamma(n, shape = forma_p, scale = esc$perm_media_h / forma_p) * 60
  } else {
    perm <- rep(Inf, n)
  }
  destinos <- sample(seq_along(DESTINOS), n, replace = TRUE, prob = unlist(PARAMETROS$desvio))

  vel <- esc$vel_kmh * 1000 / 60   # m por minuto
  ocupado <- rep(FALSE, C)
  libera <- rep(Inf, C)            # instante en que cada cupo queda libre
  cupo <- integer(n)               # 0 = desviado
  t_parq <- rep(NA_real_, n)
  t_sal <- rep(NA_real_, n)
  t_lleno <- NA_real_
  for (i in seq_len(n)) {
    t <- fin[i]
    salen <- libera <= t
    if (any(salen)) { ocupado[salen] <- FALSE; libera[salen] <- Inf }
    if (!all(ocupado)) {
      cc <- which.min(ocupado)     # primer cupo libre = el mas cercano a la talanquera
      cupo[i] <- orden[cc]
      ocupado[cc] <- TRUE
      t_parq[i] <- t + dist[cc] / vel + esc$maniobra_s / 60
      s <- t_parq[i] + perm[i]
      if (s < H) { t_sal[i] <- s; libera[cc] <- s }
      if (is.na(t_lleno) && all(ocupado)) t_lleno <- t
    }
    # si no hay cupo, el vehiculo queda desviado (cupo = 0)
  }

  parq <- cupo > 0
  t_ent <- sort(fin[parq])
  t_out <- sort(t_sal[!is.na(t_sal)])
  ocup_rej <- findInterval(rej, t_ent) - findInterval(rej, t_out)
  fila_rej <- findInterval(rej, lleg) - findInterval(rej, fin)
  interv <- pmin(floor(lleg / PASO_REJILLA), n_int - 1) + 1
  x1 <- tabulate(interv, nbins = n_int)
  suma <- numeric(n_int)
  if (n > 0) { rs <- rowsum(espera_s, interv); suma[as.integer(rownames(rs))] <- rs[, 1] }
  espera_int <- suma / pmax(x1, 1)
  busq_s <- (t_parq[parq] - fin[parq]) * 60

  dia <- list(
    n_llegadas = n, n_parqueados = sum(parq), n_desviados = sum(!parq),
    n_salidas = sum(!is.na(t_sal)), t_lleno = t_lleno,
    ocup_rej = ocup_rej, fila_rej = fila_rej, x1 = x1, espera_int = espera_int,
    espera_media_s = if (n) mean(espera_s) else 0,
    espera_max_s = if (n) max(espera_s) else 0,
    busq_media_s = if (any(parq)) mean(busq_s) else 0,
    ocup_max = max(ocup_rej),
    entre = ll$entre, franja = ll$franja, serv_s = serv_s, x4 = x4,
    desv_destino = tabulate(destinos[!parq], nbins = length(DESTINOS))
  )
  if (detalle) {
    dia$autos <- list(
      lleg = round(lleg * 60, 1), ini = round(ini * 60, 1), fin = round(fin * 60, 1),
      cupo = cupo - 1L,                      # ids desde 0 para la escena; -1 = desviado
      parq = round(t_parq * 60, 1), sal = round(t_sal * 60, 1),
      dest = destinos - 1L
    )
  }
  dia
}

# Repite el dia completo `replicas` veces y resume los indicadores.
simular <- function(esc) {
  set.seed(esc$semilla)
  dias <- lapply(seq_len(esc$replicas), function(r) simular_dia(esc, detalle = (r == 1)))
  h0 <- PARAMETROS$horario$inicio_h
  apilar <- function(campo) do.call(rbind, lapply(dias, `[[`, campo))
  vec <- function(campo) sapply(dias, `[[`, campo)

  ocup <- apilar("ocup_rej"); fila <- apilar("fila_rej")
  hora_lleno <- h0 + vec("t_lleno") / 60
  tope <- min(60, length(dias))
  list(
    escenario = esc,
    horas = rejilla_horas(),
    ocup_media = colMeans(ocup),
    ocup_p05 = apply(ocup, 2, quantile, 0.05), ocup_p95 = apply(ocup, 2, quantile, 0.95),
    fila_media = colMeans(fila), fila_p95 = apply(fila, 2, quantile, 0.95),
    espera_int = colMeans(apilar("espera_int")),
    hora_lleno = hora_lleno,
    prob_llenado = mean(!is.na(hora_lleno)),
    hora_lleno_media = if (any(!is.na(hora_lleno))) mean(hora_lleno, na.rm = TRUE) else NA_real_,
    desviados = vec("n_desviados"),
    desv_media = mean(vec("n_desviados")),
    desv_destino = colMeans(apilar("desv_destino")),
    llegadas_media = mean(vec("n_llegadas")),
    salidas_media = mean(vec("n_salidas")),
    espera_media_s = mean(vec("espera_media_s")),
    espera_max_s = mean(vec("espera_max_s")),
    busq_media_s = mean(vec("busq_media_s")),
    ocup_max_media = mean(vec("ocup_max")),
    x1 = apilar("x1"),
    entre = unlist(lapply(dias[seq_len(tope)], `[[`, "entre")),
    franja = unlist(lapply(dias[seq_len(tope)], `[[`, "franja")),
    serv_s = unlist(lapply(dias[seq_len(tope)], `[[`, "serv_s")),
    x4 = unlist(lapply(dias, `[[`, "x4")),
    franja_x4 = unlist(lapply(dias, `[[`, "franja")),
    dia0 = dias[[1]]
  )
}

# P(el parqueadero se llena antes de `hora`)
prob_lleno_antes <- function(res, hora) mean(!is.na(res$hora_lleno) & res$hora_lleno <= hora)

hora_texto <- function(h) {
  if (is.null(h) || is.na(h)) return("No se llena")
  m <- round(h * 60)
  sprintf("%d:%02d", m %/% 60, m %% 60)
}

# Indicadores principales de un escenario (para tarjetas y comparacion)
resumen <- function(res, hora_ref) {
  r <- list(
    prob_ref = prob_lleno_antes(res, hora_ref),
    "P(se llena en la mañana)" = res$prob_llenado,
    "Hora esperada de llenado" = res$hora_lleno_media,
    "Vehículos desviados (media)" = res$desv_media,
    "Ocupación máxima (media)" = res$ocup_max_media,
    "Espera en la entrada (s)" = res$espera_media_s,
    "Fila al llegar, E[X4]" = if (length(res$x4)) mean(res$x4) else 0,
    "Búsqueda de cupo (s)" = res$busq_media_s,
    "Llegadas (media)" = res$llegadas_media,
    "Salidas (media)" = res$salidas_media
  )
  names(r)[1] <- sprintf("P(lleno antes de %s)", hora_texto(hora_ref))
  r
}

# Paquete que consume compartido/escena3d.html para animar un dia simulado
html_escena <- function(res) {
  esc <- res$escenario
  autos <- jsonlite::toJSON(res$dia0$autos, na = "null", digits = NA, auto_unbox = FALSE)
  datos <- sprintf(
    '{"layout":%s,"capacidad":%d,"hora_inicio":%s,"horizonte_s":%s,"vel_ms":%s,"destinos":%s,"autos":%s,"titulo":%s}',
    LAYOUT_JSON, esc$capacidad, PARAMETROS$horario$inicio_h, horizonte_min() * 60,
    format(esc$vel_kmh / 3.6, digits = 6),
    jsonlite::toJSON(DESTINOS), autos,
    jsonlite::toJSON(paste(esc$nombre, "·", esc$dia), auto_unbox = TRUE)
  )
  plantilla <- paste(readLines("compartido/escena3d.html", warn = FALSE, encoding = "UTF-8"), collapse = "\n")
  sub("/*__DATOS__*/null", datos, plantilla, fixed = TRUE)
}
