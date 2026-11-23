"""
Biblioteca de estrategias.

Cada estrategia es un diccionario ESTRATEGIA con:
  id, nombre, papel, referencia, publicacion (fecha del paper),
  universo (tickers que usa), inicio ("comun" o "disponibles"),
  senales (función que calcula los pesos objetivo),
  parametros (los del paper), rejilla (variantes para probar robustez),
  max_drawdown_aceptable (según su papel en la cartera).

Para añadir una estrategia nueva: crear su archivo y añadirla a TODAS.
"""

from src.strategies import crypto_trend, dual_momentum, faber, rsi2, tsmom

TODAS = [
    tsmom.ESTRATEGIA,
    dual_momentum.ESTRATEGIA,
    faber.ESTRATEGIA,
    rsi2.ESTRATEGIA,
    crypto_trend.ESTRATEGIA,
]
