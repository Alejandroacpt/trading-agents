"""
INDICADORES TÉCNICOS
--------------------
Piezas básicas que usan las estrategias. Todas trabajan con los días
en que el activo cotiza de verdad (sin los huecos de fin de semana o
festivos), para que una media de 200 sesiones sean 200 sesiones reales.
"""

import numpy as np
import pandas as pd


def serie_propia(precios: pd.DataFrame, activo: str) -> pd.Series:
    """Precios de un activo solo en los días en que cotizó."""
    return precios[activo].dropna()


def fines_de_mes(indice: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Último día con datos de cada mes (el día en que se rebalancea)."""
    s = indice.to_series()
    return pd.DatetimeIndex(s.groupby(indice.to_period("M")).max().values)


def mes_cerrado(ultima_fecha: pd.Timestamp) -> bool:
    """¿Es 'ultima_fecha' el último día hábil de su mes?"""
    return (ultima_fecha + pd.offsets.BDay(1)).month != ultima_fecha.month


def precios_fin_de_mes(precios: pd.DataFrame) -> pd.DataFrame:
    """Precio de cierre de cada activo el último día de cada mes CERRADO.

    El mes en curso solo se incluye si el último dato es del último día
    hábil del mes. Así, en vivo, una estrategia mensual no cambia de
    opinión a mitad de mes con un precio provisional.
    """
    rellenos = precios.ffill()
    fm = fines_de_mes(precios.index)
    if len(fm) and not mes_cerrado(fm[-1]):
        fm = fm[:-1]
    p = rellenos.loc[fm]
    # Si un activo aún no existía ese mes, se queda en NaN
    primeros = precios.apply(lambda c: c.first_valid_index())
    for a in p.columns:
        if primeros[a] is not None:
            p.loc[p.index < primeros[a], a] = np.nan
        else:
            p[a] = np.nan
    return p


def media_movil(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 2) -> pd.Series:
    """RSI de Wilder. Valores bajos (< 10) = muy sobrevendido."""
    delta = s.diff()
    subidas = delta.clip(lower=0)
    bajadas = -delta.clip(upper=0)
    media_sub = subidas.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    media_baj = bajadas.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = media_sub / media_baj.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(media_baj != 0, 100.0)


def volatilidad_anual(precios: pd.DataFrame, centro_masa: int = 60) -> pd.DataFrame:
    """Volatilidad anualizada de cada activo con media exponencial
    (centro de masa de 60 días, como en Moskowitz, Ooi y Pedersen).
    Se calcula con los días reales de cada activo y luego se alinea."""
    salida = {}
    for a in precios.columns:
        s = serie_propia(precios, a)
        if len(s) < 30:
            continue
        r = s.pct_change()
        anios = (s.index[-1] - s.index[0]).days / 365.25
        ppa = len(s) / anios if anios > 0 else 252
        salida[a] = r.ewm(com=centro_masa, min_periods=centro_masa).std() * np.sqrt(ppa)
    vol = pd.DataFrame(salida).reindex(precios.index).ffill()
    return vol.reindex(columns=precios.columns)
