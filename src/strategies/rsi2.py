"""
REVERSIÓN A LA MEDIA A CORTO PLAZO (RSI-2)
------------------------------------------
Referencia: Connors y Alvarez (2008), "Short Term Trading Strategies
That Work". Evidencia sobre todo de practicantes, no académica.

Idea: en un índice que está en tendencia alcista, las caídas bruscas de
2-5 días suelen rebotar. Se compra el "pánico" y se vende el rebote.

Reglas (cada día, para cada índice):
  - Entrar si: precio > media de 200 sesiones (tendencia alcista)
               y RSI de 2 sesiones < 10 (muy sobrevendido).
  - Salir si:  precio > media de 5 sesiones (ya rebotó).
Cada índice tiene reservada su parte fija del capital (1/5).

Nota: en el libro se compra al cierre del mismo día de la señal. Aquí,
como en todo el sistema, se ejecuta al cierre del día siguiente, que es
lo que podremos hacer de verdad. Esto empeora algo el resultado.
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import media_movil, rsi, serie_propia

INDICES = ["SPY", "QQQ", "VGK", "EWJ", "EEM"]


def senales(precios: pd.DataFrame, umbral: float = 10, tendencia: int = 200, salida: int = 5) -> pd.DataFrame:
    objetivos = pd.DataFrame(index=precios.index, columns=precios.columns, dtype=float)
    reparto = 1 / len(INDICES)

    for a in INDICES:
        s = serie_propia(precios, a)
        ma_t = media_movil(s, tendencia)
        ma_s = media_movil(s, salida)
        r = rsi(s, 2)

        dentro = False
        posicion = np.full(len(s), np.nan)
        for i in range(len(s)):
            if np.isnan(ma_t.iloc[i]) or np.isnan(r.iloc[i]):
                continue  # aún sin histórico suficiente
            if not dentro and s.iloc[i] > ma_t.iloc[i] and r.iloc[i] < umbral:
                dentro = True
            elif dentro and s.iloc[i] > ma_s.iloc[i]:
                dentro = False
            posicion[i] = reparto if dentro else 0.0
        objetivos[a] = pd.Series(posicion, index=s.index).reindex(precios.index).ffill()

    for a in precios.columns:
        if a not in INDICES:
            objetivos[a] = 0.0
    # Solo cuando todos los índices tienen señal (inicio común)
    return objetivos.where(objetivos[INDICES].notna().all(axis=1))


ESTRATEGIA = {
    "id": "rsi2",
    "nombre": "Reversión a la media (RSI-2)",
    "papel": "satélite",
    "referencia": "Connors y Alvarez (2008), Short Term Trading Strategies That Work",
    "publicacion": "2008-01-01",
    "universo": INDICES + ["BIL"],
    "inicio": "comun",
    "senales": senales,
    "parametros": {"umbral": 10, "tendencia": 200},
    "rejilla": [{"umbral": u, "tendencia": t} for u in (5, 10, 15) for t in (150, 200, 250)],
    "max_drawdown_aceptable": 0.25,
    "nota_validacion": (
        "Su ventaja depende mucho de cuándo se ejecuta. Comprando al cierre del mismo día de la señal "
        "(como en el libro) el Sharpe completo sube de 0,14 a 0,33 y el de test, de -0,05 a 0,24: "
        "ni así llega al umbral. Se podría replantear calculando la señal minutos antes del cierre "
        "y enviando órdenes 'market-on-close' a Alpaca."
    ),
}
