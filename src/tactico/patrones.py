"""
PATRONES DE GRÁFICO CON DETECCIÓN ALGORÍTMICA
---------------------------------------------
Lo, Mamaysky y Wang (2000), "Foundations of Technical Analysis", Journal of
Finance 55(4). Ficha: research/fichas/patrones_graficos.md.

En cada vela t (sin mirar al futuro):
  1. Se toma la ventana de las últimas `ventana` velas (38 = l 35 + d 3).
  2. Se suaviza el cierre con una regresión kernel gaussiana (Nadaraya-Watson)
     ajustada SOLO con la ventana. Ancho de banda = 0,3 × el de validación
     cruzada (dejando uno fuera), como en el paper.
  3. Extremo local = cambio de signo de la pendiente del precio suavizado; su
     precio es el cierre real máximo/mínimo en ±1 vela.
  4. Se buscan los patrones sobre los extremos, y solo cuentan si el último
     extremo está entre las velas t−d y t (confirmado con d velas de retraso).

Como el eje x de cada ventana es siempre 0..ventana−1, las matrices del kernel
son las mismas para todas las ventanas: el cálculo se hace de golpe con
álgebra matricial (rápido) y es idéntico a hacerlo ventana a ventana.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

REJILLA_H = np.round(np.arange(0.5, 20.01, 0.25), 4)   # anchos de banda candidatos (en velas)


def _pesos(n: int, h: float) -> np.ndarray:
    x = np.arange(n)
    return np.exp(-0.5 * ((x[:, None] - x[None, :]) / h) ** 2)


def _matriz_suavizado(n: int, h: float, dejar_uno_fuera: bool = False) -> np.ndarray:
    w = _pesos(n, h)
    if dejar_uno_fuera:
        np.fill_diagonal(w, 0.0)
    return w / w.sum(axis=1, keepdims=True)


def suavizar_ventanas(cierres: np.ndarray, ventana: int, factor: float = 0.3) -> np.ndarray:
    """Devuelve una matriz (velas × ventana): fila t = precio suavizado de la
    ventana que TERMINA en t (filas NaN mientras no hay `ventana` velas)."""
    T = len(cierres)
    out = np.full((T, ventana), np.nan)
    if T < ventana:
        return out
    Y = sliding_window_view(cierres.astype(float), ventana)            # (T−ventana+1) × ventana
    # Validación cruzada dejando uno fuera: error de cada ancho de banda en cada ventana
    errores = np.stack([((Y - Y @ _matriz_suavizado(ventana, h, True).T) ** 2).sum(axis=1) for h in REJILLA_H])
    h_cv = REJILLA_H[np.argmin(errores, axis=0)]
    h_final = np.maximum(factor * h_cv, 0.1)
    suave = np.empty_like(Y)
    for h in np.unique(h_final):
        filas = h_final == h
        suave[filas] = Y[filas] @ _matriz_suavizado(ventana, float(h)).T
    out[ventana - 1:] = suave
    return out


def extremos(suave: np.ndarray, real: np.ndarray) -> list[tuple[int, int, float]]:
    """Extremos de una ventana: lista de (posición, +1 máximo / −1 mínimo, precio real)."""
    pendiente = np.sign(np.diff(suave))
    res = []
    for k in range(1, len(suave) - 1):
        a, b = pendiente[k - 1], pendiente[k]
        if a > 0 and b < 0:
            lo, hi = max(0, k - 1), min(len(real), k + 2)
            res.append((k, 1, float(real[lo:hi].max())))
        elif a < 0 and b > 0:
            lo, hi = max(0, k - 1), min(len(real), k + 2)
            res.append((k, -1, float(real[lo:hi].min())))
    return res


def _cerca(a: float, b: float, tol: float) -> bool:
    m = (a + b) / 2
    return abs(a - m) <= tol * m and abs(b - m) <= tol * m


def buscar_patrones(ext: list, ventana: int, d: int, tol: float, separacion: int = 22) -> list[dict]:
    """Patrones de la ventana (posiciones relativas a la ventana).
    Cada patrón: tipo, alcista, cabeza (precio que va al stop), puntos de la
    línea clavicular [(pos, precio), (pos, precio)] y clave (posiciones)."""
    if not ext or ext[-1][0] < ventana - 1 - d:
        return []          # el último extremo no está en las d velas finales: nada confirmado
    out = []
    if len(ext) >= 5:
        e1, e2, e3, e4, e5 = ext[-5:]
        p = [e[2] for e in (e1, e2, e3, e4, e5)]
        if e1[1] == 1 and p[2] > p[0] and p[2] > p[4] and _cerca(p[0], p[4], tol) and _cerca(p[1], p[3], tol):
            out.append({"tipo": "HS", "alcista": False, "cabeza": p[2],
                        "clavicular": [(e2[0], p[1]), (e4[0], p[3])], "posiciones": (e1[0], e3[0], e5[0])})
        if e1[1] == -1 and p[2] < p[0] and p[2] < p[4] and _cerca(p[0], p[4], tol) and _cerca(p[1], p[3], tol):
            out.append({"tipo": "IHS", "alcista": True, "cabeza": p[2],
                        "clavicular": [(e2[0], p[1]), (e4[0], p[3])], "posiciones": (e1[0], e3[0], e5[0])})
    # Doble techo / suelo: E1 = primer extremo de la ventana; Ea = el máximo (mínimo) más alto (bajo) después
    e1 = ext[0]
    despues = [e for e in ext[1:] if e[1] == e1[1]]
    if despues:
        ea = max(despues, key=lambda e: e[2]) if e1[1] == 1 else min(despues, key=lambda e: e[2])
        entre = [e[2] for e in ext if e1[0] < e[0] < ea[0] and e[1] == -e1[1]]
        if entre and _cerca(e1[2], ea[2], tol) and ea[0] - e1[0] > separacion:
            if e1[1] == 1:
                nivel = min(entre)
                out.append({"tipo": "DTOP", "alcista": False, "cabeza": max(e1[2], ea[2]),
                            "clavicular": [(e1[0], nivel), (ea[0], nivel)], "posiciones": (e1[0], ea[0])})
            else:
                nivel = max(entre)
                out.append({"tipo": "DBOT", "alcista": True, "cabeza": min(e1[2], ea[2]),
                            "clavicular": [(e1[0], nivel), (ea[0], nivel)], "posiciones": (e1[0], ea[0])})
    return out


def detectar(cierres: np.ndarray, ventana: int = 38, d: int = 3, tol: float = 0.015) -> list[list[dict]]:
    """Para cada vela t, los patrones confirmados en la ventana que termina en t,
    con posiciones ABSOLUTAS (índice de vela). Solo usa cierres hasta t."""
    T = len(cierres)
    suave = suavizar_ventanas(cierres, ventana)
    res = [[] for _ in range(T)]
    for t in range(ventana - 1, T):
        inicio = t - ventana + 1
        ext = extremos(suave[t], cierres[inicio:t + 1])
        for p in buscar_patrones(ext, ventana, d, tol):
            p["clavicular"] = [(inicio + i, v) for i, v in p["clavicular"]]
            p["id"] = (p["tipo"],) + tuple(inicio + i for i in p["posiciones"])
            res[t].append(p)
    return res


def clavicular_en(p: dict, t: int) -> float:
    """Valor de la línea clavicular en la vela t (recta entre sus dos puntos)."""
    (t1, v1), (t2, v2) = p["clavicular"]
    return v1 if t2 == t1 else v1 + (v2 - v1) * (t - t1) / (t2 - t1)


def senales(cierres: np.ndarray, ventana: int = 38, tol: float = 0.015, patrones=("HS", "IHS", "DTOP", "DBOT"),
            d: int = 3, plazo_entrada: int = 10) -> dict:
    """Rupturas de la línea clavicular, a lo sumo `plazo_entrada` velas después de
    confirmar el patrón (una por patrón). Devuelve arrays por vela:
      alcista / bajista (bool): el cierre rompe la clavicular de un patrón alcista / bajista
      cabeza_* (float): precio de la cabeza (o del techo/suelo extremo) del patrón roto
      objetivo_* (float): movimiento medido proyectado desde la ruptura
    """
    T = len(cierres)
    alc, baj = np.zeros(T, bool), np.zeros(T, bool)
    cab_a, obj_a, cab_b, obj_b = (np.full(T, np.nan) for _ in range(4))
    activos: dict = {}          # id del patrón -> (patrón, vela de confirmación)
    usados: set = set()
    for t, lista in enumerate(detectar(cierres, ventana, d, tol)):
        for p in lista:
            if p["tipo"] in patrones and p["id"] not in activos and p["id"] not in usados:
                activos[p["id"]] = (p, t)
        for pid, (p, t0) in list(activos.items()):
            if t - t0 > plazo_entrada:
                del activos[pid]
                continue
            if t == 0:
                continue
            ahora, antes = clavicular_en(p, t), clavicular_en(p, t - 1)
            altura = abs(p["cabeza"] - clavicular_en(p, t))
            if p["alcista"] and cierres[t] > ahora and cierres[t - 1] <= antes:
                alc[t], cab_a[t], obj_a[t] = True, p["cabeza"], ahora + altura
            elif not p["alcista"] and cierres[t] < ahora and cierres[t - 1] >= antes:
                baj[t], cab_b[t], obj_b[t] = True, p["cabeza"], ahora - altura
            else:
                continue
            usados.add(pid)
            del activos[pid]
    return {"alcista": alc, "bajista": baj, "cabeza_alcista": cab_a, "objetivo_alcista": obj_a,
            "cabeza_bajista": cab_b, "objetivo_bajista": obj_b}
