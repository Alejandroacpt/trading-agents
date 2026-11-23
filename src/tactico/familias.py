"""
FAMILIAS TÁCTICAS (velas de 1 hora)
-----------------------------------
Cada familia devuelve, por activo, una tabla con:
  entrada (bool), salida (bool), stop (distancia en precio),
  dinamico (distancia del stop dinámico o NaN), max_velas (o NaN).

El stop se mide en ATR (rango verdadero medio de las últimas 24 velas):
se adapta a lo que se mueve cada activo, así un 1,5 % de riesgo significa
lo mismo en Bitcoin que en un ETF de bonos.

Las rejillas se fijaron ANTES de ver resultados (23 nov 2026).
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import rsi


def atr(df: pd.DataFrame, n: int = 24) -> pd.Series:
    cierre_prev = df["close"].shift(1)
    rango = pd.concat([df["high"] - df["low"], (df["high"] - cierre_prev).abs(),
                       (df["low"] - cierre_prev).abs()], axis=1).max(axis=1)
    return rango.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _tabla(df, entrada, salida, stop, dinamico=np.nan, max_velas=np.nan) -> pd.DataFrame:
    return pd.DataFrame({
        "entrada": entrada.fillna(False).astype(bool),
        "salida": salida.fillna(False).astype(bool),
        "stop": stop,
        "dinamico": dinamico if isinstance(dinamico, pd.Series) else pd.Series(dinamico, index=df.index),
        "max_velas": pd.Series(max_velas, index=df.index),
    }, index=df.index)


def ruptura_horaria(ohlc: dict, velas: int = 48) -> dict:
    """Entra al superar el máximo de las últimas N velas; sale al perder el
    mínimo de N/2 velas; stop inicial a 2 ATR."""
    salida_n = max(6, velas // 2)
    out = {}
    for a, df in ohlc.items():
        maximo = df["high"].rolling(velas).max().shift(1)
        minimo = df["low"].rolling(salida_n).min().shift(1)
        out[a] = _tabla(df, df["close"] > maximo, df["close"] < minimo, 2 * atr(df))
    return out


def reversion_horaria(ohlc: dict, umbral: float = 10) -> dict:
    """En tendencia alcista (precio > media exponencial de 200 velas), compra
    caídas bruscas (RSI de 2 velas < umbral); vende al rebotar (precio > media
    de 5 velas) o tras 48 velas; stop a 3 ATR."""
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        entrada = (c > ema(c, 200)) & (rsi(c, 2) < umbral)
        salida = c > c.rolling(5).mean()
        out[a] = _tabla(df, entrada, salida, 3 * atr(df), max_velas=48)
    return out


def momentum_horario(ohlc: dict, velas: int = 72) -> dict:
    """Entra cuando el rendimiento de las últimas N velas se vuelve positivo y
    el precio supera su media exponencial de N velas; sale si el rendimiento
    se vuelve negativo; stop inicial a 2,5 ATR y stop dinámico a 3 ATR."""
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        condicion = (c / c.shift(velas) - 1 > 0) & (c > ema(c, velas))
        entrada = condicion & ~condicion.shift(1, fill_value=False)
        salida = c / c.shift(velas) - 1 < 0
        a_t = atr(df)
        out[a] = _tabla(df, entrada, salida, 2.5 * a_t, dinamico=3 * a_t)
    return out


FAMILIAS_TACTICAS = {
    "ruptura_horaria": {
        "nombre": "Ruptura horaria (canal de N velas)",
        "funcion": ruptura_horaria,
        "referencia": "Donchian; Faith (2007); Wilcox y Crittenden (2005) — aplicado a velas de 1 hora",
        "publicacion": "2005-06-01",
        "parametros": {"velas": 48},
        "rejilla": [{"velas": v} for v in (24, 48, 96)],
    },
    "reversion_horaria": {
        "nombre": "Reversión horaria (RSI-2 con tendencia)",
        "funcion": reversion_horaria,
        "referencia": "Connors y Alvarez (2008) — aplicado a velas de 1 hora",
        "publicacion": "2008-01-01",
        "parametros": {"umbral": 10},
        "rejilla": [{"umbral": u} for u in (5, 10, 20)],
    },
    "momentum_horario": {
        "nombre": "Momentum horario con stop dinámico",
        "funcion": momentum_horario,
        "referencia": "Moskowitz, Ooi y Pedersen (2012); Gao, Han, Li y Zhou (2018), Market Intraday Momentum, JFE",
        "publicacion": "2018-01-01",
        "parametros": {"velas": 72},
        "rejilla": [{"velas": v} for v in (24, 72, 168)],
    },
}
