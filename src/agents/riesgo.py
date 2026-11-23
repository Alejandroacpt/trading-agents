"""
AGENTE DE RIESGO Y CAPITAL
--------------------------
Decide CUÁNTO capital recibe cada estrategia y cada activo. Las
estrategias solo dicen "qué" quieren; el tamaño lo decide este agente.

Pasos:
1. Paridad de riesgo entre estrategias: cada una recibe capital en
   proporción inversa a su volatilidad del último año, multiplicada por
   su peso de riesgo (las de observación, la mitad).
2. Topes: cripto como máximo el 25 % del capital; ningún activo más del 20 %.
3. Kill-switch: si la cartera virtual cae un 15 % desde su máximo, la
   exposición se reduce a la mitad; si cae un 25 %, todo a liquidez.
4. Cartera ejecutable: con poco capital, solo las posiciones más grandes
   (máximo 5) y de al menos 50 €; el resto queda en liquidez.
"""

import numpy as np
import pandas as pd


def rent_aproximada(objetivos: pd.DataFrame, precios: pd.DataFrame) -> pd.Series:
    """Rentabilidad diaria aproximada de una estrategia (sin costes),
    solo para estimar su volatilidad."""
    pesos = objetivos.reindex(precios.index).ffill().fillna(0).shift(1)
    r = precios.reindex(columns=pesos.columns).ffill().pct_change().fillna(0)
    rent = (pesos * r).sum(axis=1)
    empezado = objetivos.reindex(precios.index).notna().any(axis=1).cummax()
    return rent.where(empezado)


def reparto_estrategias(senales: dict, precios: pd.DataFrame, sistema: dict) -> pd.Series:
    """Fracción del capital asignada a cada estrategia."""
    ventana = sistema["riesgo"]["ventana_volatilidad"]
    vols, pesos_riesgo = {}, {}
    for sid, d in senales.items():
        r = rent_aproximada(d["objetivos"], precios).dropna().tail(ventana)
        vols[sid] = r.std() * np.sqrt(365) if len(r) > 20 else np.nan
        pesos_riesgo[sid] = d["config"].get("peso_riesgo", 1.0)
    vols = pd.Series(vols)
    vols = vols.fillna(vols.max() if vols.notna().any() else 0.2)
    bruto = pd.Series(pesos_riesgo) / vols.replace(0, np.nan)
    reparto = (bruto / bruto.sum()).fillna(0)

    # Tope a cripto (las estrategias cuyo universo es solo cripto)
    tope = sistema["riesgo"]["tope_cripto"]
    cripto = [sid for sid, d in senales.items() if _es_cripto(d["estrategia"])]
    exceso = max(0.0, reparto[cripto].sum() - tope) if cripto else 0.0
    if exceso > 0:
        reparto[cripto] *= tope / reparto[cripto].sum()
        otros = [s for s in reparto.index if s not in cripto]
        if otros:
            reparto[otros] += exceso * reparto[otros] / reparto[otros].sum()
    return reparto


def _es_cripto(estrategia: dict) -> bool:
    return all(t.endswith("-USD") or t == "BIL" for t in estrategia["universo"])


def cartera_modelo(senales: dict, reparto: pd.Series, sistema: dict, factor_kill: float = 1.0) -> pd.Series:
    """Peso final de cada activo, sumando lo que pide cada estrategia."""
    total = pd.Series(dtype=float)
    for sid, d in senales.items():
        total = total.add(d["pesos"] * reparto[sid], fill_value=0.0)
    total = total[total.abs() > 1e-9]

    tope = sistema["riesgo"]["tope_por_activo"]
    total = total.clip(upper=tope)
    return (total * factor_kill).sort_values(ascending=False)


def cartera_ejecutable(modelo: pd.Series, sistema: dict) -> pd.Series:
    """Versión operable con poco capital.

    Se queda con las N posiciones mayores del modelo y las reescala para
    que la exposición total sea la misma que la del modelo (el riesgo no
    baja por tener menos posiciones), sin pasar del tope por activo.
    Las que, aun reescaladas, no llegan al importe mínimo se descartan.
    """
    conf = sistema["cartera_ejecutable"]
    capital = sistema["capital_eur"]
    tope = sistema["riesgo"]["tope_por_activo"]
    minimo = conf["minimo_posicion_eur"] / capital
    objetivo = modelo.clip(lower=0).sum()

    elegidas = modelo[modelo > 0].sort_values(ascending=False).head(conf["max_posiciones"])
    escaladas = elegidas
    for _ in range(conf["max_posiciones"]):
        if elegidas.empty:
            break
        escaladas = (elegidas * objetivo / elegidas.sum()).clip(upper=tope)
        validas = escaladas[escaladas >= minimo - 1e-12]
        if len(validas) == len(elegidas):
            break
        elegidas = elegidas[validas.index]
    if elegidas.empty:
        return pd.Series(dtype=float)
    return escaladas.sort_values(ascending=False)


def factor_kill_switch(drawdown: float, sistema: dict) -> tuple[float, str]:
    """Multiplicador de exposición según la caída de la cartera virtual."""
    ks = sistema["riesgo"]["kill_switch"]
    if drawdown <= -ks["pausa"]:
        return 0.0, "PAUSA"
    if drawdown <= -ks["reducir_a_la_mitad"]:
        return 0.5, "MITAD"
    return 1.0, "NORMAL"
