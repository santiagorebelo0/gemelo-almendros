"""Tablero Streamlit: gemelo digital del parqueadero Almendros (PUJ Cali).

Ejecutar localmente:  streamlit run streamlit_app.py
"""
from math import lgamma

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import simulacion as sim
from simulacion import PARAMETROS, Escenario, hora_texto

st.set_page_config(page_title="Gemelo digital · Parqueadero Almendros", page_icon="🅿️", layout="wide")

# ------------------------------------------------------------------ estilo de gráficos
AZUL, NARANJA, AGUA, AMARILLO = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
SERIES = [AZUL, NARANJA, AGUA, AMARILLO]
TINTA, TENUE, REJILLA = "#0b0b0b", "#52514e", "#e9e7e2"
FRANJAS = [f["nombre"] for f in PARAMETROS["franjas"]]
DIAS = list(sim.factores_por_dia().keys())
H0, H1 = PARAMETROS["horario"]["inicio_h"], PARAMETROS["horario"]["fin_h"]
FECHA = pd.Timestamp("2026-11-12")


def a_hora(h):
    """Convierte horas decimales en marcas de tiempo para que el eje muestre 8:15."""
    return FECHA + pd.to_timedelta(np.asarray(h, float) * 3600, unit="s")


def lienzo(titulo, eje_x, eje_y, alto=330, horas=0, leyenda=True):
    """horas = separación de las marcas del eje de tiempo, en horas (0 = eje numérico)."""
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15, color=TINTA), x=0, xanchor="left"),
        height=alto, margin=dict(l=55, r=20, t=64, b=48),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, 'Segoe UI', sans-serif", size=12, color=TENUE),
        hovermode="x unified", showlegend=leyenda,
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1, xanchor="right"),
        xaxis=dict(title=eje_x, gridcolor=REJILLA, zeroline=False, showline=True, linecolor="#c9c7c0"),
        yaxis=dict(title=eje_y, gridcolor=REJILLA, zeroline=False, rangemode="tozero"),
        bargap=0.12,
    )
    if horas:
        fig.update_xaxes(tickformat="%-H:%M", hoverformat="%-H:%M", dtick=horas * 3600 * 1000, tick0=a_hora(H0 + (H1 - H0) % horas),
                         tickangle=0,
                         range=[a_hora(H0 - 0.08), a_hora(H1 + 0.08)])
    return fig


LEYENDA_ABAJO = dict(legend=dict(orientation="h", y=-0.24, yanchor="top", x=0, xanchor="left"), margin=dict(b=96, t=48))


def mostrar(fig, clave=None):
    st.plotly_chart(fig, width="stretch", theme=None, key=clave, config={"displayModeBar": False})


# ------------------------------------------------------------------ distribuciones teóricas
def pmf_poisson(k, lam):
    return np.array([np.exp(-lam + x * np.log(lam) - lgamma(x + 1)) if lam > 0 else float(x == 0) for x in k])


def pdf_gamma(x, forma, tasa):
    x = np.maximum(np.asarray(x, float), 1e-12)
    return np.exp(forma * np.log(tasa) + (forma - 1) * np.log(x) - tasa * x - lgamma(forma))


# ------------------------------------------------------------------ simulación con caché
@st.cache_data(show_spinner=False, max_entries=24)
def correr(parametros: dict) -> dict:
    return sim.simular(Escenario(**parametros))


def escenario_actual() -> dict:
    s = st.session_state
    return dict(
        nombre=s.nombre.strip() or "Escenario", dia=s.dia,
        lambdas=[float(s.lam0), float(s.lam1), float(s.lam2)],
        capacidad=int(s.capacidad), tal_media_s=float(s.tal_media), tal_cv=float(s.tal_cv),
        salidas=bool(s.salidas), perm_media_h=float(s.perm_media), perm_cv=float(s.perm_cv),
        vel_kmh=float(s.vel), maniobra_s=float(s.maniobra), replicas=int(s.replicas), semilla=int(s.semilla),
    )


def sin_nombre(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "nombre"}


# ------------------------------------------------------------------ estado inicial
base = Escenario()
INICIAL = dict(
    nombre="Base", dia="Promedio", lam0=base.lambdas[0], lam1=base.lambdas[1], lam2=base.lambdas[2],
    capacidad=base.capacidad, tal_media=float(base.tal_media_s), tal_cv=base.tal_cv, salidas=base.salidas,
    perm_media=base.perm_media_h, perm_cv=base.perm_cv, vel=float(base.vel_kmh), maniobra=float(base.maniobra_s),
    replicas=base.replicas, semilla=base.semilla, hora_ref=PARAMETROS["hora_referencia_h"],
)
for k, v in INICIAL.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("guardados", {})


def al_cambiar_dia():
    lam = sim.lambdas_del_dia(st.session_state.dia)
    st.session_state.lam0, st.session_state.lam1, st.session_state.lam2 = lam


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.markdown("### Parámetros del escenario")
    st.text_input("Nombre del escenario", key="nombre")
    st.selectbox("Día de la semana", DIAS, key="dia", on_change=al_cambiar_dia,
                 help="Ajusta las tasas de llegada con la Tabla 1 de Varela et al. (2023). "
                      "«Promedio» usa los valores preliminares de la Entrega 2.")
    st.caption("**X1 · Llegadas** — λ en vehículos por intervalo de 15 minutos")
    st.slider(f"λ₁ · {FRANJAS[0]}", 0.0, 30.0, step=0.1, key="lam0")
    st.slider(f"λ₂ · {FRANJAS[1]}", 0.0, 30.0, step=0.1, key="lam1")
    st.slider(f"λ₃ · {FRANJAS[2]}", 0.0, 30.0, step=0.1, key="lam2")
    st.slider("Capacidad (cupos)", PARAMETROS["capacidad_min"], PARAMETROS["capacidad_max"], step=2, key="capacidad")
    st.caption("**X3 · Talanquera** — tiempo de atención Gamma(α, β)")
    st.slider("Tiempo medio en la talanquera (s)", 4.0, 60.0, step=1.0, key="tal_media")
    st.slider("Coeficiente de variación de X3", 0.2, 1.0, step=0.05, key="tal_cv",
              help="α = 1 / CV² y β = α / media. Con CV = 1 la Gamma es una exponencial.")
    st.caption("**Salidas** — permanencia Gamma")
    st.toggle("Modelar salidas durante la mañana", key="salidas",
              help="Apagado reproduce el supuesto base de la Entrega 2: nadie sale antes de las 12:00.")
    st.slider("Permanencia media (h)", 2.0, 10.0, step=0.5, key="perm_media", disabled=not st.session_state.salidas)
    st.slider("Coeficiente de variación de la permanencia", 0.1, 0.8, step=0.05, key="perm_cv",
              disabled=not st.session_state.salidas)
    with st.expander("Opciones avanzadas"):
        st.slider("Velocidad dentro del parqueadero (km/h)", 5.0, 20.0, step=1.0, key="vel")
        st.slider("Maniobra de parqueo (s)", 5.0, 40.0, step=1.0, key="maniobra")
        st.select_slider("Réplicas (días simulados)", [100, 200, 500, 1000, 2000], key="replicas")
        st.number_input("Semilla", min_value=1, step=1, key="semilla")
    ejecutar = st.button("Ejecutar simulación", type="primary", width="stretch")
    guardar = st.button("Guardar escenario para comparar", width="stretch")

actual = escenario_actual()
if ejecutar or "params" not in st.session_state:
    st.session_state.params = actual
params = st.session_state.params
with st.spinner("Simulando…"):
    res = correr(params)
esc: Escenario = res["escenario"]
hora_ref = st.session_state.hora_ref


def paquete(r: dict) -> dict:
    """Lo necesario de un resultado para compararlo después."""
    return dict(resumen=sim.resumen(r, st.session_state.hora_ref), horas=r["horas"], ocup=r["ocup_media"],
                fila=r["fila_media"], hora_lleno=r["hora_lleno"], capacidad=r["escenario"].capacidad)


if guardar:
    nombre = params["nombre"]
    if len(st.session_state.guardados) >= 4 and nombre not in st.session_state.guardados:
        st.sidebar.warning("Se comparan máximo 4 escenarios. Borra alguno en la pestaña «Comparar escenarios».")
    else:
        st.session_state.guardados[nombre] = paquete(res)
        st.sidebar.success(f"«{nombre}» guardado.")

# ------------------------------------------------------------------ encabezado e indicadores
st.title("Gemelo digital del parqueadero Almendros")
st.caption("Pontificia Universidad Javeriana Cali · Teoría de Probabilidades · "
           f"Escenario **{esc.nombre}** ({esc.dia}) · {esc.replicas} días simulados de {H0}:00 a {H1}:00")
if sin_nombre(actual) != sin_nombre(params):
    st.info("Cambiaste parámetros. Pulsa **Ejecutar simulación** para actualizar los resultados.", icon="ℹ️")

x4_media = float(res["x4"].mean()) if len(res["x4"]) else 0.0
c = st.columns(5)
c[0].metric(f"P(lleno antes de {hora_texto(hora_ref)})", f"{sim.prob_lleno_antes(res, hora_ref):.0%}")
c[1].metric("Hora esperada de llenado", hora_texto(res["hora_lleno_media"]),
            help=f"Promedio sobre los días en que se llena ({res['prob_llenado']:.0%} de los días).")
c[2].metric("Vehículos desviados", f"{res['desv_media']:.1f}", help="Promedio por mañana.")
c[3].metric("Espera en la entrada", f"{res['espera_media_s']:.1f} s", help="Tiempo medio en fila antes de la talanquera.")
c[4].metric("Fila al llegar, E[X4]", f"{x4_media:.2f}", help="Vehículos delante del que llega, en promedio.")

t3d, tres, tvar, tcomp, tmod = st.tabs(
    ["Gemelo 3D", "Resultados", "Variables aleatorias", "Comparar escenarios", "Modelo y supuestos"])

# ------------------------------------------------------------------ pestaña 3D
with t3d:
    d0 = res["dia0"]
    st.caption(
        f"Animación de **un** día simulado (la primera réplica): {d0['n_llegadas']} llegadas, "
        f"{d0['n_parqueados']} parquean, {d0['n_desviados']} desviados, {d0['n_salidas']} salen antes de las {H1}:00. "
        "Arrastra para girar, rueda para acercar, y usa la línea de tiempo inferior para moverte en la mañana.")
    if hasattr(st, "iframe"):                       # Streamlit reciente
        st.iframe(sim.html_escena(res), height=640)
    else:                                           # versiones anteriores
        components.html(sim.html_escena(res), height=640)

# ------------------------------------------------------------------ pestaña resultados
with tres:
    st.select_slider("Hora de referencia para P(lleno antes de …)", key="hora_ref", format_func=hora_texto,
                     options=[float(v) for v in np.arange(H0 + 1, H1 + 0.01, 0.25)])
    x = a_hora(res["horas"])
    izq, der = st.columns([3, 2])
    with izq:
        fig = lienzo("Ocupación según la hora", "Hora", "Vehículos parqueados", 360, horas=1)
        fig.add_scatter(x=x, y=res["ocup_p95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=x, y=res["ocup_p05"], mode="lines", line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(42,120,214,.18)", name="Entre el 5 % y el 95 % de los días", hoverinfo="skip")
        fig.add_scatter(x=x, y=res["ocup_media"], mode="lines", line=dict(color=AZUL, width=2), name="Media",
                        hovertemplate="%{y:.0f} vehículos<extra>Media</extra>")
        fig.add_hline(y=esc.capacidad, line=dict(color=TENUE, width=1, dash="dash"),
                      annotation_text=f"Capacidad: {esc.capacidad}", annotation_position="top left",
                      annotation_font=dict(color=TENUE, size=11))
        fig.update_yaxes(range=[0, esc.capacidad * 1.12])
        mostrar(fig, "ocup")
    with der:
        llenos = res["hora_lleno"][~np.isnan(res["hora_lleno"])]
        fig = lienzo("Hora de llenado", "Hora en que se ocupa el último cupo", "Días simulados", 360, horas=2, leyenda=False)
        if len(llenos):
            cuenta, bordes = np.histogram(llenos, bins=np.arange(H0, H1 + 0.26, 0.25))
            fig.add_bar(x=a_hora(bordes[:-1] + 0.125), y=cuenta, width=0.25 * 3600 * 1000 * 0.9, marker_color=AZUL,
                        hovertemplate="%{y} días<extra></extra>")
            marca = a_hora(hora_ref).isoformat()
            fig.add_shape(type="line", x0=marca, x1=marca, yref="paper", y0=0, y1=1, line=dict(color=TENUE, width=1, dash="dash"))
            fig.add_annotation(x=marca, yref="paper", y=1, text=hora_texto(hora_ref), showarrow=False, yanchor="bottom",
                               font=dict(color=TENUE, size=11))
        else:
            fig.add_annotation(text="El parqueadero no se llena en ningún día simulado", showarrow=False,
                               xref="paper", yref="paper", x=0.5, y=0.5, font=dict(size=13, color=TENUE))
        mostrar(fig, "lleno")
    a, b, d = st.columns(3)
    with a:
        fig = lienzo("Fila en la entrada (incluye la talanquera)", "Hora", "Vehículos", 310, horas=2)
        fig.add_scatter(x=x, y=res["fila_p95"], mode="lines", line=dict(color=NARANJA, width=1.5, dash="dot"),
                        name="Percentil 95", hovertemplate="%{y:.1f}<extra>Percentil 95</extra>")
        fig.add_scatter(x=x, y=res["fila_media"], mode="lines", line=dict(color=AZUL, width=2), name="Media",
                        hovertemplate="%{y:.2f}<extra>Media</extra>")
        mostrar(fig, "fila")
    with b:
        fig = lienzo("Espera antes de la talanquera", "Hora de llegada", "Segundos (media)", 310, horas=2, leyenda=False)
        fig.add_scatter(x=a_hora(res["horas"][:-1] + 0.125), y=res["espera_int"], mode="lines",
                        line=dict(color=AZUL, width=2), hovertemplate="%{y:.1f} s<extra></extra>")
        mostrar(fig, "espera")
    with d:
        fig = lienzo("Vehículos desviados por mañana", "Vehículos desviados", "Días simulados", 310, leyenda=False)
        desv = res["desviados"]
        paso = max(1, int(np.ceil((desv.max() - desv.min() + 1) / 25)))
        cuenta, bordes = np.histogram(desv, bins=np.arange(desv.min(), desv.max() + paso + 1, paso) - 0.5)
        fig.add_bar(x=bordes[:-1] + paso / 2, y=cuenta, width=paso * 0.9, marker_color=AZUL,
                    hovertemplate="%{y} días<extra></extra>")
        mostrar(fig, "desv")
    reparto = " · ".join(f"{n}: {v:.1f}" for n, v in zip(sim.DESTINOS, res["desv_destino"]))
    st.caption(f"Reparto de los desviados según Iguarán et al. (2019), media por mañana → {reparto}. "
               f"Llegadas: {res['llegadas_media']:.0f} · Salidas antes de las {H1}:00: {res['salidas_media']:.0f} · "
               f"Búsqueda de cupo: {res['busq_media_s']:.0f} s en promedio.")
    with st.expander("Ver los datos de las curvas"):
        tabla = pd.DataFrame({
            "Hora": [hora_texto(h) for h in res["horas"]],
            "Ocupación media": np.round(res["ocup_media"], 1),
            "Ocupación p5": np.round(res["ocup_p05"], 0), "Ocupación p95": np.round(res["ocup_p95"], 0),
            "Fila media": np.round(res["fila_media"], 2), "Fila p95": np.round(res["fila_p95"], 1),
        })
        st.dataframe(tabla, hide_index=True, width="stretch")

# ------------------------------------------------------------------ pestaña variables aleatorias
with tvar:
    st.caption("Cada gráfico compara lo que produce la simulación (barras) con la distribución teórica "
               "declarada en la Entrega 2 (línea). Sirve para verificar que el modelo hace lo que dice.")
    k = st.radio("Franja horaria", range(len(FRANJAS)), format_func=lambda i: FRANJAS[i], horizontal=True)
    lam = esc.lambdas[k]
    tasa_min = lam / 15.0
    rho = esc.rho()[k]
    ini_int = int((PARAMETROS["franjas"][k]["inicio_h"] - H0) * 4)
    fin_int = int((PARAMETROS["franjas"][k]["fin_h"] - H0) * 4)
    x1 = res["x1"][:, ini_int:fin_int].ravel()
    x2 = res["entre"][res["franja"] == k]
    x3 = res["serv_s"]
    x4 = res["x4"][res["franja_x4"] == k]

    def discreta(titulo, eje, muestra, teorica, nombre_teo):
        tope = int(max(np.percentile(muestra, 99.5), 4)) if len(muestra) else 4
        ks = np.arange(0, tope + 1)
        frec = np.bincount(np.minimum(muestra, tope).astype(int), minlength=tope + 1) / max(len(muestra), 1)
        fig = lienzo(titulo, eje, "Probabilidad", 310)
        fig.add_bar(x=ks, y=frec, marker_color=AZUL, name="Simulado", hovertemplate="%{y:.3f}<extra>Simulado</extra>")
        fig.add_scatter(x=ks, y=teorica(ks), mode="lines+markers", line=dict(color=NARANJA, width=2),
                        marker=dict(size=7, line=dict(color="white", width=1.5)), name=nombre_teo,
                        hovertemplate="%{y:.3f}<extra>" + nombre_teo + "</extra>")
        return fig

    def continua(titulo, eje, muestra, densidad, nombre_teo):
        fig = lienzo(titulo, eje, "Densidad", 310)
        if len(muestra):
            tope = float(np.percentile(muestra, 99.5))
            dens, bordes = np.histogram(muestra[muestra <= tope], bins=36, range=(0, tope), density=True)
            ancho = bordes[1] - bordes[0]
            fig.add_bar(x=bordes[:-1] + ancho / 2, y=dens, width=ancho * 0.94, marker_color=AZUL, name="Simulado",
                        hovertemplate="%{y:.3f}<extra>Simulado</extra>")
            xs = np.linspace(tope / 300, tope, 200)
            fig.add_scatter(x=xs, y=densidad(xs), mode="lines", line=dict(color=NARANJA, width=2), name=nombre_teo,
                            hovertemplate="%{y:.3f}<extra>" + nombre_teo + "</extra>")
        fig.update_xaxes(hoverformat=".2f")
        return fig

    g1, g2 = st.columns(2)
    with g1:
        mostrar(discreta("X1 · Llegadas por intervalo de 15 min", "Vehículos en 15 minutos", x1,
                         lambda q: pmf_poisson(q, lam), f"Poisson(λ = {lam:g})"), "x1")
        mostrar(continua("X3 · Tiempo en la talanquera", "Segundos", x3,
                         lambda q: pdf_gamma(q, esc.alfa, esc.beta), f"Gamma(α = {esc.alfa:.2f}, β = {esc.beta:.3f})"), "x3")
    with g2:
        mostrar(continua("X2 · Tiempo entre llegadas", "Minutos", x2,
                         lambda q: tasa_min * np.exp(-tasa_min * q), f"Exponencial(λ = {tasa_min:.3f})"), "x2")
        mostrar(discreta("X4 · Vehículos delante al llegar", "Vehículos en fila o en la talanquera", x4,
                         lambda q: (1 - rho) * rho ** q, f"Geométrica(p = {1 - rho:.3f})"), "x4")

    def fila_tabla(nombre, dist, e_teo, v_teo, muestra):
        return {"Variable": nombre, "Distribución": dist, "E[X] teórico": e_teo, "E[X] simulado": float(np.mean(muestra)) if len(muestra) else np.nan,
                "Var[X] teórica": v_teo, "Var[X] simulada": float(np.var(muestra, ddof=1)) if len(muestra) > 1 else np.nan}

    p = 1 - rho
    momentos = pd.DataFrame([
        fila_tabla("X1 (vehículos / 15 min)", f"Poisson({lam:g})", lam, lam, x1),
        fila_tabla("X2 (min)", f"Exponencial({tasa_min:.3f})", 1 / tasa_min if tasa_min else np.nan, 1 / tasa_min ** 2 if tasa_min else np.nan, x2),
        fila_tabla("X3 (s)", f"Gamma({esc.alfa:.2f}, {esc.beta:.3f})", esc.alfa / esc.beta, esc.alfa / esc.beta ** 2, x3),
        fila_tabla("X4 (vehículos)", f"Geométrica({p:.3f})", (1 - p) / p, (1 - p) / p ** 2, x4),
    ])
    st.dataframe(momentos.round(3), hide_index=True, width="stretch")
    st.caption(f"Utilización de la talanquera en esta franja: ρ = λ · E[X3] = {rho:.3f}. "
               "La geométrica de X4 es exacta con servicio exponencial (CV = 1); con servicio Gamma es una aproximación, "
               "aunque P(X4 = 0) = 1 − ρ se cumple en ambos casos.")

# ------------------------------------------------------------------ pestaña comparar
SUGERIDOS = [
    dict(nombre="Base"),
    dict(nombre="30 cupos más", capacidad=PARAMETROS["capacidad"] + 30),
    dict(nombre="Demanda +20 %", lambdas=[round(v * 1.2, 1) for v in base.lambdas]),
    dict(nombre="Talanquera lenta (45 s)", tal_media_s=45.0),
]
with tcomp:
    b1, b2, _ = st.columns([3, 3, 4])
    if b1.button("Cargar comparación sugerida", help="Simula cuatro escenarios de ejemplo a partir del caso base."):
        st.session_state.guardados = {}
        for s in SUGERIDOS:
            p_s = {**Escenario().como_dict(), **s, "replicas": params["replicas"], "semilla": params["semilla"]}
            st.session_state.guardados[s["nombre"]] = paquete(correr(p_s))
    if b2.button("Borrar escenarios guardados"):
        st.session_state.guardados = {}
    guardados = st.session_state.guardados
    if not guardados:
        st.info("Aún no hay escenarios guardados. Cambia parámetros, ejecuta la simulación y pulsa "
                "**Guardar escenario para comparar**, o carga la comparación sugerida.")
    else:
        filas = {}
        for nombre, g in guardados.items():
            r = dict(g["resumen"])
            r["Hora esperada de llenado"] = hora_texto(r["Hora esperada de llenado"])
            filas[nombre] = {q: (v if isinstance(v, str) else (f"{v:.0%}" if q.startswith("P(") else f"{v:.2f}" if "X4" in q else f"{v:.1f}"))
                             for q, v in r.items()}
            filas[nombre] = {"Capacidad": str(g["capacidad"]), **filas[nombre]}
        st.dataframe(pd.DataFrame(filas), width="stretch")
        izq, der = st.columns(2)
        with izq:
            fig = lienzo("Ocupación media según la hora", "Hora", "Vehículos parqueados", 400, horas=1)
            for j, (nombre, g) in enumerate(guardados.items()):
                fig.add_scatter(x=a_hora(g["horas"]), y=g["ocup"], mode="lines", name=nombre,
                                line=dict(color=SERIES[j % 4], width=2),
                                hovertemplate="%{y:.0f}<extra>" + nombre + "</extra>")
            fig.update_layout(LEYENDA_ABAJO)
            mostrar(fig, "cmp_ocup")
        with der:
            fig = lienzo("Probabilidad de estar lleno antes de cada hora", "Hora", "Probabilidad", 400, horas=1)
            hs = np.arange(H0, H1 + 0.01, 0.25)
            for j, (nombre, g) in enumerate(guardados.items()):
                pr = [float(np.mean(g["hora_lleno"] <= h)) for h in hs]
                fig.add_scatter(x=a_hora(hs), y=pr, mode="lines", name=nombre, line=dict(color=SERIES[j % 4], width=2),
                                hovertemplate="%{y:.0%}<extra>" + nombre + "</extra>")
            fig.update_yaxes(tickformat=".0%", range=[0, 1.05])
            fig.update_layout(LEYENDA_ABAJO)
            mostrar(fig, "cmp_prob")

# ------------------------------------------------------------------ pestaña modelo
with tmod:
    rhos = esc.rho()
    st.markdown(f"""
#### Variables aleatorias del escenario actual

| Variable | Qué representa | Distribución | Parámetros en uso |
|---|---|---|---|
| **X1** | Vehículos que llegan en 15 minutos (discreta) | Poisson(λₖ) | λ₁ = {esc.lambdas[0]:g}, λ₂ = {esc.lambdas[1]:g}, λ₃ = {esc.lambdas[2]:g} |
| **X2** | Minutos entre dos llegadas consecutivas (continua) | Exponencial(λₖ / 15) | {esc.lambdas[0] / 15:.3f}, {esc.lambdas[1] / 15:.3f} y {esc.lambdas[2] / 15:.3f} por minuto |
| **X3** | Segundos en la talanquera (continua) | Gamma(α, β) | α = {esc.alfa:.2f}, β = {esc.beta:.3f} (media {esc.tal_media_s:g} s, CV {esc.tal_cv:g}) |
| **X4** | Vehículos delante al llegar (discreta) | Geométrica(p = 1 − ρ) | ρ = {rhos[0]:.3f}, {rhos[1]:.3f} y {rhos[2]:.3f} por franja |
| Permanencia | Horas que el vehículo ocupa el cupo (continua) | Gamma | media {esc.perm_media_h:g} h, CV {esc.perm_cv:g} ({'activa' if esc.salidas else 'apagada: nadie sale'}) |

#### Cómo funciona la simulación
1. Se generan las llegadas del día con tiempos entre llegadas exponenciales, usando la λ de cada franja.
2. Cada vehículo espera si la talanquera está ocupada (una sola, en orden de llegada) y es atendido un tiempo Gamma.
3. Al subir la barrera, si hay cupo toma el **cupo libre más cercano** a la entrada; si no, queda **desviado**.
4. Si las salidas están activas, permanece un tiempo Gamma y libera el cupo.
5. El día se repite {esc.replicas} veces y se resumen los indicadores.

#### Supuestos
- Las llegadas son independientes entre sí y el parqueadero empieza vacío a las {H0}:00.
- Los valores de λ son los **preliminares de la Entrega 2**, derivados de la distribución de horas de llegada de Varela et al. (2023) y de la capacidad de 230 cupos. El selector de día los multiplica por el peso de ese día en la Tabla 1 del mismo estudio.
- **No hubo medición en campo.** El tiempo en la talanquera (media 12 s) es un supuesto ajustable. La permanencia usa una Gamma con la misma media (7 h) y desviación (2,9 h) que la Uniforme(2 h, 12 h) de Iguarán et al. (2019); con esos valores el modelo reproduce la congestión de 8:30 a 9:30 que reporta Varela et al. (2023).
- El reparto de los desviados (Gualanday 78 %, Central 22 %) sale de la Tabla 2 de Iguarán et al. (2019), columna «No hay en CDL», que es el parqueadero con acceso por la Calle 17a en ese estudio. Ceibas no existía entonces y queda en 0 %.
- El plano 3D se trazó sobre la vista satelital: el contorno, las islas con bordillo en sierra, el laboratorio y la portería de la Calle 17a están medidos en la imagen. La posición de cada cupo es estimada, porque el piso es grava sin demarcación, y se ajustó para sumar 230. Los cupos 231 a 276 son una zona de ampliación hipotética al occidente.

#### Fuentes
- Varela, C., Solarte, L. y Suárez, S. (2023). *El aumento de la demanda en los parqueaderos de la Universidad Javeriana de Cali*. RPubs. https://rpubs.com/lsolarte/1041166
- Iguarán, J., López, M., Muñoz, C. y Sarmiento, G. (2019). *Análisis del nivel de utilización de los parqueaderos en la Universidad Javeriana Cali*. Scribd. https://es.scribd.com/document/438890279/SIMULACION-DE-PARQUEADEROS
- González, D. (2026). *Guía del proyecto: gemelo digital de un sistema universitario*. https://dgonxalex80.github.io/curso013/guia_proyecto1.html
""")
