"""
TENDENCIA MULTI-HORIZONTE
-------------------------
Referencia: Hurst, Ooi y Pedersen (2017), "A Century of Evidence on
Trend-Following Investing", Journal of Portfolio Management.

Idea: en vez de mirar un solo plazo (12 meses), combinar varios (1, 3 y
12 meses). Cada horizonte "vota"; la posición es proporcional a los
votos alcistas. Así se reacciona antes a los giros (horizonte corto)
sin perder las tendencias largas, y la señal es más estable.

Reglas (cada fin de mes), para cada ETF:
  - fuerza = proporción de horizontes con rentabilidad positiva (0 a 1)
  - peso = fuerza × reparto inverso a la volatilidad (sin apalancamiento)
Solo largos y solo ETFs (en divisas, "solo largos" no tiene sentido:
comprar EUR/USD es vender dólares).
"""

import pandas as pd

from src.strategies.indicadores import precios_fin_de_mes, volatilidad_anual

ETFS = ["SPY", "QQQ", "VGK", "EWJ", "EEM", "IEF", "TLT", "GLD", "SLV", "USO", "DBC"]


def senales(precios: pd.DataFrame, horizontes: tuple = (1, 3, 12)) -> pd.DataFrame:
    p_m = precios_fin_de_mes(precios[ETFS])
    votos = [(p_m / p_m.shift(h) - 1 > 0).astype(float).where(p_m.shift(h).notna()) for h in horizontes]
    fuerza = sum(votos) / len(horizontes)

    vol = volatilidad_anual(precios[ETFS]).reindex(p_m.index)
    inversa = (1 / vol).where(fuerza.notna())
    peso_riesgo = inversa.div(inversa.sum(axis=1), axis=0)

    objetivos = (fuerza * peso_riesgo).dropna(how="all")
    return objetivos.reindex(index=precios.index, columns=precios.columns)


ESTRATEGIA = {
    "id": "multi_horizonte",
    "nombre": "Tendencia multi-horizonte (1-3-12 meses)",
    "papel": "núcleo",
    "referencia": "Hurst, Ooi y Pedersen (2017), A Century of Evidence on Trend-Following Investing, JPM",
    "publicacion": "2017-09-01",
    "universo": ETFS + ["BIL"],
    "inicio": "disponibles",
    "min_activos": 9,
    "senales": senales,
    "parametros": {"horizontes": (1, 3, 12)},
    "rejilla": [{"horizontes": h} for h in ((1, 3, 12), (3, 6, 12), (1, 3, 6, 12))],
    "max_drawdown_aceptable": 0.30,
    "nota_validacion": (
        "Pasa todas las pruebas menos el Sharpe deflactado: con 20 años de datos, un Sharpe de 0,56 no basta "
        "para descartar la suerte tras 64 pruebas. Mejora claramente a la TSMOM de un solo horizonte (0,37)."
    ),
}
