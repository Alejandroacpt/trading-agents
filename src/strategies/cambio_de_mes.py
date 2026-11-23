"""
EFECTO CAMBIO DE MES (TURN OF THE MONTH)
----------------------------------------
Referencias: Lakonishok y Smidt (1988), "Are Seasonal Anomalies Real?
A Ninety-Year Perspective", Review of Financial Studies; Xu y McConnell
(2008), "The Turn-of-the-Month Effect", Journal of Financial Economics
(lo confirman en 30 países).

Idea: una parte desproporcionada de la subida de la bolsa se concentra
en torno al cambio de mes (último día y primeros días del siguiente),
probablemente por los flujos de nóminas y planes de pensiones.

Reglas:
  - Estar comprado desde el cierre de N sesiones antes del fin de mes
    hasta el cierre de la M-ésima sesión del mes siguiente.
  - El resto del mes, en liquidez.
  - Cada índice tiene reservada su parte del capital (1/5).

El calendario de sesiones se conoce por adelantado, así que las órdenes
se pueden preparar con antelación (no hay sesgo de anticipación).
"""

import numpy as np
import pandas as pd

from src.strategies.indicadores import serie_propia

INDICES = ["SPY", "QQQ", "VGK", "EWJ", "EEM"]


def senales(precios: pd.DataFrame, antes: int = 1, despues: int = 3) -> pd.DataFrame:
    objetivos = pd.DataFrame(index=precios.index, columns=precios.columns, dtype=float)
    reparto = 1 / len(INDICES)

    for a in INDICES:
        s = serie_propia(precios, a)
        idx = s.index
        mes = idx.to_period("M")
        # posición de cada sesión dentro de su mes: 1, 2, 3... y contando desde el final: -1 (última), -2...
        pos = pd.Series(1, index=idx).groupby(mes).cumsum().to_numpy()
        n_mes = pd.Series(1, index=idx).groupby(mes).transform("sum").to_numpy()
        desde_final = pos - n_mes - 1          # -1 = última sesión del mes

        # Queremos GANAR la rentabilidad de las sesiones -antes+1 ... +despues.
        # Con el motor (señal en t -> compra al cierre de t+1 -> gana desde t+2),
        # la señal de "dentro" se emite 2 sesiones antes del primer día a ganar.
        en_ventana = (desde_final >= -antes) | (pos <= despues)
        senal = np.roll(en_ventana, -2)        # adelantar 2 sesiones
        senal[-2:] = en_ventana[-2:]
        objetivos[a] = pd.Series(np.where(senal, reparto, 0.0), index=idx).reindex(precios.index).ffill()

    for a in precios.columns:
        if a not in INDICES:
            objetivos[a] = 0.0
    return objetivos.where(objetivos[INDICES].notna().all(axis=1))


ESTRATEGIA = {
    "id": "cambio_de_mes",
    "nombre": "Efecto cambio de mes",
    "papel": "satélite",
    "referencia": "Lakonishok y Smidt (1988), RFS; Xu y McConnell (2008), The Turn-of-the-Month Effect, JFE",
    "publicacion": "1988-10-01",
    "universo": INDICES + ["BIL"],
    "inicio": "comun",
    "senales": senales,
    "parametros": {"antes": 1, "despues": 3},
    "rejilla": [{"antes": a, "despues": d} for a in (1, 2) for d in (2, 3, 4)],
    "max_drawdown_aceptable": 0.25,
}
