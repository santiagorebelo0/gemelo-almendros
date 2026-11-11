# Tablero Shiny: gemelo digital del parqueadero Almendros (PUJ Cali).
#
# Ejecutar localmente:           shiny::runApp()
# Ejecutar desde GitHub:         shiny::runGitHub("gemelo-almendros", "santiagorebelo0")
# El motor de simulacion esta en R/simulacion.R (Shiny lo carga automaticamente).

library(shiny)
library(bslib)
library(plotly)

if (!exists("simular")) source("R/simulacion.R", encoding = "UTF-8")

# ------------------------------------------------------------------ estilo de graficos
AZUL <- "#2a78d6"; NARANJA <- "#eb6834"; AGUA <- "#1baf7a"; AMARILLO <- "#eda100"
SERIES <- c(AZUL, NARANJA, AGUA, AMARILLO)
TINTA <- "#0b0b0b"; TENUE <- "#52514e"; REJILLA <- "#e9e7e2"
FRANJAS <- PARAMETROS$franjas$nombre
DIAS <- names(factores_por_dia())
H0 <- PARAMETROS$horario$inicio_h; H1 <- PARAMETROS$horario$fin_h
BASE <- escenario()

# Horas decimales -> texto de fecha, para que el eje muestre 8:15
a_hora <- function(h) format(as.POSIXct("2026-11-12 00:00:00", tz = "UTC") + round(h * 3600), "%Y-%m-%d %H:%M:%S")

lienzo <- function(p, titulo, eje_x, eje_y, horas = 0, leyenda = TRUE, abajo = FALSE) {
  ejex <- list(title = eje_x, gridcolor = REJILLA, zeroline = FALSE, showline = TRUE, linecolor = "#c9c7c0")
  if (horas > 0) {
    ejex <- c(ejex, list(type = "date", tickformat = "%-H:%M", hoverformat = "%-H:%M", tickangle = 0,
                         dtick = horas * 3600 * 1000, tick0 = a_hora(H0 + (H1 - H0) %% horas),
                         range = c(a_hora(H0 - 0.08), a_hora(H1 + 0.08))))
  }
  p |>
    layout(
      title = list(text = titulo, font = list(size = 15, color = TINTA), x = 0, xanchor = "left"),
      margin = if (abajo) list(l = 55, r = 20, t = 48, b = 96) else list(l = 55, r = 20, t = 64, b = 48),
      paper_bgcolor = "rgba(0,0,0,0)", plot_bgcolor = "rgba(0,0,0,0)",
      font = list(family = "system-ui, 'Segoe UI', sans-serif", size = 12, color = TENUE),
      hovermode = "x unified", showlegend = leyenda,
      legend = if (abajo) list(orientation = "h", y = -0.24, yanchor = "top", x = 0, xanchor = "left")
               else list(orientation = "h", y = 1, yanchor = "bottom", x = 1, xanchor = "right"),
      xaxis = ejex,
      yaxis = list(title = eje_y, gridcolor = REJILLA, zeroline = FALSE, rangemode = "tozero"),
      bargap = 0.12
    ) |>
    config(displayModeBar = FALSE)
}

discreta <- function(titulo, eje, muestra, teorica, nombre_teo) {
  tope <- if (length(muestra)) as.integer(max(quantile(muestra, 0.995), 4)) else 4L
  ks <- 0:tope
  frec <- tabulate(pmin(muestra, tope) + 1, nbins = tope + 1) / max(length(muestra), 1)
  plot_ly() |>
    add_bars(x = ks, y = frec, marker = list(color = AZUL), name = "Simulado",
             hovertemplate = "%{y:.3f}<extra>Simulado</extra>") |>
    add_trace(x = ks, y = teorica(ks), type = "scatter", mode = "lines+markers", name = nombre_teo,
              line = list(color = NARANJA, width = 2),
              marker = list(color = NARANJA, size = 7, line = list(color = "white", width = 1.5)),
              hovertemplate = paste0("%{y:.3f}<extra>", nombre_teo, "</extra>")) |>
    lienzo(titulo, eje, "Probabilidad")
}

continua <- function(titulo, eje, muestra, densidad, nombre_teo) {
  p <- plot_ly()
  if (length(muestra)) {
    tope <- as.numeric(quantile(muestra, 0.995))
    h <- hist(muestra[muestra <= tope], breaks = seq(0, tope, length.out = 37), plot = FALSE)
    ancho <- h$breaks[2] - h$breaks[1]
    xs <- seq(tope / 300, tope, length.out = 200)
    p <- p |>
      add_bars(x = h$mids, y = h$density, width = ancho * 0.94, marker = list(color = AZUL), name = "Simulado",
               hovertemplate = "%{y:.3f}<extra>Simulado</extra>") |>
      add_trace(x = xs, y = densidad(xs), type = "scatter", mode = "lines", name = nombre_teo,
                line = list(color = NARANJA, width = 2),
                hovertemplate = paste0("%{y:.3f}<extra>", nombre_teo, "</extra>"))
  }
  p |> lienzo(titulo, eje, "Densidad") |> layout(xaxis = list(hoverformat = ".2f"))
}

# Lo necesario de un resultado para compararlo despues
paquete <- function(res, hora_ref) {
  list(resumen = resumen(res, hora_ref), horas = res$horas, ocup = res$ocup_media, fila = res$fila_media,
       hora_lleno = res$hora_lleno, capacidad = res$escenario$capacidad)
}

formato_indicador <- function(nombre, v) {
  if (grepl("^Hora", nombre)) hora_texto(v)
  else if (grepl("^P\\(", nombre)) sprintf("%.0f%%", 100 * v)
  else if (grepl("X4", nombre)) sprintf("%.2f", v)
  else sprintf("%.1f", v)
}

horas_ref <- seq(H0 + 1, H1, by = 0.25)
names(horas_ref) <- vapply(horas_ref, hora_texto, "")

# ------------------------------------------------------------------ interfaz
ui <- page_sidebar(
  title = "Gemelo digital del parqueadero Almendros",
  theme = bs_theme(version = 5, primary = "#1e3a8a", "font-size-base" = "0.92rem"),
  fillable = FALSE,
  sidebar = sidebar(
    width = 330, title = "Parámetros del escenario",
    textInput("nombre", "Nombre del escenario", "Base"),
    selectInput("dia", "Día de la semana", DIAS) |>
      tooltip("Ajusta las tasas de llegada con la Tabla 1 de Varela et al. (2023). «Promedio» usa los valores preliminares de la Entrega 2."),
    helpText(strong("X1 · Llegadas"), "— λ en vehículos por intervalo de 15 minutos"),
    sliderInput("lam0", paste("λ₁ ·", FRANJAS[1]), 0, 30, BASE$lambdas[1], step = 0.1, ticks = FALSE),
    sliderInput("lam1", paste("λ₂ ·", FRANJAS[2]), 0, 30, BASE$lambdas[2], step = 0.1, ticks = FALSE),
    sliderInput("lam2", paste("λ₃ ·", FRANJAS[3]), 0, 30, BASE$lambdas[3], step = 0.1, ticks = FALSE),
    sliderInput("capacidad", "Capacidad (cupos)", PARAMETROS$capacidad_min, PARAMETROS$capacidad_max, BASE$capacidad, step = 2, ticks = FALSE),
    helpText(strong("X3 · Talanquera"), "— tiempo de atención Gamma(α, β)"),
    sliderInput("tal_media", "Tiempo medio en la talanquera (s)", 4, 60, BASE$tal_media_s, step = 1, ticks = FALSE),
    sliderInput("tal_cv", "Coeficiente de variación de X3", 0.2, 1, BASE$tal_cv, step = 0.05, ticks = FALSE),
    helpText(strong("Salidas"), "— permanencia Gamma"),
    input_switch("salidas", "Modelar salidas durante la mañana", BASE$salidas),
    sliderInput("perm_media", "Permanencia media (h)", 2, 10, BASE$perm_media_h, step = 0.5, ticks = FALSE),
    sliderInput("perm_cv", "Coeficiente de variación de la permanencia", 0.1, 0.8, BASE$perm_cv, step = 0.05, ticks = FALSE),
    accordion(open = FALSE, accordion_panel(
      "Opciones avanzadas",
      sliderInput("vel", "Velocidad dentro del parqueadero (km/h)", 5, 20, BASE$vel_kmh, step = 1, ticks = FALSE),
      sliderInput("maniobra", "Maniobra de parqueo (s)", 5, 40, BASE$maniobra_s, step = 1, ticks = FALSE),
      selectInput("replicas", "Réplicas (días simulados)", c(100, 200, 500, 1000, 2000), BASE$replicas),
      numericInput("semilla", "Semilla", BASE$semilla, min = 1, step = 1)
    )),
    actionButton("ejecutar", "Ejecutar simulación", class = "btn-primary"),
    actionButton("guardar", "Guardar escenario para comparar", class = "btn-outline-secondary")
  ),
  uiOutput("encabezado"),
  uiOutput("indicadores"),
  navset_card_underline(
    id = "pestanas",
    nav_panel("Gemelo 3D", uiOutput("nota3d"), uiOutput("escena")),
    nav_panel(
      "Resultados",
      selectInput("hora_ref", "Hora de referencia para P(lleno antes de …)", horas_ref, selected = PARAMETROS$hora_referencia_h, width = "320px"),
      layout_columns(col_widths = c(7, 5), plotlyOutput("g_ocup", height = "360px"), plotlyOutput("g_lleno", height = "360px")),
      layout_columns(col_widths = c(4, 4, 4), plotlyOutput("g_fila", height = "310px"),
                     plotlyOutput("g_espera", height = "310px"), plotlyOutput("g_desv", height = "310px")),
      uiOutput("nota_resultados"),
      accordion(open = FALSE, accordion_panel("Ver los datos de las curvas", tableOutput("tabla_curvas")))
    ),
    nav_panel(
      "Variables aleatorias",
      p(class = "text-muted small", "Cada gráfico compara lo que produce la simulación (barras) con la distribución teórica declarada en la Entrega 2 (línea). Sirve para verificar que el modelo hace lo que dice."),
      radioButtons("franja", "Franja horaria", setNames(seq_along(FRANJAS), FRANJAS), inline = TRUE),
      layout_columns(col_widths = c(6, 6, 6, 6),
                     plotlyOutput("g_x1", height = "310px"), plotlyOutput("g_x2", height = "310px"),
                     plotlyOutput("g_x3", height = "310px"), plotlyOutput("g_x4", height = "310px")),
      tableOutput("tabla_momentos"),
      uiOutput("nota_variables")
    ),
    nav_panel(
      "Comparar escenarios",
      div(class = "d-flex gap-2 mb-3",
          actionButton("sugeridos", "Cargar comparación sugerida", class = "btn-outline-primary btn-sm"),
          actionButton("borrar", "Borrar escenarios guardados", class = "btn-outline-secondary btn-sm")),
      uiOutput("comparacion")
    ),
    nav_panel("Modelo y supuestos", uiOutput("modelo"))
  )
)

# ------------------------------------------------------------------ servidor
server <- function(input, output, session) {
  actual <- reactive({
    nombre <- trimws(input$nombre); if (!nzchar(nombre)) nombre <- "Escenario"
    escenario(nombre = nombre, dia = input$dia, lambdas = c(input$lam0, input$lam1, input$lam2),
              capacidad = input$capacidad, tal_media_s = input$tal_media, tal_cv = input$tal_cv,
              salidas = input$salidas, perm_media_h = input$perm_media, perm_cv = input$perm_cv,
              vel_kmh = input$vel, maniobra_s = input$maniobra,
              replicas = as.integer(input$replicas), semilla = as.integer(input$semilla))
  })
  params <- reactiveVal(BASE)
  guardados <- reactiveVal(list())
  observeEvent(input$ejecutar, params(actual()))
  observeEvent(input$dia, {
    lam <- lambdas_del_dia(input$dia)
    for (k in 1:3) updateSliderInput(session, paste0("lam", k - 1), value = lam[k])
  }, ignoreInit = TRUE)

  res <- reactive({
    withProgress(message = "Simulando…", value = 0.5, simular(params()))
  }) |> bindCache(params())
  hora_ref <- reactive(as.numeric(input$hora_ref))

  observeEvent(input$guardar, {
    g <- guardados(); nombre <- params()$nombre
    if (length(g) >= 4 && !(nombre %in% names(g))) {
      showNotification("Se comparan máximo 4 escenarios. Borra los guardados en la pestaña «Comparar escenarios».", type = "warning")
    } else {
      g[[nombre]] <- paquete(res(), hora_ref()); guardados(g)
      showNotification(sprintf("«%s» guardado.", nombre), type = "message")
    }
  })
  observeEvent(input$sugeridos, {
    p <- params()
    lista <- list(
      escenario(nombre = "Base"),
      escenario(nombre = "30 cupos más", capacidad = PARAMETROS$capacidad + 30),
      escenario(nombre = "Demanda +20 %", lambdas = round(BASE$lambdas * 1.2, 1)),
      escenario(nombre = "Talanquera lenta (45 s)", tal_media_s = 45)
    )
    g <- list()
    withProgress(message = "Simulando escenarios…", value = 0, {
      for (e in lista) {
        e$replicas <- p$replicas; e$semilla <- p$semilla
        g[[e$nombre]] <- paquete(simular(e), hora_ref()); incProgress(1 / length(lista))
      }
    })
    guardados(g)
  })
  observeEvent(input$borrar, guardados(list()))

  # ---------------- encabezado e indicadores
  output$encabezado <- renderUI({
    e <- res()$escenario
    a <- actual(); p <- params(); a$nombre <- p$nombre <- NULL
    tagList(
      p(class = "text-muted small mb-2", HTML(sprintf(
        "Pontificia Universidad Javeriana Cali · Teoría de Probabilidades · Escenario <b>%s</b> (%s) · %d días simulados de %d:00 a %d:00",
        htmltools::htmlEscape(e$nombre), e$dia, e$replicas, H0, H1))),
      if (!isTRUE(all.equal(a, p, check.attributes = FALSE))) div(class = "alert alert-info py-2", HTML("Cambiaste parámetros. Pulsa <b>Ejecutar simulación</b> para actualizar los resultados."))
    )
  })
  output$indicadores <- renderUI({
    r <- res(); h <- hora_ref()
    caja <- function(titulo, valor) value_box(title = span(class = "small", titulo), value = valor, theme = "light", min_height = "104px")
    layout_column_wrap(
      width = "170px", class = "mb-3",     # se reacomoda en pantallas angostas
      caja(sprintf("P(lleno antes de %s)", hora_texto(h)), sprintf("%.0f%%", 100 * prob_lleno_antes(r, h))),
      caja("Hora esperada de llenado", hora_texto(r$hora_lleno_media)),
      caja("Vehículos desviados", sprintf("%.1f", r$desv_media)),
      caja("Espera en la entrada", sprintf("%.1f s", r$espera_media_s)),
      caja("Fila al llegar, E[X4]", sprintf("%.2f", if (length(r$x4)) mean(r$x4) else 0))
    )
  })

  # ---------------- gemelo 3D
  output$nota3d <- renderUI({
    d <- res()$dia0
    p(class = "text-muted small", HTML(sprintf(
      "Animación de <b>un</b> día simulado (la primera réplica): %d llegadas, %d parquean, %d desviados, %d salen antes de las %d:00. Arrastra para girar, rueda para acercar, y usa la línea de tiempo inferior para moverte en la mañana.",
      d$n_llegadas, d$n_parqueados, d$n_desviados, d$n_salidas, H1)))
  })
  output$escena <- renderUI({
    tags$iframe(srcdoc = html_escena(res()), title = "Escena 3D del parqueadero",
                style = "width:100%; height:640px; border:0; border-radius:10px;")
  })

  # ---------------- resultados
  output$g_ocup <- renderPlotly({
    r <- res(); x <- a_hora(r$horas); C <- r$escenario$capacidad
    plot_ly() |>
      add_ribbons(x = x, ymin = r$ocup_p05, ymax = r$ocup_p95, fillcolor = "rgba(42,120,214,.18)",
                  line = list(width = 0), name = "Entre el 5 % y el 95 % de los días", hoverinfo = "skip") |>
      add_trace(x = x, y = r$ocup_media, type = "scatter", mode = "lines", line = list(color = AZUL, width = 2),
                name = "Media", hovertemplate = "%{y:.0f} vehículos<extra>Media</extra>") |>
      lienzo("Ocupación según la hora", "Hora", "Vehículos parqueados", horas = 1) |>
      layout(yaxis = list(range = c(0, C * 1.12)),
             shapes = list(list(type = "line", xref = "paper", x0 = 0, x1 = 1, y0 = C, y1 = C,
                                line = list(color = TENUE, width = 1, dash = "dash"))),
             annotations = list(list(xref = "paper", x = 0.01, y = C, yanchor = "bottom", xanchor = "left", showarrow = FALSE,
                                     text = paste("Capacidad:", C), font = list(color = TENUE, size = 11))))
  })
  output$g_lleno <- renderPlotly({
    r <- res(); llenos <- r$hora_lleno[!is.na(r$hora_lleno)]
    p <- plot_ly()
    if (length(llenos)) {
      h <- hist(llenos, breaks = seq(H0, H1 + 0.25, by = 0.25), plot = FALSE)
      marca <- a_hora(hora_ref())
      p <- p |>
        add_bars(x = a_hora(h$mids), y = h$counts, width = 0.25 * 3600 * 1000 * 0.9, marker = list(color = AZUL),
                 hovertemplate = "%{y} días<extra></extra>") |>
        layout(shapes = list(list(type = "line", x0 = marca, x1 = marca, yref = "paper", y0 = 0, y1 = 1,
                                  line = list(color = TENUE, width = 1, dash = "dash"))),
               annotations = list(list(x = marca, yref = "paper", y = 1, yanchor = "bottom", showarrow = FALSE,
                                       text = hora_texto(hora_ref()), font = list(color = TENUE, size = 11))))
    } else {
      p <- p |> layout(annotations = list(list(text = "El parqueadero no se llena en ningún día simulado", showarrow = FALSE,
                                               xref = "paper", yref = "paper", x = 0.5, y = 0.5, font = list(size = 13, color = TENUE))))
    }
    p |> lienzo("Hora de llenado", "Hora en que se ocupa el último cupo", "Días simulados", horas = 2, leyenda = FALSE)
  })
  output$g_fila <- renderPlotly({
    r <- res(); x <- a_hora(r$horas)
    plot_ly() |>
      add_trace(x = x, y = r$fila_p95, type = "scatter", mode = "lines", line = list(color = NARANJA, width = 1.5, dash = "dot"),
                name = "Percentil 95", hovertemplate = "%{y:.1f}<extra>Percentil 95</extra>") |>
      add_trace(x = x, y = r$fila_media, type = "scatter", mode = "lines", line = list(color = AZUL, width = 2),
                name = "Media", hovertemplate = "%{y:.2f}<extra>Media</extra>") |>
      lienzo("Fila en la entrada (incluye la talanquera)", "Hora", "Vehículos", horas = 2)
  })
  output$g_espera <- renderPlotly({
    r <- res()
    plot_ly() |>
      add_trace(x = a_hora(head(r$horas, -1) + 0.125), y = r$espera_int, type = "scatter", mode = "lines",
                line = list(color = AZUL, width = 2), hovertemplate = "%{y:.1f} s<extra></extra>") |>
      lienzo("Espera antes de la talanquera", "Hora de llegada", "Segundos (media)", horas = 2, leyenda = FALSE)
  })
  output$g_desv <- renderPlotly({
    d <- res()$desviados
    paso <- max(1, ceiling((max(d) - min(d) + 1) / 25))
    h <- hist(d, breaks = seq(min(d), max(d) + paso, by = paso) - 0.5, plot = FALSE)
    plot_ly() |>
      add_bars(x = h$mids, y = h$counts, width = paso * 0.9, marker = list(color = AZUL), hovertemplate = "%{y} días<extra></extra>") |>
      lienzo("Vehículos desviados por mañana", "Vehículos desviados", "Días simulados", leyenda = FALSE)
  })
  output$nota_resultados <- renderUI({
    r <- res()
    reparto <- paste(sprintf("%s: %.1f", DESTINOS, r$desv_destino), collapse = " · ")
    p(class = "text-muted small", sprintf(
      "Reparto de los desviados según Iguarán et al. (2019), media por mañana → %s. Llegadas: %.0f · Salidas antes de las %d:00: %.0f · Búsqueda de cupo: %.0f s en promedio.",
      reparto, r$llegadas_media, H1, r$salidas_media, r$busq_media_s))
  })
  output$tabla_curvas <- renderTable({
    r <- res()
    data.frame(Hora = vapply(r$horas, hora_texto, ""), "Ocupación media" = round(r$ocup_media, 1),
               "Ocupación p5" = round(r$ocup_p05), "Ocupación p95" = round(r$ocup_p95),
               "Fila media" = round(r$fila_media, 2), "Fila p95" = round(r$fila_p95, 1), check.names = FALSE)
  }, striped = TRUE, spacing = "s")

  # ---------------- variables aleatorias
  muestras <- reactive({
    r <- res(); e <- r$escenario; k <- as.integer(input$franja)
    fr <- PARAMETROS$franjas
    cols <- ((fr$inicio_h[k] - H0) * 4 + 1):((fr$fin_h[k] - H0) * 4)
    list(e = e, k = k, lam = e$lambdas[k], tasa = e$lambdas[k] / 15, rho = rho_franjas(e)[k],
         alfa = alfa_x3(e), beta = beta_x3(e),
         x1 = as.vector(r$x1[, cols]), x2 = r$entre[r$franja == k], x3 = r$serv_s, x4 = r$x4[r$franja_x4 == k])
  })
  output$g_x1 <- renderPlotly({ m <- muestras()
    discreta("X1 · Llegadas por intervalo de 15 min", "Vehículos en 15 minutos", m$x1, function(q) dpois(q, m$lam), sprintf("Poisson(λ = %g)", m$lam)) })
  output$g_x2 <- renderPlotly({ m <- muestras()
    continua("X2 · Tiempo entre llegadas", "Minutos", m$x2, function(q) dexp(q, m$tasa), sprintf("Exponencial(λ = %.3f)", m$tasa)) })
  output$g_x3 <- renderPlotly({ m <- muestras()
    continua("X3 · Tiempo en la talanquera", "Segundos", m$x3, function(q) dgamma(q, shape = m$alfa, rate = m$beta), sprintf("Gamma(α = %.2f, β = %.3f)", m$alfa, m$beta)) })
  output$g_x4 <- renderPlotly({ m <- muestras()
    discreta("X4 · Vehículos delante al llegar", "Vehículos en fila o en la talanquera", m$x4, function(q) dgeom(q, 1 - m$rho), sprintf("Geométrica(p = %.3f)", 1 - m$rho)) })
  output$tabla_momentos <- renderTable({
    m <- muestras(); p <- 1 - m$rho
    fila <- function(nombre, dist, e_teo, v_teo, x) data.frame(
      Variable = nombre, "Distribución" = dist, "E[X] teórico" = e_teo, "E[X] simulado" = mean(x),
      "Var[X] teórica" = v_teo, "Var[X] simulada" = var(x), check.names = FALSE)
    rbind(
      fila("X1 (vehículos / 15 min)", sprintf("Poisson(%g)", m$lam), m$lam, m$lam, m$x1),
      fila("X2 (min)", sprintf("Exponencial(%.3f)", m$tasa), 1 / m$tasa, 1 / m$tasa^2, m$x2),
      fila("X3 (s)", sprintf("Gamma(%.2f, %.3f)", m$alfa, m$beta), m$alfa / m$beta, m$alfa / m$beta^2, m$x3),
      fila("X4 (vehículos)", sprintf("Geométrica(%.3f)", p), (1 - p) / p, (1 - p) / p^2, m$x4)
    )
  }, striped = TRUE, digits = 3, width = "100%")
  output$nota_variables <- renderUI({
    m <- muestras()
    p(class = "text-muted small", sprintf(
      "Utilización de la talanquera en esta franja: ρ = λ · E[X3] = %.3f. La geométrica de X4 es exacta con servicio exponencial (CV = 1); con servicio Gamma es una aproximación, aunque P(X4 = 0) = 1 − ρ se cumple en ambos casos.", m$rho))
  })

  # ---------------- comparar escenarios
  output$comparacion <- renderUI({
    if (!length(guardados())) {
      return(div(class = "alert alert-info", HTML("Aún no hay escenarios guardados. Cambia parámetros, ejecuta la simulación y pulsa <b>Guardar escenario para comparar</b>, o carga la comparación sugerida.")))
    }
    tagList(
      tableOutput("tabla_comparacion"),
      layout_columns(col_widths = c(6, 6), plotlyOutput("g_cmp_ocup", height = "400px"), plotlyOutput("g_cmp_prob", height = "400px"))
    )
  })
  output$tabla_comparacion <- renderTable({
    g <- guardados(); req(length(g) > 0)
    indicadores <- c("Capacidad", names(g[[1]]$resumen))
    indicadores[2] <- sub("antes de .*\\)", "antes de la hora de referencia)", indicadores[2])
    tabla <- data.frame(Indicador = indicadores, check.names = FALSE)
    for (nombre in names(g)) {
      r <- g[[nombre]]$resumen
      tabla[[nombre]] <- c(as.character(g[[nombre]]$capacidad), mapply(formato_indicador, names(r), r))
    }
    tabla
  }, striped = TRUE, width = "100%")
  output$g_cmp_ocup <- renderPlotly({
    g <- guardados(); req(length(g) > 0); p <- plot_ly()
    for (j in seq_along(g)) {
      p <- p |> add_trace(x = a_hora(g[[j]]$horas), y = g[[j]]$ocup, type = "scatter", mode = "lines", name = names(g)[j],
                          line = list(color = SERIES[(j - 1) %% 4 + 1], width = 2),
                          hovertemplate = paste0("%{y:.0f}<extra>", names(g)[j], "</extra>"))
    }
    p |> lienzo("Ocupación media según la hora", "Hora", "Vehículos parqueados", horas = 1, abajo = TRUE)
  })
  output$g_cmp_prob <- renderPlotly({
    g <- guardados(); req(length(g) > 0); p <- plot_ly(); hs <- seq(H0, H1, by = 0.25)
    for (j in seq_along(g)) {
      hl <- g[[j]]$hora_lleno
      pr <- vapply(hs, function(h) mean(!is.na(hl) & hl <= h), 0)
      p <- p |> add_trace(x = a_hora(hs), y = pr, type = "scatter", mode = "lines", name = names(g)[j],
                          line = list(color = SERIES[(j - 1) %% 4 + 1], width = 2),
                          hovertemplate = paste0("%{y:.0%}<extra>", names(g)[j], "</extra>"))
    }
    p |> lienzo("Probabilidad de estar lleno antes de cada hora", "Hora", "Probabilidad", horas = 1, abajo = TRUE) |>
      layout(yaxis = list(tickformat = ".0%", range = c(0, 1.05)))
  })

  # ---------------- modelo y supuestos
  output$modelo <- renderUI({
    e <- res()$escenario; rh <- rho_franjas(e)
    markdown(sprintf("
#### Variables aleatorias del escenario actual

| Variable | Qué representa | Distribución | Parámetros en uso |
|---|---|---|---|
| **X1** | Vehículos que llegan en 15 minutos (discreta) | Poisson(λₖ) | λ₁ = %g, λ₂ = %g, λ₃ = %g |
| **X2** | Minutos entre dos llegadas consecutivas (continua) | Exponencial(λₖ / 15) | %.3f, %.3f y %.3f por minuto |
| **X3** | Segundos en la talanquera (continua) | Gamma(α, β) | α = %.2f, β = %.3f (media %g s, CV %g) |
| **X4** | Vehículos delante al llegar (discreta) | Geométrica(p = 1 − ρ) | ρ = %.3f, %.3f y %.3f por franja |
| Permanencia | Horas que el vehículo ocupa el cupo (continua) | Gamma | media %g h, CV %g (%s) |

#### Cómo funciona la simulación
1. Se generan las llegadas del día con tiempos entre llegadas exponenciales, usando la λ de cada franja.
2. Cada vehículo espera si la talanquera está ocupada (una sola, en orden de llegada) y es atendido un tiempo Gamma.
3. Al subir la barrera, si hay cupo toma el **cupo libre más cercano** a la entrada; si no, queda **desviado**.
4. Si las salidas están activas, permanece un tiempo Gamma y libera el cupo.
5. El día se repite %d veces y se resumen los indicadores.

#### Supuestos
- Las llegadas son independientes entre sí y el parqueadero empieza vacío a las %d:00.
- Los valores de λ son los **preliminares de la Entrega 2**, derivados de la distribución de horas de llegada de Varela et al. (2023) y de la capacidad de 230 cupos. El selector de día los multiplica por el peso de ese día en la Tabla 1 del mismo estudio.
- **No hubo medición en campo.** El tiempo en la talanquera (media 12 s) es un supuesto ajustable. La permanencia usa una Gamma con la misma media (7 h) y desviación (2,9 h) que la Uniforme(2 h, 12 h) de Iguarán et al. (2019); con esos valores el modelo reproduce la congestión de 8:30 a 9:30 que reporta Varela et al. (2023).
- El reparto de los desviados (Gualanday 78 %%, Central 22 %%) sale de la Tabla 2 de Iguarán et al. (2019), columna «No hay en CDL», que es el parqueadero con acceso por la Calle 17a en ese estudio. Ceibas no existía entonces y queda en 0 %%.
- El plano 3D se trazó sobre la vista satelital: el contorno, las islas con bordillo en sierra, el laboratorio y la portería de la Calle 17a están medidos en la imagen. La posición de cada cupo es estimada, porque el piso es grava sin demarcación, y se ajustó para sumar 230. Los cupos 231 a 276 son una zona de ampliación hipotética al occidente.

#### Fuentes
- Varela, C., Solarte, L. y Suárez, S. (2023). *El aumento de la demanda en los parqueaderos de la Universidad Javeriana de Cali*. RPubs. <https://rpubs.com/lsolarte/1041166>
- Iguarán, J., López, M., Muñoz, C. y Sarmiento, G. (2019). *Análisis del nivel de utilización de los parqueaderos en la Universidad Javeriana Cali*. Scribd. <https://es.scribd.com/document/438890279/SIMULACION-DE-PARQUEADEROS>
- González, D. (2026). *Guía del proyecto: gemelo digital de un sistema universitario*. <https://dgonxalex80.github.io/curso013/guia_proyecto1.html>
", e$lambdas[1], e$lambdas[2], e$lambdas[3], e$lambdas[1] / 15, e$lambdas[2] / 15, e$lambdas[3] / 15,
      alfa_x3(e), beta_x3(e), e$tal_media_s, e$tal_cv, rh[1], rh[2], rh[3],
      e$perm_media_h, e$perm_cv, if (e$salidas) "activa" else "apagada: nadie sale", e$replicas, H0))
  })
}

shinyApp(ui, server)
