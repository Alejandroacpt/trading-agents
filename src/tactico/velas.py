"""
VELAS AGREGADAS Y FILTRO DE TENDENCIA DIARIA
--------------------------------------------
Para operar menos (y pagar menos costes) se usan velas más largas:
  - Cripto: velas de 4 horas (00-04, 04-08... hora UTC).
  - Acciones: dos velas por sesión, "mañana" (9:00-13:00 de Nueva York,
    4 velas de 1 hora) y "tarde" (13:00-16:00, 3 velas).
Una vela agregada solo se usa si está COMPLETA (en vivo, la vela en curso
se descarta).

Filtro de tendencia diaria: un activo solo se puede comprar si el día
ANTERIOR cerró por encima de su media de N días (nunca se usa el cierre
del día en curso, que aún no se conoce).
"""

import pandas as pd

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _agg(df: pd.DataFrame) -> dict:
    return {k: v for k, v in AGG.items() if k in df.columns}


def agregar_cripto(df: pd.DataFrame, horas: int = 4) -> pd.DataFrame:
    grupos = df.groupby(df.index.floor(f"{horas}h"))
    out = grupos.agg(_agg(df))
    completas = grupos.size() == horas
    return out[completas]


def agregar_acciones(df: pd.DataFrame) -> pd.DataFrame:
    ny = df.index.tz_localize("UTC").tz_convert("America/New_York")
    tramo = (ny.hour >= 13).astype(int)                     # 0 = mañana, 1 = tarde
    clave = pd.Series(ny.date, index=df.index).astype(str) + "-" + pd.Series(tramo, index=df.index).astype(str)
    grupos = df.groupby(clave.values)
    out = grupos.agg(_agg(df))
    out.index = grupos.apply(lambda g: g.index[0]).values  # hora de la primera vela del tramo
    n = grupos.size().to_numpy()
    tramos = grupos.apply(lambda g: int(pd.Timestamp(g.index[0]).tz_localize("UTC").tz_convert("America/New_York").hour >= 13)).to_numpy()
    completas = ((tramos == 0) & (n == 4)) | ((tramos == 1) & (n == 3))
    out = out[completas].sort_index()
    out.index.name = "date"
    return out


def agregar(ohlc: dict, mercado: str) -> dict:
    f = agregar_cripto if mercado == "cripto" else agregar_acciones
    return {a: f(df) for a, df in ohlc.items() if not df.empty}


def tendencia_diaria(df: pd.DataFrame, dias: int = 50) -> pd.Series:
    """True si el cierre del día ANTERIOR estaba por encima de su media de N días."""
    dia = df.index.normalize()
    cierre_dia = df["close"].groupby(dia).last()
    alcista = (cierre_dia > cierre_dia.rolling(dias, min_periods=dias).mean()).shift(1)
    return pd.Series(alcista.reindex(dia).to_numpy(), index=df.index).fillna(False).astype(bool)
