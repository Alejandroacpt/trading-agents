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
from src.tactico.velas import regimen_bajista, tendencia_diaria


def atr(df: pd.DataFrame, n: int = 24) -> pd.Series:
    cierre_prev = df["close"].shift(1)
    rango = pd.concat([df["high"] - df["low"], (df["high"] - cierre_prev).abs(),
                       (df["low"] - cierre_prev).abs()], axis=1).max(axis=1)
    return rango.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _tabla(df, entrada, salida, stop, dinamico=np.nan, max_velas=np.nan, corto=False) -> pd.DataFrame:
    """corto=True: todas las entradas de la tabla son ventas en corto (solo investigación;
    el simulador refleja stop, stop dinámico y orden limitada, y cobra la financiación)."""
    return pd.DataFrame({
        "entrada": entrada.fillna(False).astype(bool),
        "salida": salida.fillna(False).astype(bool),
        "stop": stop,
        "dinamico": dinamico if isinstance(dinamico, pd.Series) else pd.Series(dinamico, index=df.index),
        "max_velas": pd.Series(max_velas, index=df.index),
        "corto": pd.Series(bool(corto), index=df.index),
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
        entrada = tendencia_diaria(df, 50) & (c > ema(c, 50)) & (rsi(c, 3) < umbral)
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


# ----------------------------------------------------------------------
# CORTOS EN CRIPTO (encargo de Alejandro, 26 nov 2026). Solo investigación:
# Alpaca no opera cortos en cripto (se ejecutarían con ETFs inversos).
# Reglas y rejillas fijadas en research/GUIA_INVESTIGADOR.md ANTES de ver
# resultados. Velas de 4 h, solo mercado cripto.
# ----------------------------------------------------------------------

def corto_rebote(ohlc: dict, velas: int = 50) -> dict:
    """Vender los rebotes en tendencia bajista. Régimen: cierre diario de ayer
    por debajo de su media de 50 días. Entrada en corto: el máximo de la vela
    toca la media exponencial de N velas pero la vela cierra por debajo de ella
    y en negativo. Salida: cierre por encima de la media, o 30 velas (5 días).
    Stop 2 ATR(14) por encima de la entrada, stop dinámico 3 ATR."""
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        m = ema(c, velas)
        entrada = regimen_bajista(df, 50) & (df["high"] >= m) & (c < m) & (c < df["open"])
        a_t = atr(df, 14)
        out[a] = _tabla(df, entrada, c > m, 2 * a_t, dinamico=3 * a_t, max_velas=30, corto=True)
    return out


def corto_ruptura_bajista(ohlc: dict, velas: int = 60) -> dict:
    """Ruptura a la baja con la tendencia bajista confirmada. Régimen: cierre
    diario de ayer por debajo de su media de 200 días Y esa media por debajo de
    la de hace 20 días. Entrada en corto: cierre por debajo del mínimo de las N
    velas anteriores. Salida: cierre por encima del máximo de N/2 velas o fin del
    régimen. Stop 3 ATR(14), stop dinámico 4 ATR."""
    salida_n = max(6, velas // 2)
    out = {}
    for a, df in ohlc.items():
        c = df["close"]
        regimen = regimen_bajista(df, 200, pendiente=20)
        minimo = df["low"].rolling(velas).min().shift(1)
        maximo = df["high"].rolling(salida_n).max().shift(1)
        a_t = atr(df, 14)
        out[a] = _tabla(df, regimen & (c < minimo), (c > maximo) | ~regimen, 3 * a_t,
                        dinamico=4 * a_t, corto=True)
    return out


def corto_debilidad_relativa(ohlc: dict, velas: int = 90, referencia: str = "BTC/USD",
                             peores: int = 2, salida_fuera_de: int = 3) -> dict:
    """Las monedas más débiles frente a BTC. Régimen: BTC con cierre diario de
    ayer por debajo de su media de 50 días. En cada vela se ordenan las monedas
    (menos BTC) por su rendimiento de N velas MENOS el de BTC; entrada en corto
    en las 2 peores; salida cuando una deja de estar entre las 3 peores o
    termina el régimen. Stop 3 ATR(14). BTC no se opera."""
    if referencia not in ohlc:
        return {a: _tabla(df, pd.Series(False, index=df.index), pd.Series(False, index=df.index),
                          atr(df, 14), corto=True) for a, df in ohlc.items()}
    btc = ohlc[referencia]
    otras = [a for a in ohlc if a != referencia]
    indice = pd.DatetimeIndex(sorted(set().union(*[ohlc[a].index for a in ohlc])))
    rend_btc = (btc["close"] / btc["close"].shift(velas) - 1).reindex(indice)
    regimen = regimen_bajista(btc, 50).reindex(indice).fillna(False).astype(bool)
    relativo = pd.DataFrame({a: (ohlc[a]["close"] / ohlc[a]["close"].shift(velas) - 1).reindex(indice) - rend_btc
                             for a in otras})
    puesto = relativo.rank(axis=1, ascending=True, method="first")   # 1 = la más débil
    out = {}
    for a, df in ohlc.items():
        if a == referencia:
            nada = pd.Series(False, index=df.index)
            out[a] = _tabla(df, nada, nada, atr(df, 14), corto=True)
            continue
        p_a = puesto[a].reindex(df.index)
        reg = regimen.reindex(df.index).fillna(False).astype(bool)
        entrada = reg & (p_a <= peores)
        salida = ~reg | (p_a > salida_fuera_de) | p_a.isna()
        out[a] = _tabla(df, entrada, salida, 3 * atr(df, 14), corto=True)
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
    # --- cortos en cripto (solo investigación; velas de 4 h) ---
    "corto_rebote": {
        "nombre": "Corto: vender rebotes en tendencia bajista (4 h)",
        "funcion": corto_rebote,
        "velas": "4h",
        "mercados": ["cripto"],
        "laboratorio": False,   # rechazada en el cribado (26 nov 2026): el laboratorio semanal no la prueba
        "referencia": "Encargo de Alejandro (26 nov 2026); venta de rebotes a la media en tendencia bajista (Elder, Trading for a Living, 1993)",
        "publicacion": "1993-01-01",
        "parametros": {"velas": 50},
        "rejilla": [{"velas": v} for v in (20, 50, 100)],
    },
    "corto_ruptura_bajista": {
        "nombre": "Corto: ruptura bajista con tendencia confirmada (4 h)",
        "funcion": corto_ruptura_bajista,
        "velas": "4h",
        "mercados": ["cripto"],
        "laboratorio": False,   # rechazada en el cribado (26 nov 2026): el laboratorio semanal no la prueba
        "referencia": "Encargo de Alejandro (26 nov 2026); Donchian a la baja (Faith, 2007) con media de 200 días bajando",
        "publicacion": "2007-01-01",
        "parametros": {"velas": 60},
        "rejilla": [{"velas": v} for v in (30, 60, 120)],
    },
    "corto_debilidad_relativa": {
        "nombre": "Corto: monedas más débiles frente a BTC (4 h)",
        "funcion": corto_debilidad_relativa,
        "velas": "4h",
        "mercados": ["cripto"],
        "laboratorio": False,   # rechazada en el cribado (26 nov 2026): el laboratorio semanal no la prueba
        "referencia": "Encargo de Alejandro (26 nov 2026); momentum transversal en cripto (Liu, Tsyvinski y Wu, 2022, JF), lado corto",
        "publicacion": "2022-01-01",
        "parametros": {"velas": 90},
        "rejilla": [{"velas": v} for v in (42, 90, 180)],
    },
}
