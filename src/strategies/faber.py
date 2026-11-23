"""
FILTRO DE TENDENCIA DE 10 MESES (FABER)
---------------------------------------
Referencia: Faber (2007), "A Quantitative Approach to Tactical Asset
Allocation", Journal of Wealth Management.

Idea: repartir el dinero a partes iguales entre varias clases de activo,
pero salir a liquidez de las que estén por debajo de su media de 10
meses. No busca ganar más que el mercado, sino evitar las grandes caídas
(en 2008 habría estado casi todo en liquidez).

Reglas (cada fin de mes), para cada activo de la cesta:
  - precio > media de los últimos N cierres mensuales -> invertido (1/7)
  - si no -> esa parte en liquidez

Cesta: EEUU (SPY), Europa (VGK), Japón (EWJ), emergentes (EEM),
bonos (IEF), oro (GLD) y materias primas (DBC). Faber usaba también
inmobiliario (REITs), que no está en nuestro universo.
"""

import pandas as pd

from src.strategies.indicadores import precios_fin_de_mes

CESTA = ["SPY", "VGK", "EWJ", "EEM", "IEF", "GLD", "DBC"]


def senales(precios: pd.DataFrame, meses: int = 10) -> pd.DataFrame:
    p_m = precios_fin_de_mes(precios[CESTA])
    media = p_m.rolling(meses, min_periods=meses).mean()
    invertido = (p_m > media).astype(float)
    objetivos = invertido / len(CESTA)
    objetivos = objetivos[media.notna().all(axis=1)]
    return objetivos.reindex(index=precios.index, columns=precios.columns)


ESTRATEGIA = {
    "id": "faber",
    "nombre": "Filtro de tendencia de 10 meses (Faber)",
    "papel": "control de caídas",
    "referencia": "Faber (2007), A Quantitative Approach to Tactical Asset Allocation, JWM",
    "publicacion": "2007-01-01",
    "universo": CESTA + ["BIL"],
    "inicio": "comun",
    "senales": senales,
    "parametros": {"meses": 10},
    "rejilla": [{"meses": m} for m in (6, 8, 10, 12)],
    "max_drawdown_aceptable": 0.25,
}
