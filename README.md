# Gemelo digital del parqueadero Almendros

Proyecto final de Teoría de Probabilidades (Pontificia Universidad Javeriana Cali).
Néstor Acosta, José Luis Canchala y José Santiago Rebelo.

Simula la entrada y la ocupación del parqueadero Almendros entre las 5:00 y las 12:00 de un
día hábil, y lo muestra en un tablero con una escena 3D animada. El mismo modelo está en dos
versiones que comparten parámetros, plano y escena:

| Versión | Archivo principal | Motor de simulación |
|---|---|---|
| Shiny (R) | `app.R` | `R/simulacion.R` |
| Streamlit (Python) | `streamlit_app.py` | `simulacion.py` |

## Modelo

| Variable | Qué representa | Distribución |
|---|---|---|
| X1 | Vehículos que llegan en 15 minutos | Poisson(λₖ), una λ por franja |
| X2 | Minutos entre llegadas consecutivas | Exponencial(λₖ / 15) |
| X3 | Segundos en la talanquera | Gamma(α, β) |
| X4 | Vehículos delante al llegar | Geométrica(p = 1 − ρ), ρ = λ · E[X3] |

Extensiones de la Entrega 3: perfil por día de la semana (Tabla 1 de Varela et al., 2023),
permanencia Gamma con liberación de cupos, búsqueda del cupo libre más cercano y reparto de
los vehículos desviados entre Gualanday y Central (Tabla 2 de Iguarán et al., 2019).

Los valores por defecto están en `compartido/parametros.json`. No hubo medición en campo: las
λ son las preliminares de la Entrega 2, el tiempo de talanquera es un supuesto ajustable y la
permanencia usa la media y la desviación de la Uniforme(2 h, 12 h) de Iguarán et al. (2019).

## Estructura

```
app.R                      Tablero Shiny
R/simulacion.R             Motor en R
streamlit_app.py           Tablero Streamlit
simulacion.py              Motor en Python
compartido/parametros.json Parámetros por defecto (los leen ambas versiones)
compartido/layout.json     Plano del parqueadero (lo genera herramientas/generar_layout.py)
compartido/escena3d.html   Escena 3D en Three.js (la incrustan ambas versiones)
herramientas/              Generador del plano y script de despliegue de Shiny
requirements.txt           Dependencias de Python
```

## Ejecutar en el computador

Shiny, desde R o RStudio con la carpeta del proyecto como directorio de trabajo:

```r
install.packages(c("shiny", "bslib", "plotly", "jsonlite"))
shiny::runApp()
```

Streamlit:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

La escena 3D descarga Three.js de un CDN, así que necesita conexión a internet.

## Subir a GitHub

1. En https://github.com/new crea un repositorio **público** y **vacío** llamado `gemelo-almendros`.
2. En una terminal dentro de esta carpeta (cambia `santiagorebelo0` por tu usuario de GitHub):

```bash
git init
git add .
git commit -m "Gemelo digital del parqueadero Almendros"
git branch -M main
git remote add origin https://github.com/santiagorebelo0/gemelo-almendros.git
git push -u origin main
```

Cualquier persona con R puede abrir el tablero Shiny directamente desde el repositorio:

```r
shiny::runGitHub("gemelo-almendros", "santiagorebelo0")
```

## Publicar Streamlit (Streamlit Community Cloud)

1. Entra a https://share.streamlit.io e inicia sesión con GitHub.
2. **Create app** → repositorio `santiagorebelo0/gemelo-almendros`, rama `main`, archivo `streamlit_app.py`.
3. **Deploy**. Queda en una dirección `https://….streamlit.app` y se actualiza sola con cada `git push`.

## Publicar Shiny (shinyapps.io)

1. Crea una cuenta gratuita en https://www.shinyapps.io.
2. En **Account → Tokens → Show** copia la línea `rsconnect::setAccountInfo(...)` y ejecútala una vez en R.
3. Con la carpeta del proyecto como directorio de trabajo:

```r
source("herramientas/desplegar_shiny.R")
```

Queda en `https://TU-CUENTA.shinyapps.io/gemelo-almendros/`. Para actualizarla después de un
cambio, vuelve a ejecutar el paso 3.

## Ajustar el plano 3D

El plano se trazó sobre la vista satelital de Google Maps (3.34523, -76.53189): contorno, islas
con bordillo en sierra, Laboratorio Central de Mezclas y portería sobre la Calle 17a. La posición
de cada cupo es estimada (el piso es grava sin demarcación) y suma 230; los cupos 231 a 276 son
una zona de ampliación hipotética. Para cambiarlo, edita `herramientas/generar_layout.py` y
ejecuta `python herramientas/generar_layout.py`.

## Fuentes

- Varela, C., Solarte, L. y Suárez, S. (2023). *El aumento de la demanda en los parqueaderos de la Universidad Javeriana de Cali*. RPubs. https://rpubs.com/lsolarte/1041166
- Iguarán, J., López, M., Muñoz, C. y Sarmiento, G. (2019). *Análisis del nivel de utilización de los parqueaderos en la Universidad Javeriana Cali*. Scribd. https://es.scribd.com/document/438890279/SIMULACION-DE-PARQUEADEROS
- González, D. (2026). *Guía del proyecto: gemelo digital de un sistema universitario*. https://dgonxalex80.github.io/curso013/guia_proyecto1.html
