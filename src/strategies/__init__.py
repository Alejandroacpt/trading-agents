"""
Biblioteca de estrategias.

Cada estrategia es un diccionario ESTRATEGIA con:
  id, nombre, papel, referencia, publicacion (fecha del paper),
  universo (tickers que usa), inicio ("comun" o "disponibles"),
  senales (función que calcula los pesos objetivo),
  parametros (los del paper), rejilla (variantes para probar robustez),
  max_drawdown_aceptable (según su papel en la cartera).

Para añadir una estrategia nueva: crear su archivo y añadirla a TODAS.
Todas las variantes de TODAS cuentan para el Sharpe deflactado.
"""

from src.strategies import (
    cambio_de_mes,
    cartera,
    crypto_trend,
    dual_momentum,
    faber,
    halloween,
    multi_horizonte,
    rsi2,
    tsmom,
)
from src.strategies.variantes_riesgo import CRIPTO_VOL, FABER_VOL

# Semana 2: biblioteca inicial
INICIALES = [
    tsmom.ESTRATEGIA,
    dual_momentum.ESTRATEGIA,
    faber.ESTRATEGIA,
    rsi2.ESTRATEGIA,
    crypto_trend.ESTRATEGIA,
]

# Semana 3: control de volatilidad, nuevas candidatas y cartera combinada
SEMANA_3 = [
    FABER_VOL,
    CRIPTO_VOL,
    multi_horizonte.ESTRATEGIA,
    cambio_de_mes.ESTRATEGIA,
    halloween.ESTRATEGIA,
    cartera.ESTRATEGIA,
]

TODAS = INICIALES + SEMANA_3
