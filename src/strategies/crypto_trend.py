"""
TENDENCIA EN CRIPTO
-------------------
Referencia: Liu y Tsyvinski (2021), "Risks and Returns of
Cryptocurrency", Review of Financial Studies. Encuentran un momentum
temporal fuerte en las criptomonedas.

Idea: las criptos se mueven en grandes tendencias. Estar dentro cuando
el precio está por encima de su media, y fuera (en liquidez) cuando está
por debajo, evita buena parte de los desplomes del 70-80 %.

Reglas (cada día, para BTC, ETH y SOL):
  - precio > media de N días -> invertido
  - si no -> fuera
El capital se reparte a partes iguales entre las criptos que ya existían
en cada momento (SOL entra en 2020).
"""

import pandas as pd

from src.strategies.indicadores import media_movil, serie_propia

CRIPTOS = ["BTC-USD", "ETH-USD", "SOL-USD"]


def senales(precios: pd.DataFrame, dias: int = 100) -> pd.DataFrame:
    dentro, disponible = {}, {}
    for a in CRIPTOS:
        s = serie_propia(precios, a)
        ma = media_movil(s, dias)
        dentro[a] = (s > ma).astype(float).where(ma.notna())
        disponible[a] = ma.notna().astype(float)
    dentro = pd.DataFrame(dentro).reindex(precios.index).ffill()
    disponible = pd.DataFrame(disponible).reindex(precios.index).ffill().fillna(0)

    n = disponible.sum(axis=1)
    objetivos = dentro.fillna(0).div(n.where(n > 0), axis=0)
    objetivos = objetivos.reindex(columns=precios.columns).fillna(0.0)
    return objetivos.where(n > 0)


ESTRATEGIA = {
    "id": "crypto_trend",
    "nombre": "Tendencia en cripto",
    "papel": "núcleo cripto",
    "referencia": "Liu y Tsyvinski (2021), Risks and Returns of Cryptocurrency, RFS",
    "publicacion": "2021-01-01",
    "universo": CRIPTOS + ["BIL"],
    "inicio": "disponibles",
    "senales": senales,
    "parametros": {"dias": 100},
    "rejilla": [{"dias": d} for d in (20, 50, 100, 150, 200)],
    "max_drawdown_aceptable": 0.60,
    "nota_validacion": (
        "La peor caída (-71 %) va de diciembre de 2017 a marzo de 2019: el filtro de tendencia sale tarde "
        "del desplome de 2018 y recibe varias señales falsas durante el mercado bajista. En la caída de "
        "2021-2022 perdió un 59 %, frente al ~75-80 % de comprar y mantener. Con una volatilidad del 57 % "
        "anual, el agente de riesgo deberá limitar mucho su tamaño en cartera."
    ),
}
