"""Motor de simulacion del gemelo digital del parqueadero Almendros (version Python).

Implementa el esquema de la Entrega 2:
  X1  llegadas por intervalo de 15 min      ~ Poisson(lambda_k), una lambda por franja
  X2  tiempo entre llegadas (min)           ~ Exponencial(lambda_k / 15)
  X3  tiempo en la talanquera (s)           ~ Gamma(alfa, beta)
  X4  vehiculos delante al llegar           ~ Geometrica(p = 1 - rho), rho = lambda * E[X3]
y las extensiones acordadas para la Entrega 3:
  - perfil por dia de la semana (Tabla 1 de Varela et al., 2023)
  - permanencia ~ Gamma: cada vehiculo libera su cupo al salir
  - busqueda de cupo: el vehiculo toma el cupo libre mas cercano a la talanquera
  - reparto de los desviados entre Gualanday, Central y Ceibas

El archivo R/simulacion.R contiene exactamente el mismo modelo en R.
Unidad de tiempo interna: minutos desde la hora de inicio.
"""
from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent
PARAMETROS = json.loads((RAIZ / "compartido" / "parametros.json").read_text(encoding="utf-8"))
LAYOUT = json.loads((RAIZ / "compartido" / "layout.json").read_text(encoding="utf-8"))
DIST_CUPOS = np.array([c["dist"] for c in LAYOUT["cupos"]], dtype=float)  # con capacidad C existen los C primeros
DESTINOS = list(PARAMETROS["desvio"].keys())
PASO_REJILLA = 15.0  # min


def factores_por_dia() -> dict[str, list[float]]:
    """Factor multiplicativo de lambda por dia y franja a partir de la Tabla 1."""
    t = PARAMETROS["tabla1_varela"]
    filas = [np.array(t["5y7"], float), np.array(t["8y10"], float), np.array(t["11y1"], float)]
    factores = {"Promedio": [1.0, 1.0, 1.0]}
    for j, dia in enumerate(t["dias"]):
        factores[dia] = [float(f[j] / f.mean()) for f in filas]
    return factores


def lambdas_del_dia(dia: str) -> list[float]:
    f = factores_por_dia()[dia]
    return [round(fr["lambda15"] * f[k], 1) for k, fr in enumerate(PARAMETROS["franjas"])]


@dataclass
class Escenario:
    nombre: str = "Base"
    dia: str = "Promedio"
    lambdas: list[float] = field(default_factory=lambda: [fr["lambda15"] for fr in PARAMETROS["franjas"]])
    capacidad: int = PARAMETROS["capacidad"]
    tal_media_s: float = PARAMETROS["talanquera"]["media_s"]
    tal_cv: float = PARAMETROS["talanquera"]["cv"]
    salidas: bool = PARAMETROS["permanencia"]["activa"]
    perm_media_h: float = PARAMETROS["permanencia"]["media_h"]
    perm_cv: float = PARAMETROS["permanencia"]["cv"]
    vel_kmh: float = PARAMETROS["busqueda"]["velocidad_kmh"]
    maniobra_s: float = PARAMETROS["busqueda"]["maniobra_s"]
    replicas: int = PARAMETROS["replicas"]
    semilla: int = PARAMETROS["semilla"]

    # --- parametros derivados -------------------------------------------------
    @property
    def alfa(self) -> float:          # forma de X3
        return 1.0 / self.tal_cv ** 2

    @property
    def beta(self) -> float:          # tasa de X3 (1/s)
        return self.alfa / self.tal_media_s

    def rho(self) -> list[float]:     # utilizacion de la talanquera por franja
        return [lam / 15.0 / 60.0 * self.tal_media_s for lam in self.lambdas]

    def como_dict(self) -> dict:
        return asdict(self)


def _franjas_min():
    h0 = PARAMETROS["horario"]["inicio_h"]
    return [((fr["inicio_h"] - h0) * 60.0, (fr["fin_h"] - h0) * 60.0) for fr in PARAMETROS["franjas"]]


def horizonte_min() -> float:
    return (PARAMETROS["horario"]["fin_h"] - PARAMETROS["horario"]["inicio_h"]) * 60.0


def rejilla_horas() -> np.ndarray:
    h0 = PARAMETROS["horario"]["inicio_h"]
    return h0 + np.arange(0, horizonte_min() + 1e-9, PASO_REJILLA) / 60.0


def _generar_llegadas(esc: Escenario, rng: np.random.Generator):
    """Tiempos de llegada con tiempos entre llegadas exponenciales (X2), franja por franja.

    Al cambiar de franja el reloj se reinicia en el limite: por la falta de memoria de
    la exponencial esto equivale a un proceso de Poisson con tasa lambda_k en cada franja.
    """
    tiempos, entre, franja = [], [], []
    for k, (ini, fin) in enumerate(_franjas_min()):
        tasa = esc.lambdas[k] / 15.0  # vehiculos por minuto
        if tasa <= 0:
            continue
        dur = fin - ini
        n_max = int(tasa * dur + 8 * np.sqrt(tasa * dur) + 30)
        gaps = rng.exponential(1.0 / tasa, n_max)
        t = np.cumsum(gaps)
        dentro = t < dur
        tiempos.append(ini + t[dentro])
        entre.append(gaps[dentro])
        franja.append(np.full(int(dentro.sum()), k))
    if not tiempos:
        return np.array([]), np.array([]), np.array([], dtype=int)
    return np.concatenate(tiempos), np.concatenate(entre), np.concatenate(franja)


def simular_dia(esc: Escenario, rng: np.random.Generator, detalle: bool = False) -> dict:
    H = horizonte_min()
    rejilla = np.arange(0, H + 1e-9, PASO_REJILLA)
    C = int(esc.capacidad)
    orden = np.argsort(DIST_CUPOS[:C], kind="stable")   # rango de cercania -> id del cupo
    dist = DIST_CUPOS[:C][orden]

    lleg, entre, franja = _generar_llegadas(esc, rng)
    n = len(lleg)

    # X3: tiempo en la talanquera (s) -> minutos
    serv_s = rng.gamma(esc.alfa, 1.0 / esc.beta, n)
    serv = serv_s / 60.0
    # Una talanquera, orden de llegada: fin_i = max(lleg_i, fin_{i-1}) + serv_i
    acum = np.cumsum(serv)
    fin = acum + np.maximum.accumulate(lleg - (acum - serv)) if n else np.array([])
    ini = fin - serv
    espera_s = (ini - lleg) * 60.0
    # X4: vehiculos en el sistema de la talanquera delante del que llega
    x4 = np.arange(n) - np.searchsorted(fin, lleg, side="right")

    # Permanencia (h) ~ Gamma
    if esc.salidas:
        forma_p = 1.0 / esc.perm_cv ** 2
        perm = rng.gamma(forma_p, esc.perm_media_h / forma_p, n) * 60.0
    else:
        perm = np.full(n, np.inf)
    destinos = rng.choice(len(DESTINOS), size=n, p=list(PARAMETROS["desvio"].values()))

    vel = esc.vel_kmh * 1000.0 / 60.0  # m por minuto
    libres = list(range(C))            # monticulo de rangos: el menor es el cupo mas cercano
    salidas_pend: list[tuple[float, int]] = []
    cupo = np.full(n, -1)
    t_parq = np.full(n, np.nan)
    t_sal = np.full(n, np.nan)
    ocup = 0
    t_lleno = np.nan
    for i in range(n):
        t = fin[i]
        while salidas_pend and salidas_pend[0][0] <= t:
            _, c = heapq.heappop(salidas_pend)
            heapq.heappush(libres, c)
            ocup -= 1
        if ocup < C:
            c = heapq.heappop(libres)
            cupo[i] = orden[c]
            ocup += 1
            t_parq[i] = t + dist[c] / vel + esc.maniobra_s / 60.0
            s = t_parq[i] + perm[i]
            if s < H:
                t_sal[i] = s
                heapq.heappush(salidas_pend, (s, c))
            if ocup == C and np.isnan(t_lleno):
                t_lleno = t
        # si no hay cupo, el vehiculo queda desviado (cupo = -1)

    parq = cupo >= 0
    t_ent = np.sort(fin[parq])
    t_out = np.sort(t_sal[~np.isnan(t_sal)])
    ocup_rej = np.searchsorted(t_ent, rejilla, side="right") - np.searchsorted(t_out, rejilla, side="right")
    fila_rej = np.searchsorted(lleg, rejilla, side="right") - np.searchsorted(fin, rejilla, side="right")
    interv = np.minimum((lleg // PASO_REJILLA).astype(int), len(rejilla) - 2) if n else np.array([], int)
    n_int = len(rejilla) - 1
    x1 = np.bincount(interv, minlength=n_int)
    espera_int = np.bincount(interv, weights=espera_s, minlength=n_int) / np.maximum(x1, 1)
    busq_s = (t_parq[parq] - fin[parq]) * 60.0
    desv = ~parq

    dia = {
        "n_llegadas": n,
        "n_parqueados": int(parq.sum()),
        "n_desviados": int(desv.sum()),
        "n_salidas": int((~np.isnan(t_sal)).sum()),
        "t_lleno": t_lleno,
        "ocup_rej": ocup_rej,
        "fila_rej": fila_rej,
        "x1": x1,
        "espera_int": espera_int,
        "espera_media_s": float(espera_s.mean()) if n else 0.0,
        "espera_max_s": float(espera_s.max()) if n else 0.0,
        "busq_media_s": float(busq_s.mean()) if parq.any() else 0.0,
        "ocup_max": int(ocup_rej.max()),
        "entre": entre, "franja": franja, "serv_s": serv_s, "x4": x4,
        "desv_destino": np.bincount(destinos[desv], minlength=len(DESTINOS)),
    }
    if detalle:
        dia["autos"] = {
            "lleg": np.round(lleg * 60, 1).tolist(),      # segundos desde el inicio
            "ini": np.round(ini * 60, 1).tolist(),
            "fin": np.round(fin * 60, 1).tolist(),
            "cupo": cupo.tolist(),
            "parq": [None if np.isnan(v) else round(v * 60, 1) for v in t_parq],
            "sal": [None if np.isnan(v) else round(v * 60, 1) for v in t_sal],
            "dest": destinos.tolist(),
        }
    return dia


def simular(esc: Escenario) -> dict:
    """Repite el dia completo `replicas` veces y resume los indicadores."""
    rng = np.random.default_rng(esc.semilla)
    dias = [simular_dia(esc, rng, detalle=(r == 0)) for r in range(esc.replicas)]
    h0 = PARAMETROS["horario"]["inicio_h"]

    ocup = np.array([d["ocup_rej"] for d in dias], float)
    fila = np.array([d["fila_rej"] for d in dias], float)
    x1 = np.array([d["x1"] for d in dias])
    espera_int = np.array([d["espera_int"] for d in dias])
    t_lleno = np.array([d["t_lleno"] for d in dias], float)
    hora_lleno = h0 + t_lleno / 60.0
    desv = np.array([d["n_desviados"] for d in dias])

    # Muestras de las variables aleatorias (se limita el tamano para graficar)
    tope = 60
    entre = np.concatenate([d["entre"] for d in dias[:tope]])
    franja = np.concatenate([d["franja"] for d in dias[:tope]])
    serv = np.concatenate([d["serv_s"] for d in dias[:tope]])
    x4 = np.concatenate([d["x4"] for d in dias])
    franja_x4 = np.concatenate([d["franja"] for d in dias])

    return {
        "escenario": esc,
        "horas": rejilla_horas(),
        "ocup_media": ocup.mean(0), "ocup_p05": np.percentile(ocup, 5, 0), "ocup_p95": np.percentile(ocup, 95, 0),
        "fila_media": fila.mean(0), "fila_p95": np.percentile(fila, 95, 0),
        "espera_int": espera_int.mean(0),
        "hora_lleno": hora_lleno,
        "prob_llenado": float(np.mean(~np.isnan(hora_lleno))),
        "hora_lleno_media": float(np.nanmean(hora_lleno)) if np.any(~np.isnan(hora_lleno)) else float("nan"),
        "desviados": desv,
        "desv_media": float(desv.mean()),
        "desv_destino": np.mean([d["desv_destino"] for d in dias], 0),
        "llegadas_media": float(np.mean([d["n_llegadas"] for d in dias])),
        "salidas_media": float(np.mean([d["n_salidas"] for d in dias])),
        "espera_media_s": float(np.mean([d["espera_media_s"] for d in dias])),
        "espera_max_s": float(np.mean([d["espera_max_s"] for d in dias])),
        "busq_media_s": float(np.mean([d["busq_media_s"] for d in dias])),
        "ocup_max_media": float(np.mean([d["ocup_max"] for d in dias])),
        "x1": x1, "entre": entre, "franja": franja, "serv_s": serv, "x4": x4, "franja_x4": franja_x4,
        "dia0": dias[0],
    }


def prob_lleno_antes(res: dict, hora: float) -> float:
    """P(el parqueadero se llena antes de `hora`)."""
    return float(np.mean(res["hora_lleno"] <= hora))  # NaN cuenta como False


def hora_texto(h: float) -> str:
    if h is None or np.isnan(h):
        return "No se llena"
    m = int(round(h * 60))
    return f"{m // 60}:{m % 60:02d}"


def resumen(res: dict, hora_ref: float) -> dict:
    """Indicadores principales de un escenario (para tarjetas y comparacion)."""
    return {
        "P(lleno antes de %s)" % hora_texto(hora_ref): prob_lleno_antes(res, hora_ref),
        "P(se llena en la mañana)": res["prob_llenado"],
        "Hora esperada de llenado": res["hora_lleno_media"],
        "Vehículos desviados (media)": res["desv_media"],
        "Ocupación máxima (media)": res["ocup_max_media"],
        "Espera en la entrada (s)": res["espera_media_s"],
        "Fila al llegar, E[X4]": float(res["x4"].mean()) if len(res["x4"]) else 0.0,
        "Búsqueda de cupo (s)": res["busq_media_s"],
        "Llegadas (media)": res["llegadas_media"],
        "Salidas (media)": res["salidas_media"],
    }


def datos_escena(res: dict) -> dict:
    """Paquete que consume compartido/escena3d.html para animar un dia simulado."""
    esc: Escenario = res["escenario"]
    return {
        "layout": LAYOUT,
        "capacidad": int(esc.capacidad),
        "hora_inicio": PARAMETROS["horario"]["inicio_h"],
        "horizonte_s": horizonte_min() * 60,
        "vel_ms": esc.vel_kmh / 3.6,
        "destinos": DESTINOS,
        "autos": res["dia0"]["autos"],
        "titulo": f"{esc.nombre} · {esc.dia}",
    }


def html_escena(res: dict) -> str:
    plantilla = (RAIZ / "compartido" / "escena3d.html").read_text(encoding="utf-8")
    return plantilla.replace("/*__DATOS__*/null", json.dumps(datos_escena(res), ensure_ascii=False))


if __name__ == "__main__":
    import time
    for nombre, kw in [("Sin salidas (supuesto Entrega 2)", dict(salidas=False)), ("Con permanencia Gamma", dict())]:
        e = Escenario(nombre=nombre, **kw)
        t0 = time.time()
        r = simular(e)
        print(f"\n== {nombre} ({time.time() - t0:.2f} s, {e.replicas} replicas)")
        for k, v in resumen(r, 9.0).items():
            print(f"  {k:32s} {hora_texto(v) if 'Hora' in k else round(v, 3)}")
        print("  rho por franja:", [round(x, 3) for x in e.rho()], " P(X4=0) sim:", round(float(np.mean(r['x4'] == 0)), 3))
        print("  X1 media/var franja 1:", round(r["x1"][:, :12].mean(), 2), round(r["x1"][:, :12].var(), 2))
        print("  ocupacion media por hora:", [int(v) for v in r["ocup_media"][::4]])
