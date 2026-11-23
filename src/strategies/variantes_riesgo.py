"""
Variantes con control de volatilidad de las estrategias que quedaron
en OBSERVACIÓN en la primera validación (23 nov 2026).

Parámetros fijados ANTES de ver resultados:
  - Cripto: volatilidad objetivo por activo 40 % (rejilla 30/40/60 %),
    media de 50/100/200 días.
  - Faber: volatilidad objetivo por activo 15 % (rejilla 10/15/20 %),
    media de 8/10/12 meses.
"""

from src.strategies import crypto_trend, faber
from src.strategies.control_volatilidad import con_control

CRIPTO_VOL = con_control(
    crypto_trend.ESTRATEGIA,
    id_="crypto_trend_vol",
    nombre="Tendencia en cripto + control de volatilidad",
    vol_defecto=0.40,
    vols=(0.30, 0.40, 0.60),
    rejilla_base=[{"dias": d} for d in (50, 100, 200)],
    max_dd=0.60,
    nota=(
        "El control de volatilidad reduce la exposición media del 57 % al 36 % y la peor caída de -71 % a -40 %, "
        "con un Sharpe casi igual (1,28 frente a 1,34). Es la primera estrategia aprobada del sistema."
    ),
)

FABER_VOL = con_control(
    faber.ESTRATEGIA,
    id_="faber_vol",
    nombre="Filtro de 10 meses + control de volatilidad",
    vol_defecto=0.15,
    vols=(0.10, 0.15, 0.20),
    rejilla_base=[{"meses": m} for m in (8, 10, 12)],
    max_dd=0.25,
    nota=(
        "Aquí el control de volatilidad resta en vez de sumar: Faber ya sale de los activos en caída, y recortar "
        "además por volatilidad deja la cartera demasiado infrainvertida en las recuperaciones."
    ),
)
