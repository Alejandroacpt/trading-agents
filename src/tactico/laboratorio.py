"""
LABORATORIO TÁCTICO
-------------------
Prueba las familias tácticas (velas de 1 hora) en cada mercado táctico
(cripto y acciones) con el simulador de operaciones con stop y el mismo
validador estricto que el resto del sistema, más dos exigencias propias
del corto plazo:
  - periodo de test desde julio de 2024 (el histórico horario es más corto),
  - al menos 100 operaciones (con menos, el resultado no significa nada).
"""

from functools import lru_cache

import pandas as pd

from src.data import horario
from src.tactico.familias import FAMILIAS_TACTICAS
from src.tactico.simulador import Parametros, simular

INICIO_TEST_TACTICO = "2024-07-01"
CALENTAMIENTO = 250


@lru_cache(maxsize=4)
def ohlc_mercado(mercado: str) -> dict:
    conf = horario.cargar_config()
    datos = {}
    for s in conf["mercados"][mercado]["activos"]:
        df = horario.cargar(mercado, s)
        if len(df) > CALENTAMIENTO * 2:
            datos[s] = df
    return datos


def parametros_simulacion(mercado: str, mult_costes: float = 1.0) -> Parametros:
    conf = horario.cargar_config()
    r = conf["riesgo"]
    return Parametros(
        riesgo=r["riesgo_por_operacion"], max_posiciones=r["max_posiciones"], max_peso=r["max_peso_posicion"],
        coste=conf["costes"]["cripto" if mercado == "cripto" else "acciones"] * mult_costes,
        sin_intradia=bool(conf["mercados"][mercado].get("sin_operaciones_intradia", False)),
    )


def experimento(familia_id: str, mercado: str) -> dict:
    fam = FAMILIAS_TACTICAS[familia_id]

    def simular_variante(params: dict, mult_costes: float = 1.0):
        ohlc = ohlc_mercado(mercado)
        senales = fam["funcion"](ohlc, **params)
        return simular(ohlc, senales, parametros_simulacion(mercado, mult_costes), calentamiento=CALENTAMIENTO)

    return {
        "id": f"tac_{familia_id}__{mercado}",
        "nombre": f"{fam['nombre']} · {'Cripto' if mercado == 'cripto' else 'Acciones y ETFs'}",
        "familia": familia_id,
        "mercado": f"tactico_{mercado}",
        "papel": "táctico",
        "referencia": fam["referencia"],
        "publicacion": fam["publicacion"],
        "simular": simular_variante,
        "parametros": fam["parametros"],
        "rejilla": fam["rejilla"],
        "inicio_test": INICIO_TEST_TACTICO,
        "min_operaciones": 100,
        "max_drawdown_aceptable": 0.25,
        "cierres": lambda: pd.DataFrame({a: df["close"] for a, df in ohlc_mercado(mercado).items()}),
        "universo": list(ohlc_mercado(mercado)),
    }


def todos_los_experimentos() -> list[dict]:
    return [experimento(f, m) for m in ("cripto", "acciones") for f in FAMILIAS_TACTICAS if ohlc_mercado(m)]
