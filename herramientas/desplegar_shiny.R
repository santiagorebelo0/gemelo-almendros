# Publica el tablero Shiny en shinyapps.io.
# Antes, una sola vez: crea la cuenta en https://www.shinyapps.io, entra a
# Account > Tokens > Show, copia la linea rsconnect::setAccountInfo(...) y ejecutala en R.
# Luego, desde la carpeta del proyecto:  source("herramientas/desplegar_shiny.R")

if (!requireNamespace("rsconnect", quietly = TRUE)) install.packages("rsconnect")

rsconnect::deployApp(
  appDir = ".",
  appName = "gemelo-almendros",
  appTitle = "Gemelo digital del parqueadero Almendros",
  appFiles = c("app.R", "R/simulacion.R",
               "compartido/parametros.json", "compartido/layout.json", "compartido/escena3d.html"),
  forceUpdate = TRUE
)
