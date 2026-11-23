"""
EFECTO HALLOWEEN ("SELL IN MAY AND GO AWAY")
--------------------------------------------
Referencia: Bouman y Jacobsen (2002), "The Halloween Indicator, 'Sell in
May and Go Away': Another Puzzle", American Economic Review. Confirmado
con 300 años de datos por Jacobsen y Zhang (2018).

Idea: la bolsa rinde mucho más de noviembre a abril que de mayo a
octubre, en casi todos los países y épocas.

Reglas:
  - Invertido en bolsa desde el inicio del mes de entrada (noviembre)
    hasta el final del mes de salida (abril).
  - El resto del año, en liquidez.
  - Reparto a partes iguales entre los 5 índices.
"""

import pandas as pd

INDICES = ["SPY", "QQQ", "VGK", "EWJ", "EEM"]


def senales(precios: pd.DataFrame, entrada: int = 11, salida: int = 4) -> pd.DataFrame:
    meses = precios.index.month
    if entrada > salida:
        dentro = (meses >= entrada) | (meses <= salida)
    else:
        dentro = (meses >= entrada) & (meses <= salida)
    dentro = pd.Series(dentro, index=precios.index)
    # La señal se emite la víspera, de modo que (con la ejecución al cierre
    # siguiente) se entra al cierre del 1.er día del mes de entrada y se sale
    # al cierre del 1.er día después del mes de salida.
    dentro = dentro.shift(-1).fillna(dentro.iloc[-1]).astype(bool)

    objetivos = pd.DataFrame(0.0, index=precios.index, columns=precios.columns)
    disponibles = precios[INDICES].ffill().notna().all(axis=1)
    for a in INDICES:
        objetivos[a] = dentro.astype(float) / len(INDICES)
    return objetivos.where(disponibles, axis=0)


ESTRATEGIA = {
    "id": "halloween",
    "nombre": "Efecto Halloween (noviembre-abril)",
    "papel": "satélite",
    "referencia": "Bouman y Jacobsen (2002), The Halloween Indicator, AER",
    "publicacion": "2002-12-01",
    "universo": INDICES + ["BIL"],
    "inicio": "comun",
    "senales": senales,
    "parametros": {"entrada": 11, "salida": 4},
    "rejilla": [{"entrada": e, "salida": s} for e in (10, 11) for s in (4, 5)],
    "max_drawdown_aceptable": 0.30,
}
