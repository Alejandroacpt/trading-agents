"""
TENDENCIA / MOMENTUM TEMPORAL (TSMOM)
-------------------------------------
Referencia: Moskowitz, Ooi y Pedersen (2012), "Time Series Momentum",
Journal of Financial Economics. Ampliado en Hurst, Ooi y Pedersen (2017),
"A Century of Evidence on Trend-Following Investing".

Idea: lo que ha subido en los últimos meses tiende a seguir subiendo
(y lo que ha bajado, a seguir bajando) durante un tiempo.

Reglas (cada fin de mes):
1. Para cada activo, mirar su rentabilidad de los últimos N meses.
2. Si es positiva -> comprado. Si es negativa -> vendido en corto
   (o fuera, en la versión "solo largos", que es la que podremos
   ejecutar con poco capital).
3. Tamaño inverso a la volatilidad: los activos tranquilos (bonos)
   pesan más que los nerviosos (petróleo), para que todos aporten
   un riesgo parecido. Sin apalancamiento: la suma de pesos <= 100 %.
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import precios_fin_de_mes, volatilidad_anual


def senales(precios: pd.DataFrame, meses: int = 12, largo_corto: bool = False) -> pd.DataFrame:
    p_m = precios_fin_de_mes(precios)
    rent_n = p_m / p_m.shift(meses) - 1

    signo = np.sign(rent_n)
    if not largo_corto:
        signo = signo.clip(lower=0)  # solo largos: si la tendencia es bajista, fuera

    vol = volatilidad_anual(precios).reindex(p_m.index)
    inversa = (1 / vol).where(rent_n.notna())
    peso_riesgo = inversa.div(inversa.sum(axis=1), axis=0)  # suma 1 entre los activos con datos

    objetivos = signo * peso_riesgo
    objetivos = objetivos.dropna(how="all")
    return objetivos.reindex(precios.index)


UNIVERSO = [
    "SPY", "QQQ", "VGK", "EWJ", "EEM",            # renta variable
    "IEF", "TLT",                                  # bonos
    "GLD", "SLV", "USO", "DBC",                    # materias primas
    "EURUSD=X", "GBPUSD=X", "JPY=X", "AUDUSD=X", "CHF=X",  # forex
]

ESTRATEGIA = {
    "id": "tsmom",
    "nombre": "Tendencia multi-activo (TSMOM)",
    "papel": "núcleo",
    "referencia": "Moskowitz, Ooi y Pedersen (2012), Time Series Momentum, JFE",
    "publicacion": "2012-05-01",
    "universo": UNIVERSO,
    "inicio": "disponibles",
    "min_activos": 12,  # empezar cuando haya al menos 12 de los 16 activos
    "senales": senales,
    "parametros": {"meses": 12, "largo_corto": False},
    "rejilla": [{"meses": m, "largo_corto": lc} for m in (3, 6, 9, 12) for lc in (False, True)],
    "max_drawdown_aceptable": 0.30,
}
