"""
DUAL MOMENTUM
-------------
Referencia: Antonacci (2014), "Dual Momentum Investing" (libro); versión
académica: Antonacci (2012), "Risk Premia Harvesting Through Dual Momentum".

Idea: combinar dos filtros de momentum.
  - Relativo: de varias bolsas, quedarse con la que más ha subido.
  - Absoluto: invertir en ella solo si ha subido MÁS que la liquidez;
    si no, refugiarse en bonos.

Reglas (cada fin de mes):
1. Rentabilidad de los últimos N meses de SPY, VGK, EWJ y EEM.
2. La mejor de las cuatro es la candidata.
3. Si la candidata ha rendido más que las letras del Tesoro (BIL),
   100 % en la candidata. Si no, 100 % en bonos (IEF).

Diferencia con el original: Antonacci compara EEUU contra el resto del
mundo (un índice global); aquí elegimos entre cuatro regiones.
"""

import pandas as pd

from src.strategies.indicadores import precios_fin_de_mes

RENTA_VARIABLE = ["SPY", "VGK", "EWJ", "EEM"]
REFUGIO = "IEF"
LIQUIDEZ = "BIL"


def senales(precios: pd.DataFrame, meses: int = 12) -> pd.DataFrame:
    p_m = precios_fin_de_mes(precios)
    rent_n = p_m / p_m.shift(meses) - 1

    rv = rent_n[RENTA_VARIABLE]
    completo = rv.notna().all(axis=1) & rent_n[REFUGIO].notna()
    # Antes de que exista BIL (2007), la liquidez rinde 0 a efectos del filtro
    liquidez = rent_n[LIQUIDEZ].fillna(0) if LIQUIDEZ in rent_n else 0

    objetivos = pd.DataFrame(0.0, index=p_m.index, columns=precios.columns)
    mejor = rv[completo].idxmax(axis=1)
    rent_mejor = rv[completo].max(axis=1)
    for fecha in p_m.index[completo]:
        if rent_mejor[fecha] > liquidez[fecha]:
            objetivos.loc[fecha, mejor[fecha]] = 1.0
        else:
            objetivos.loc[fecha, REFUGIO] = 1.0
    objetivos = objetivos[completo]
    return objetivos.reindex(precios.index)


ESTRATEGIA = {
    "id": "dual_momentum",
    "nombre": "Dual momentum (rotación de bolsas)",
    "papel": "núcleo",
    "referencia": "Antonacci (2014), Dual Momentum Investing",
    "publicacion": "2014-11-01",
    "universo": RENTA_VARIABLE + [REFUGIO, LIQUIDEZ],
    "inicio": "comun",
    "senales": senales,
    "parametros": {"meses": 12},
    "rejilla": [{"meses": m} for m in (3, 6, 9, 12)],
    "max_drawdown_aceptable": 0.30,
}
