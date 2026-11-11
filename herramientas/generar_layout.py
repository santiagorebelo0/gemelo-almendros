"""Genera compartido/layout.json: el plano del parqueadero Almendros.

El plano se trazo sobre la vista satelital de Google Maps (3.34523, -76.53189) con el
contorno marcado por el grupo. Las coordenadas de la imagen (pixeles) se convierten a
metros con la barra de escala de la captura (98,75 px = 20 m).

Sistema de coordenadas (metros): origen en la porteria sobre la Calle 17a,
x hacia el oriente y z hacia el sur. El norte queda en -z.

Lo que es medido y lo que es estimado:
- Medido en la imagen: contorno, posicion de las cinco islas con bordillo en sierra,
  edificio del Laboratorio Central de Mezclas, porteria y calle.
- Estimado: la posicion de cada cupo. No hay demarcacion en el piso (es grava), asi que
  los cupos se repartieron a lo largo de las islas y los bordes hasta sumar los 230 que
  reporta Varela et al. (2023). Los cupos 231 a 276 son una zona de ampliacion hipotetica.

Volver a generar:  python herramientas/generar_layout.py
"""
import json
import math
from pathlib import Path

PX_POR_M = 98.75 / 20.0
OX, OY = 960.0, 543.0          # pixel de la porteria


def m(px, py):
    return [round((px - OX) / PX_POR_M, 2), round((py - OY) / PX_POR_M, 2)]


# Contorno del area de parqueo (pixeles de la captura), en sentido horario desde el noroccidente.
CONTORNO_PX = [
    (704, 100), (800, 100), (800, 146), (818, 158), (916, 158), (916, 353), (923, 387), (923, 470),
    (940, 500), (960, 520), (960, 566), (830, 556), (826, 498), (726, 498), (718, 572), (748, 610),
    (824, 610), (844, 652), (860, 740), (866, 800), (808, 822), (656, 822), (622, 776), (616, 702),
    (738, 700), (740, 684), (720, 668), (596, 668), (572, 678), (480, 678), (480, 644), (520, 630),
    (572, 652), (632, 652), (656, 628), (676, 520), (676, 215), (690, 125),
]
CONTORNO = [m(*p) for p in CONTORNO_PX]

# ---------------------------------------------------------------- circulacion
SP = -17.0                      # eje del carril oriental (norte-sur), junto al seto
WC = -49.5                      # eje del conector occidental (norte-sur)
Z_ISLAS = [-75.5, -62.0, -48.5, -35.0, -21.5]            # ejes de las islas con bordillo en sierra
Z_CARRIL = {k: (Z_ISLAS[k - 1] + Z_ISLAS[k]) / 2 for k in range(1, 5)}   # carriles entre islas
Z_A5 = -13.5                    # carril frente al laboratorio
Z_A0 = -82.6                    # carril del bloque norte

PARE = [-1.4, -2.2]             # donde se detiene el vehiculo ante la talanquera
ENTRA = [[-9.0, -2.4], [-15.0, -7.5]]
COLA_SALIDA = [[-13.0, 0.5], [-9.0, 2.2], [2.0, 2.2], [6.2, 7.5], [6.2, 330.0]]
POR_A5 = [[WC, Z_A5], [-19.0, Z_A5]] + COLA_SALIDA
PASO_OCC = ENTRA + [[-19.0, Z_A5], [-54.0, Z_A5]]         # hacia el pasaje al occidente del laboratorio
SALE_SUR = [[-54.0, Z_A5], [-19.0, Z_A5]] + COLA_SALIDA

troncos = {}


def tronco(nombre, entra, ini, fin, tipo, sale):
    d = math.hypot(fin[0] - ini[0], fin[1] - ini[1])
    troncos[nombre] = {"entra": entra, "ini": ini, "fin": fin, "tipo": tipo, "sale": sale,
                       "dir": [round((fin[0] - ini[0]) / d, 4), round((fin[1] - ini[1]) / d, 4)]}


for k, z in Z_CARRIL.items():   # carriles de un solo sentido, de oriente a occidente
    tronco(f"A{k}", ENTRA + [[SP, -12.0]], [SP, z], [WC, z], "sigue", POR_A5)
A1 = troncos["A1"]["entra"] + [[SP, Z_CARRIL[1]]]
tronco("ESTE", ENTRA, [SP, -11.0], [SP, -80.0], "vuelve", COLA_SALIDA)
tronco("OESTE", A1, [WC, Z_CARRIL[1]], [WC, Z_A5], "sigue", [[-19.0, Z_A5]] + COLA_SALIDA)
tronco("A5", ENTRA, [-19.0, Z_A5], [-47.0, Z_A5], "vuelve", COLA_SALIDA)
tronco("A0", A1 + [[WC, Z_CARRIL[1]]], [WC, Z_A0], [-32.0, Z_A0], "vuelve", POR_A5)
tronco("SO", PASO_OCC, [-54.0, 13.0], [-54.0, 26.0], "vuelve", SALE_SUR)
S1 = PASO_OCC + [[-54.0, 20.5]]
tronco("S1", PASO_OCC, [-54.0, 20.5], [-28.0, 20.5], "vuelve", SALE_SUR)
SALE_LAZO = [[-28.0, 20.5], [-54.0, 20.5]] + SALE_SUR
tronco("S2", S1 + [[-28.0, 20.5]], [-28.0, 34.3], [-63.0, 34.3], "vuelve", SALE_LAZO)
tronco("LE", S1 + [[-28.0, 20.5]], [-28.0, 35.5], [-28.0, 54.7], "vuelve", SALE_LAZO)
tronco("S3", S1 + [[-28.0, 20.5]], [-28.0, 54.7], [-63.0, 54.7], "vuelve", SALE_LAZO)
tronco("LO", S1 + [[-28.0, 20.5], [-28.0, 34.3]], [-63.0, 34.3], [-63.0, 54.7], "vuelve",
       [[-28.0, 34.3]] + SALE_LAZO)
tronco("FR", PASO_OCC + [[-54.0, 20.0]], [-62.0, 25.3], [-96.0, 25.3], "vuelve", [[-54.0, 20.0]] + SALE_SUR)
Z_EX = -80.2
tronco("EX", A1 + [[WC, Z_CARRIL[1]], [WC, Z_EX]], [-67.5, Z_EX], [-67.5, -22.0], "vuelve",
       [[WC, Z_EX]] + POR_A5)

# ---------------------------------------------------------------- filas de cupos
cupos = []


def fila(nombre, tr, p0, p1, n, rumbo, zona="real"):
    """n cupos repartidos entre p0 y p1; `rumbo` es hacia donde queda la trompa del vehiculo."""
    t = troncos[tr]
    norma = math.hypot(*rumbo)
    hx, hz = rumbo[0] / norma, rumbo[1] / norma
    dx, dz = t["dir"]
    for k in range(n):
        u = (k + 0.5) / n
        x, z = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
        # punto del carril desde el que el vehiculo gira hacia el cupo
        cruz = hx * dz - hz * dx
        s = ((x - t["ini"][0]) * dz - (z - t["ini"][1]) * dx) / cruz
        ax, az = x - hx * s, z - hz * s
        ruta = [PARE] + t["entra"] + [t["ini"], [ax, az], [x, z]]
        dist = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(ruta, ruta[1:]))
        cupos.append({"fila": nombre, "tronco": tr, "zona": zona, "x": round(x, 2), "z": round(z, 2),
                      "hx": round(hx, 4), "hz": round(hz, 4), "ax": round(ax, 2), "az": round(az, 2),
                      "dist": round(dist, 1)})


S60, C60 = math.sin(math.radians(60)), math.cos(math.radians(60))
X0_ISLA, X1_ISLA = -46.5, -19.6
for k, z in Z_CARRIL.items():   # parqueo en espina de pescado a ambos lados de cada carril
    fila(f"I{k}s", f"A{k}", [X0_ISLA, z - 4.25], [X1_ISLA, z - 4.25], 11, (-C60, -S60))
    fila(f"I{k + 1}n", f"A{k}", [X0_ISLA, z + 4.25], [X1_ISLA, z + 4.25], 11, (-C60, S60))
fila("I5s", "A5", [X0_ISLA, -19.0], [X1_ISLA, -19.0], 11, (0, -1))
fila("I1n", "A0", [-46.2, -78.0], [-32.4, -78.0], 6, (0, 1))
fila("Norte", "A0", [-51.0, -87.2], [-32.6, -87.2], 8, (0, -1))
fila("Seto oriental", "ESTE", [-11.8, -77.5], [-11.8, -11.0], 28, (1, 0))
fila("Borde occidental", "OESTE", [-54.5, -67.0], [-54.5, -19.0], 20, (-1, 0))
fila("Muro sur", "S1", [-47.2, 16.1], [-28.8, 16.1], 8, (0, -1))
fila("Isla sur n", "S1", [-45.0, 24.9], [-31.0, 24.9], 6, (0, 1))
fila("Isla sur s", "S2", [-45.0, 29.9], [-31.0, 29.9], 6, (0, -1))
fila("Lazo norte", "S2", [-60.5, 38.7], [-32.5, 38.7], 12, (0, 1))
fila("Lazo sur", "S3", [-60.5, 50.3], [-32.5, 50.3], 12, (0, -1))
fila("Lazo oriente", "LE", [-23.3, 36.8], [-23.3, 53.6], 7, (1, 0))
fila("Lazo occidente", "LO", [-67.4, 36.8], [-67.4, 53.6], 7, (-1, 0))
fila("Suroccidente", "SO", [-59.0, 14.6], [-59.0, 24.4], 4, (-1, 0))
fila("Franja occidental", "FR", [-95.0, 21.0], [-79.0, 21.0], 7, (0, -1))
N_REAL = len(cupos)
assert N_REAL == 230, N_REAL
fila("Ampliacion e", "EX", [-62.0, -77.5], [-62.0, -22.5], 23, (1, 0), zona="ampliacion")
fila("Ampliacion o", "EX", [-73.0, -77.5], [-73.0, -22.5], 23, (-1, 0), zona="ampliacion")

# Orden de existencia: con capacidad C existen los cupos 0..C-1. Primero los reales, del mas
# cercano al mas lejano (al reducir la capacidad se cierran los mas lejanos); luego la ampliacion.
cupos.sort(key=lambda c: (c["zona"] != "real", c["dist"]))
for k, c in enumerate(cupos):
    c["id"] = k

layout = {
    "px_por_m": PX_POR_M,
    "n_reales": N_REAL,
    "contorno": CONTORNO,
    "ampliacion": [[-76.5, -84.0], [-57.0, -84.0], [-57.0, -20.0], [-76.5, -20.0]],
    "islas": [{"x0": X0_ISLA - 0.3, "x1": X1_ISLA + 0.3, "z": z} for z in Z_ISLAS]
             + [{"x0": -45.3, "x1": -30.7, "z": 27.4}],
    "isla_lazo": {"x0": -61.0, "x1": -32.0, "z0": 41.3, "z1": 47.7},
    "pare": PARE,
    "talanquera_x": -4.0,
    "calle_x": 8.0,
    "carril_llegada_x": 6.2,
    "cola_salida": COLA_SALIDA,
    "troncos": troncos,
    "cupos": cupos,
}

destino = Path(__file__).resolve().parent.parent / "compartido" / "layout.json"
destino.write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8")
dist = [c["dist"] for c in cupos[:N_REAL]]
print(f"{N_REAL} cupos reales + {len(cupos) - N_REAL} de ampliacion -> {destino}")
print("distancia desde la talanquera (m): min", min(dist), " media", round(sum(dist) / len(dist), 1), " max", max(dist))
