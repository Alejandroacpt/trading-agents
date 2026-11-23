"""
CARTERA COMBINADA
-----------------
Junta varias estrategias ("bolsillos") en una sola cartera. Es un primer
borrador de lo que hará el agente de riesgo.

Reparto entre bolsillos: PARIDAD DE RIESGO. Cada bolsillo recibe un
capital inversamente proporcional a su volatilidad del último año, para
que todos aporten un riesgo parecido. Como cripto es mucho más volátil,
recibe mucho menos capital. Además se pone un tope al bolsillo de cripto.

Se recalcula cada fin de mes con datos pasados (sin mirar el futuro).

Composición fijada ANTES de ver resultados: las dos estrategias que
quedaron en observación, en su versión con control de volatilidad.
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import fines_de_mes
from src.strategies.variantes_riesgo import CRIPTO_VOL, FABER_VOL

BOLSILLOS = [FABER_VOL, CRIPTO_VOL]
BOLSILLO_CRIPTO = CRIPTO_VOL["id"]


def _rent_aproximada(objetivos: pd.DataFrame, precios: pd.DataFrame) -> pd.Series:
    """Rentabilidad diaria aproximada de un bolsillo (sin costes), solo para
    estimar su volatilidad."""
    pesos = objetivos.ffill().fillna(0).shift(1)
    r = precios.ffill().pct_change().fillna(0)
    return (pesos * r).sum(axis=1)


def senales(precios: pd.DataFrame, tope_cripto: float = 0.25, ventana: int = 252) -> pd.DataFrame:
    objetivos_b, vol_b = {}, {}
    for b in BOLSILLOS:
        cols = [c for c in b["universo"] if c in precios.columns]
        obj = b["senales"](precios[cols], **b["parametros"])
        obj = obj.reindex(index=precios.index, columns=precios.columns)
        objetivos_b[b["id"]] = obj
        rent = _rent_aproximada(obj, precios)
        empezado = obj.notna().any(axis=1).cummax()
        vol_b[b["id"]] = rent.where(empezado).rolling(ventana, min_periods=ventana // 2).std() * np.sqrt(365)

    vol = pd.DataFrame(vol_b)
    fm = fines_de_mes(precios.index)
    inversa = (1 / vol.loc[fm]).replace([np.inf], np.nan)
    reparto = inversa.div(inversa.sum(axis=1), axis=0)
    # Tope a cripto: lo que sobra pasa al resto de bolsillos
    exceso = (reparto[BOLSILLO_CRIPTO] - tope_cripto).clip(lower=0)
    reparto[BOLSILLO_CRIPTO] -= exceso
    otros = [c for c in reparto.columns if c != BOLSILLO_CRIPTO]
    reparto[otros] = reparto[otros].add(exceso / len(otros), axis=0)
    reparto = reparto.dropna()  # solo cuando todos los bolsillos tienen historia

    reparto_diario = reparto.reindex(precios.index).ffill()
    total = sum(objetivos_b[k].ffill().fillna(0).mul(reparto_diario[k], axis=0) for k in objetivos_b)
    total = total.where(reparto_diario.notna().all(axis=1), axis=0)

    # Solo se opera cuando cambia algo (reparto mensual o señales de un bolsillo)
    cambia = total.fillna(0).diff().abs().sum(axis=1) > 1e-9
    return total.where(cambia | total.notna().all(axis=1) & ~total.shift().notna().all(axis=1), axis=0)


ESTRATEGIA = {
    "id": "cartera",
    "nombre": "Cartera: Faber + cripto (con control de volatilidad)",
    "papel": "cartera combinada",
    "referencia": "Combinación por paridad de riesgo de las estrategias en observación",
    "publicacion": "2026-11-23",   # se define hoy: todo el histórico es 'pre-publicación'
    "universo": sorted(set(FABER_VOL["universo"]) | set(CRIPTO_VOL["universo"])),
    "inicio": "comun",
    "senales": senales,
    "parametros": {"tope_cripto": 0.25},
    "rejilla": [{"tope_cripto": t} for t in (0.15, 0.25, 0.35)],
    "max_drawdown_aceptable": 0.25,
    "nota_validacion": (
        "Composición fijada antes de ver resultados (incluye Faber con control de volatilidad, que luego salió "
        "rechazada). La referencia 'comprar y mantener' pesa cripto con 3 de 10 activos, por eso su CAGR es tan alto "
        "y su caída tan grande; no es una comparación justa de riesgo. Sin fecha de publicación: no hay periodo "
        "posterior a la publicación que evaluar."
    ),
}
