"""
ESCÁNERES DE MERCADO
--------------------
Cada día, tras actualizar los datos, calculan:
  1. La señal vigente de cada estrategia activa (qué quiere tener y cuánto).
  2. El estado de cada activo del universo, agrupado por clase
     (renta variable, bonos, materias primas, cripto, forex): los
     "4 escáneres" de la arquitectura, en un solo módulo.
  3. Una explicación en lenguaje claro de cada señal, para las alertas.

Las señales las calcula el mismo código que se ha validado en el
backtest: lo que se opera es exactamente lo que se ha probado.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.config import CONFIG_DIR
from src.strategies import TODAS
from src.strategies.indicadores import media_movil, precios_fin_de_mes, serie_propia, volatilidad_anual

POR_ID = {e["id"]: e for e in TODAS}

NOMBRE_CLASE = {
    "equity": "Renta variable",
    "bonds": "Bonos",
    "commodities": "Materias primas",
    "crypto": "Cripto",
    "forex": "Forex",
    "cash": "Liquidez",
}


def cargar_sistema(path: Path | None = None) -> dict:
    with open(path or CONFIG_DIR / "sistema.yaml", encoding="utf-8") as f:
        sistema = yaml.safe_load(f)
    for e in sistema["estrategias"]:
        if e["id"] not in POR_ID:
            raise ValueError(f"Estrategia desconocida en sistema.yaml: {e['id']}")
    return sistema


def calcular_senales(precios: pd.DataFrame, sistema: dict) -> dict:
    """Señal vigente de cada estrategia activa."""
    salida = {}
    for conf in sistema["estrategias"]:
        e = POR_ID[conf["id"]]
        cols = [c for c in e["universo"] if c in precios.columns]
        p = precios[cols].dropna(how="all")
        objetivos = e["senales"](p, **e["parametros"])
        vigente = objetivos.ffill().iloc[-1].fillna(0.0)
        salida[e["id"]] = {
            "estrategia": e,
            "config": conf,
            "objetivos": objetivos,
            "pesos": vigente[vigente.abs() > 1e-9],
            "fecha_datos": p.index[-1],
        }
    return salida


# ----------------------------------------------------------------------
# Explicaciones
# ----------------------------------------------------------------------

def _fmt(x: float) -> str:
    """Número legible: 62.805 · 1,0908 · 336,32"""
    if abs(x) >= 1000:
        return f"{x:,.0f}".replace(",", ".")
    if abs(x) >= 10:
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{x:.4f}".replace(".", ",")


def explicar(estrategia_id: str, precios: pd.DataFrame, activo: str, dentro: bool) -> tuple[str, str]:
    """Devuelve (por qué, cuándo se saldría) para un activo y una estrategia."""
    e = POR_ID[estrategia_id]
    params = e["parametros"]
    s = serie_propia(precios, activo)
    cierre = s.iloc[-1]

    if estrategia_id in ("crypto_trend", "crypto_trend_vol"):
        dias = params["dias"]
        ma = media_movil(s, dias).iloc[-1]
        lado = "por encima" if cierre > ma else "por debajo"
        motivo = f"{activo} cerró en {_fmt(cierre)} $, {lado} de su media de {dias} días ({_fmt(ma)} $)."
        if estrategia_id == "crypto_trend_vol" and dentro:
            vol = volatilidad_anual(precios[[activo]], 20)[activo].iloc[-1]
            factor = min(1.0, params["vol_objetivo"] / vol) if vol and not np.isnan(vol) else 1.0
            motivo += (f" Su volatilidad del último mes es del {vol:.0%}, así que el tamaño se reduce "
                       f"al {factor:.0%} de lo normal.")
        salida = (f"Se vende si cierra por debajo de su media de {dias} días (hoy en {_fmt(ma)} $)."
                  if dentro else f"Se compraría si cierra por encima de {_fmt(ma)} $.")
        return motivo, salida

    if estrategia_id == "faber":
        meses = params["meses"]
        p_m = precios_fin_de_mes(precios[[activo]])[activo].dropna()
        ma = p_m.tail(meses).mean()
        lado = "por encima" if p_m.iloc[-1] > ma else "por debajo"
        motivo = (f"{activo} cerró el último mes en {_fmt(p_m.iloc[-1])}, {lado} de su media de "
                  f"{meses} meses ({_fmt(ma)}).")
        salida = "Se revisa a fin de mes: se vende si el cierre mensual queda por debajo de esa media."
        return motivo, salida

    if estrategia_id == "multi_horizonte":
        p_m = precios_fin_de_mes(precios[[activo]])[activo].dropna()
        partes, votos = [], 0
        for h in params["horizontes"]:
            r = p_m.iloc[-1] / p_m.iloc[-1 - h] - 1
            votos += r > 0
            partes.append(f"{h} m {r:+.1%}".replace(".", ","))
        n = len(params["horizontes"])
        motivo = (f"Tendencia de {activo}: {votos} de {n} horizontes al alza ({', '.join(partes)}). "
                  f"El tamaño es proporcional a los horizontes alcistas y a la inversa de su volatilidad.")
        salida = "Se revisa a fin de mes: se reduce o se vende cuando los horizontes se vuelven bajistas."
        return motivo, salida

    return f"Señal de {e['nombre']}.", "Según las reglas de la estrategia."


# ----------------------------------------------------------------------
# Vista por clase de activo (los escáneres)
# ----------------------------------------------------------------------

def vista_por_clase(precios: pd.DataFrame, universo: list[dict], senales: dict) -> dict:
    """{clase: [filas]} con el estado de cada activo y qué estrategias lo tienen."""
    vista = {}
    for a in universo:
        t, clase = a["ticker"], a["clase"]
        if clase == "cash" or t not in precios:
            continue
        s = precios[t].dropna()
        if len(s) < 2:
            continue
        en = {sid: float(d["pesos"].get(t, 0.0)) for sid, d in senales.items() if t in d["pesos"].index}
        vista.setdefault(clase, []).append({
            "ticker": t,
            "nombre": a.get("nombre", ""),
            "fecha": s.index[-1].date(),
            "cierre": float(s.iloc[-1]),
            "var_dia": float(s.iloc[-1] / s.iloc[-2] - 1),
            "estrategias": en,
        })
    return vista
