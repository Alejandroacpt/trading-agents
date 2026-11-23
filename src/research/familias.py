"""
FAMILIAS DE ESTRATEGIAS
-----------------------
Una "familia" es una idea de trading genérica que se puede aplicar a
cualquier grupo de activos. El laboratorio la prueba en cada mercado
por separado (renta variable, bonos, materias primas, cripto, forex).

Cómo añadir una familia (lo hace el agente investigador):
  1. Escribir su función de señales: recibe (precios, activos, largo_corto,
     **parametros) y devuelve pesos objetivo (ver las de abajo).
  2. Añadirla a FAMILIAS con su referencia, fecha de publicación y una
     rejilla de parámetros FIJADA ANTES de ver ningún resultado.
  3. Escribir su ficha en research/fichas/<id>.md.

Reglas comunes a todas las familias:
  - Reparto entre activos inverso a la volatilidad (recalculado cada
    semana): los activos tranquilos pesan más, para igualar el riesgo.
  - Sin apalancamiento: la suma de pesos nunca pasa del 100 %.
  - En forex se permite ir corto (comprar EUR/USD = vender dólares, así
    que "solo largos" no tiene sentido); en el resto, solo largos.
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import media_movil, precios_fin_de_mes, rsi, serie_propia, volatilidad_anual


# ----------------------------------------------------------------------
# Utilidades comunes
# ----------------------------------------------------------------------

def _pesos_riesgo(precios: pd.DataFrame, activos: list[str]) -> pd.DataFrame:
    """Peso de cada activo inverso a su volatilidad, recalculado cada semana."""
    vol = volatilidad_anual(precios[activos])
    semanas = vol.index.to_series().groupby(vol.index.to_period("W")).max().values
    es_fin_semana = pd.Series(vol.index.isin(semanas), index=vol.index)
    inversa = (1 / vol).where(es_fin_semana, axis=0).ffill()
    return inversa.div(inversa.sum(axis=1), axis=0)


def _a_objetivos(senal: pd.DataFrame, precios: pd.DataFrame, activos: list[str]) -> pd.DataFrame:
    """Combina la señal (-1, 0, 1 o fracción) con el reparto por riesgo."""
    pesos = _pesos_riesgo(precios, activos)
    obj = (senal.reindex(precios.index).ffill() * pesos).reindex(columns=precios.columns)
    obj = obj.fillna(0.0).where(senal.reindex(precios.index).ffill().notna().any(axis=1), axis=0)
    # Solo se opera cuando algo cambia de verdad (señal) o en el recálculo semanal
    cambia = obj.fillna(0).diff().abs().sum(axis=1) > 1e-9
    return obj.where(cambia | (obj.notna().any(axis=1) & ~obj.shift().notna().any(axis=1)), axis=0)


def _senal_diaria(precios, activos, funcion) -> pd.DataFrame:
    """Aplica una función de señal a la serie propia de cada activo."""
    salida = {}
    for a in activos:
        s = serie_propia(precios, a)
        if len(s) > 30:
            salida[a] = funcion(s)
    return pd.DataFrame(salida).reindex(precios.index).ffill()


# ----------------------------------------------------------------------
# Familias
# ----------------------------------------------------------------------

def tendencia_media(precios, activos, largo_corto=False, dias=100):
    """Comprado si el precio está por encima de su media de N días."""
    def f(s):
        ma = media_movil(s, dias)
        senal = np.sign(s - ma).where(ma.notna())
        return senal if largo_corto else senal.clip(lower=0)
    return _a_objetivos(_senal_diaria(precios, activos, f), precios, activos)


def ruptura_canal(precios, activos, largo_corto=False, dias=50):
    """Canal de Donchian (las 'tortugas'): entra al superar el máximo de N
    días y sale al perder el mínimo de N/2 días (simétrico en corto)."""
    salida_dias = max(5, dias // 2)

    def f(s):
        maximo = s.shift(1).rolling(dias).max()
        minimo = s.shift(1).rolling(dias).min()
        max_sal = s.shift(1).rolling(salida_dias).max()
        min_sal = s.shift(1).rolling(salida_dias).min()
        pos, estado = np.full(len(s), np.nan), 0
        for i in range(len(s)):
            if np.isnan(maximo.iloc[i]):
                continue
            p = s.iloc[i]
            if estado == 0:
                if p > maximo.iloc[i]:
                    estado = 1
                elif largo_corto and p < minimo.iloc[i]:
                    estado = -1
            elif estado == 1 and p < min_sal.iloc[i]:
                estado = 0
            elif estado == -1 and p > max_sal.iloc[i]:
                estado = 0
            pos[i] = estado
        return pd.Series(pos, index=s.index)
    return _a_objetivos(_senal_diaria(precios, activos, f), precios, activos)


def momentum_mensual(precios, activos, largo_corto=False, meses=12):
    """Cada fin de mes: comprado si el rendimiento de N meses es positivo."""
    p_m = precios_fin_de_mes(precios[activos])
    senal = np.sign(p_m / p_m.shift(meses) - 1).where(p_m.shift(meses).notna())
    if not largo_corto:
        senal = senal.clip(lower=0)
    return _a_objetivos(senal, precios, activos)


def multi_horizonte(precios, activos, largo_corto=False, horizontes=(1, 3, 12)):
    """Cada fin de mes: posición proporcional a los horizontes alcistas
    (en largo-corto: votos alcistas menos bajistas)."""
    p_m = precios_fin_de_mes(precios[activos])
    votos = [np.sign(p_m / p_m.shift(h) - 1).where(p_m.shift(h).notna()) for h in horizontes]
    senal = sum(votos) / len(horizontes)
    if not largo_corto:
        senal = sum(v.clip(lower=0) for v in votos) / len(horizontes)
    return _a_objetivos(senal, precios, activos)


def reversion_rsi2(precios, activos, largo_corto=False, umbral=10):
    """Compra caídas fuertes (RSI de 2 días < umbral) dentro de una tendencia
    alcista (precio > media de 200) y vende al rebotar (precio > media de 5)."""
    def f(s):
        ma200, ma5, r = media_movil(s, 200), media_movil(s, 5), rsi(s, 2)
        pos, dentro = np.full(len(s), np.nan), False
        for i in range(len(s)):
            if np.isnan(ma200.iloc[i]) or np.isnan(r.iloc[i]):
                continue
            if not dentro and s.iloc[i] > ma200.iloc[i] and r.iloc[i] < umbral:
                dentro = True
            elif dentro and s.iloc[i] > ma5.iloc[i]:
                dentro = False
            pos[i] = 1.0 if dentro else 0.0
        return pd.Series(pos, index=s.index)
    return _a_objetivos(_senal_diaria(precios, activos, f), precios, activos)


def carry_divisas(precios, activos, largo_corto=True, modo="signo"):
    """Carry en forex: comprar las divisas con tipos de interés altos y vender
    las de tipos bajos (cada fin de mes).
      - modo "signo": largo en cada par si su diferencial es positivo, corto si es negativo.
      - modo "ranking": largo en los 2 pares con más carry, corto en los 2 con menos.
      - modo "con_tendencia": como "signo", pero solo si la tendencia de 3 meses acompaña.
    Requiere data/macro/tipos_3m.csv (se descarga semanalmente de FRED)."""
    from src.data.macro import cargar_tipos, diferencial_diario

    tipos = cargar_tipos()
    if tipos.empty:
        return pd.DataFrame(np.nan, index=precios.index, columns=precios.columns)
    p_m = precios_fin_de_mes(precios[activos])
    dif = diferencial_diario(tipos, p_m.index).reindex(columns=activos)
    if modo == "ranking":
        rango = dif.rank(axis=1)
        n = dif.notna().sum(axis=1)
        senal = rango.gt(n - 2, axis=0).astype(float) - (rango <= 2).astype(float)
        senal = senal.where(dif.notna())
    else:
        senal = np.sign(dif)
        if modo == "con_tendencia":
            tendencia = np.sign(p_m / p_m.shift(3) - 1)
            senal = senal.where(senal == tendencia, 0.0)
    if not largo_corto:
        senal = senal.clip(lower=0)
    return _a_objetivos(senal, precios, activos)


# ----------------------------------------------------------------------
# Catálogo (las rejillas se fijan ANTES de ver resultados)
# ----------------------------------------------------------------------

FAMILIAS = {
    "tendencia_media": {
        "nombre": "Tendencia por media móvil",
        "funcion": tendencia_media,
        "referencia": "Faber (2007); Liu y Tsyvinski (2021) en cripto; Brock, Lakonishok y LeBaron (1992)",
        "publicacion": "1992-12-01",
        "parametros": {"dias": 100},
        "rejilla": [{"dias": d} for d in (50, 100, 200)],
        "anadida": "2026-11-23",
    },
    "ruptura_canal": {
        "nombre": "Ruptura de canal (Donchian)",
        "funcion": ruptura_canal,
        "referencia": "Donchian; Faith (2007), Way of the Turtle; Wilcox y Crittenden (2005)",
        "publicacion": "2005-06-01",
        "parametros": {"dias": 50},
        "rejilla": [{"dias": d} for d in (20, 50, 100)],
        "anadida": "2026-11-23",
    },
    "momentum_mensual": {
        "nombre": "Momentum temporal mensual",
        "funcion": momentum_mensual,
        "referencia": "Moskowitz, Ooi y Pedersen (2012), Time Series Momentum, JFE",
        "publicacion": "2012-05-01",
        "parametros": {"meses": 12},
        "rejilla": [{"meses": m} for m in (3, 6, 12)],
        "anadida": "2026-11-23",
    },
    "multi_horizonte": {
        "nombre": "Tendencia multi-horizonte",
        "funcion": multi_horizonte,
        "referencia": "Hurst, Ooi y Pedersen (2017), A Century of Evidence on Trend-Following Investing, JPM",
        "publicacion": "2017-09-01",
        "parametros": {"horizontes": (1, 3, 12)},
        "rejilla": [{"horizontes": h} for h in ((1, 3, 12), (3, 6, 12), (1, 3, 6, 12))],
        "anadida": "2026-11-23",
    },
    "reversion_rsi2": {
        "nombre": "Reversión a la media (RSI-2)",
        "funcion": reversion_rsi2,
        "referencia": "Connors y Alvarez (2008), Short Term Trading Strategies That Work",
        "publicacion": "2008-01-01",
        "parametros": {"umbral": 10},
        "rejilla": [{"umbral": u} for u in (5, 10, 20)],
        "anadida": "2026-11-23",
    },
    "carry_divisas": {
        "nombre": "Carry de divisas",
        "funcion": carry_divisas,
        "referencia": "Koijen, Moskowitz, Pedersen y Vrugt (2018), Carry, JFE; Lustig, Roussanov y Verdelhan (2011), RFS",
        "publicacion": "2011-11-01",
        "parametros": {"modo": "signo"},
        "rejilla": [{"modo": m} for m in ("signo", "ranking", "con_tendencia")],
        "mercados": ["forex"],   # solo tiene sentido en divisas
        "anadida": "2026-11-23",
    },
}
