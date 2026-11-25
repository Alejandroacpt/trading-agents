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

Prioridad entre señales simultáneas (prueba del 25 nov 2026): si salen más
compras que dinero, entran por el orden de la lista de activos de
config/tactico.yaml, que va de lo más diversificado a lo más concreto
(SPY, QQQ, IWM → sectores → acciones sueltas). Se probaron, eligiendo solo con
el periodo de ENTRENAMIENTO, cuatro reglas "por rentabilidad esperada" en la
estrategia activa (momentum con tendencia, acciones):
                                     entreno (Sharpe)   test (CAGR / Sharpe)
  orden de lista (diversificado 1º)       0,93            +12,1 % / 1,00
  señal más fuerte (momentum/vol)         0,91             −1,6 % / −0,06
  señal menos estirada                    0,82             +6,7 % / 0,57
  menor volatilidad                       0,85             +6,3 % / 0,59
  mayor subida bruta                      0,86             −1,1 % / −0,01
Ninguna mejora el orden actual en entrenamiento, así que se mantiene. El
simulador admite la columna "prioridad" (y fuerza_momentum / fuerza_reversion
para calcularla) para probar reglas nuevas en el laboratorio; una regla solo
pasa a vivo si mejora en entrenamiento y lo confirma en test.
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import rsi
from src.tactico.velas import tendencia_diaria


def atr(df: pd.DataFrame, n: int = 24) -> pd.Series:
    cierre_prev = df["close"].shift(1)
    rango = pd.concat([df["high"] - df["low"], (df["high"] - cierre_prev).abs(),
                       (df["low"] - cierre_prev).abs()], axis=1).max(axis=1)
    return rango.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def fuerza_momentum(c: pd.Series, n: int) -> pd.Series:
    """Rendimiento de n velas en unidades de su volatilidad (tipo t-estadístico)."""
    vol = c.pct_change().rolling(n, min_periods=max(10, n // 2)).std() * np.sqrt(n)
    return (c / c.shift(n) - 1) / vol.replace(0, np.nan)


def fuerza_reversion(r: pd.Series, umbral: float) -> pd.Series:
    """Cuánto por debajo del umbral está el RSI (0 = justo en el umbral, 1 = RSI en 0)."""
    return (umbral - r) / umbral


def _tabla(df, entrada, salida, stop, dinamico=np.nan, max_velas=np.nan, prioridad=np.nan) -> pd.DataFrame:
    return pd.DataFrame({
        "entrada": entrada.fillna(False).astype(bool),
        "salida": salida.fillna(False).astype(bool),
        "stop": stop,
        "dinamico": dinamico if isinstance(dinamico, pd.Series) else pd.Series(dinamico, index=df.index),
        "max_velas": pd.Series(max_velas, index=df.index),
        "prioridad": prioridad if isinstance(prioridad, pd.Series) else pd.Series(prioridad, index=df.index),
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
        r = rsi(c, 2)
        entrada = (c > ema(c, 200)) & (r < umbral)
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


# ----------------------------------------------------------------------
# Familias de BAJA ROTACIÓN (velas de 4 h en cripto / media sesión en
# acciones, solo a favor de la tendencia diaria). Fijadas el 23 nov 2026
# tras ver que, con velas de 1 hora, los costes se comían la ventaja.
# ----------------------------------------------------------------------

def ruptura_tendencia(ohlc: dict, velas: int = 60) -> dict:
    """Ruptura del máximo de N velas solo si la tendencia diaria es alcista;
    sale al perder el mínimo de N/2 velas; stop 3 ATR y stop dinámico 4 ATR."""
    salida_n = max(6, velas // 2)
    out = {}
    for a, df in ohlc.items():
        maximo = df["high"].rolling(velas).max().shift(1)
        minimo = df["low"].rolling(salida_n).min().shift(1)
        a_t = atr(df, 14)
        entrada = (df["close"] > maximo) & tendencia_diaria(df, 50)
        out[a] = _tabla(df, entrada, df["close"] < minimo, 3 * a_t, dinamico=4 * a_t)
    return out


def retroceso_tendencia(ohlc: dict, umbral: float = 25) -> dict:
    """En tendencia diaria alcista, compra un retroceso (RSI de 3 velas < umbral)
    con ORDEN LIMITADA al cierre de la vela de señal (si el precio no vuelve a
    ese nivel, no se compra); vende al rebotar (precio > media de 5 velas) o
    tras 30 velas; stop 2,5 ATR."""
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        r = rsi(c, 3)
        entrada = tendencia_diaria(df, 50) & (c > ema(c, 50)) & (r < umbral)
        t = _tabla(df, entrada, c > c.rolling(5).mean(), 2.5 * atr(df, 14), max_velas=30)
        t["limite"] = c.where(entrada)
        out[a] = t
    return out


def momentum_tendencia(ohlc: dict, velas: int = 90) -> dict:
    """Entra cuando el rendimiento de N velas se vuelve positivo y el precio
    supera su media de N velas, solo con tendencia diaria alcista; sale si el
    rendimiento se vuelve negativo; stop 3 ATR y stop dinámico 4 ATR."""
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        condicion = (c / c.shift(velas) - 1 > 0) & (c > ema(c, velas)) & tendencia_diaria(df, 50)
        entrada = condicion & ~condicion.shift(1, fill_value=False)
        a_t = atr(df, 14)
        out[a] = _tabla(df, entrada, c / c.shift(velas) - 1 < 0, 3 * a_t, dinamico=4 * a_t)
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
    # --- baja rotación: velas de 4 h (cripto) / media sesión (acciones) ---
    "ruptura_tendencia": {
        "nombre": "Ruptura con tendencia diaria (4 h)",
        "funcion": ruptura_tendencia,
        "velas": "4h",
        "referencia": "Donchian; Faith (2007); filtro de tendencia de Faber (2007)",
        "publicacion": "2007-01-01",
        "parametros": {"velas": 60},
        "rejilla": [{"velas": v} for v in (30, 60, 120)],
    },
    "retroceso_tendencia": {
        "nombre": "Retroceso en tendencia con orden limitada (4 h)",
        "funcion": retroceso_tendencia,
        "velas": "4h",
        "referencia": "Connors y Alvarez (2008); compra de retrocesos en tendencia",
        "publicacion": "2008-01-01",
        "parametros": {"umbral": 25},
        "rejilla": [{"umbral": u} for u in (15, 25, 35)],
    },
    "momentum_tendencia": {
        "nombre": "Momentum con tendencia diaria (4 h)",
        "funcion": momentum_tendencia,
        "velas": "4h",
        "referencia": "Moskowitz, Ooi y Pedersen (2012); Hurst, Ooi y Pedersen (2017)",
        "publicacion": "2012-05-01",
        "parametros": {"velas": 90},
        "rejilla": [{"velas": v} for v in (42, 90, 180)],
    },
}
