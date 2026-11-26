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
from src.tactico.velas import agregar

INICIO_TEST_TACTICO = "2024-07-01"

# Mercados solo de investigación (no los opera el sistema):
#   apalancados: ETFs x3 de config/investigacion.yaml, tratados como acciones
#                (mismas velas de media sesión, costes y norma PDT).
#   forex:       pares de divisas de Dukascopy (config/investigacion.yaml -> forex),
#                24 h como la cripto (velas de 4 h), costes de forex, sin PDT.
# Uso: experimento("momentum_tendencia", "apalancados") / experimento(..., "forex")
MERCADOS_INVESTIGACION = {"apalancados": "acciones", "forex": "forex"}


def mercado_base(mercado: str) -> str:
    return MERCADOS_INVESTIGACION.get(mercado, mercado)


def tipo_velas(mercado: str) -> str:
    """Cómo se agregan las velas: 'cripto' (bloques de 4 h, 24 h al día) o 'acciones' (media sesión)."""
    return "acciones" if mercado_base(mercado) == "acciones" else "cripto"


def _activos(mercado: str, extra: bool) -> list[str]:
    conf = horario.cargar_config()
    if mercado == "forex":
        from src.data import forex
        return forex.cargar_config()["pares"]
    if mercado in MERCADOS_INVESTIGACION:
        return horario.activos_investigacion(mercado_base(mercado))
    activos = list(conf["mercados"][mercado]["activos"])
    if extra:
        activos += [a for a in horario.activos_investigacion(mercado) if a not in activos]
    return activos
CALENTAMIENTO = 250


@lru_cache(maxsize=8)
def ohlc_mercado(mercado: str, extra: bool = False) -> dict:
    """Velas de 1 hora del universo táctico; con extra=True, también los
    activos solo de investigación (config/investigacion.yaml)."""
    datos = {}
    base = mercado_base(mercado)
    for s in _activos(mercado, extra):
        df = horario.cargar(base, s)
        if len(df) > CALENTAMIENTO * 2:
            datos[s] = df
    return datos


@lru_cache(maxsize=8)
def ohlc_agregado(mercado: str, extra: bool = False) -> dict:
    """Velas de 4 h (cripto) o de media sesión (acciones)."""
    return agregar(ohlc_mercado(mercado, extra), tipo_velas(mercado))


def velas_de(familia: dict, mercado: str) -> dict:
    return ohlc_agregado(mercado) if familia.get("velas") == "4h" else ohlc_mercado(mercado)


def parametros_simulacion(mercado: str, mult_costes: float = 1.0) -> Parametros:
    conf = horario.cargar_config()
    r = conf["riesgo"]
    base = mercado_base(mercado)
    clave = base if base in ("cripto", "forex") else "acciones"
    return Parametros(
        riesgo=r["riesgo_por_operacion"], max_posiciones=r["max_posiciones"], max_peso=r["max_peso_posicion"],
        coste=conf["costes"][clave] * mult_costes,
        coste_limitada=conf["costes"].get(f"{clave}_limitada", conf["costes"][clave]) * mult_costes,
        sin_intradia=bool(conf["mercados"].get(base, {}).get("sin_operaciones_intradia", False)),
        financiacion_corto=float(conf["costes"].get(f"financiacion_corto_{clave}", 0.0)),
    )


ETIQUETA = {"cripto": "Cripto", "acciones": "Acciones y ETFs", "apalancados": "ETFs apalancados x3",
            "forex": "Forex (Dukascopy)"}


def experimento(familia_id: str, mercado: str) -> dict:
    fam = FAMILIAS_TACTICAS[familia_id]

    calentamiento = 120 if fam.get("velas") == "4h" else CALENTAMIENTO

    def simular_variante(params: dict, mult_costes: float = 1.0):
        ohlc = velas_de(fam, mercado)
        senales = fam["funcion"](ohlc, **params)
        return simular(ohlc, senales, parametros_simulacion(mercado, mult_costes), calentamiento=calentamiento)

    return {
        "id": f"tac_{familia_id}__{mercado}",
        "nombre": (f"{fam['nombre']} · {ETIQUETA.get(mercado, mercado)}"
                   .replace("(4 h) · Acciones y ETFs", "(media sesión) · Acciones y ETFs")
                   .replace("(4 h) · ETFs apalancados x3", "(media sesión) · ETFs apalancados x3")),
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
        "cierres": lambda: pd.DataFrame({a: df["close"] for a, df in velas_de(fam, mercado).items()}),
        "universo": list(ohlc_mercado(mercado)),
    }


def todos_los_experimentos() -> list[dict]:
    # Una familia con campo "mercados" solo se prueba en esos mercados (p. ej. los cortos en cripto),
    # y con "laboratorio": False no se prueba (rechazada en el cribado: no sumar pruebas sin motivo).
    return [experimento(f, m) for m in ("cripto", "acciones") for f, fam in FAMILIAS_TACTICAS.items()
            if ohlc_mercado(m) and m in fam.get("mercados", (m,)) and fam.get("laboratorio", True)]


def simular_en_vivo(estrategia_id: str, inicio_vivo: str):
    """Repite una estrategia táctica activa con los datos reales desde su puesta en
    marcha. Los indicadores se calculan con TODO el histórico (igual que en el
    backtest); solo cuentan las entradas desde inicio_vivo.
    Devuelve (resultado, familia, mercado)."""
    familia, mercado = estrategia_id.removeprefix("tac_").split("__")
    fam = FAMILIAS_TACTICAS[familia]
    ohlc = velas_de(fam, mercado)
    desde = pd.Timestamp(inicio_vivo)
    senales = fam["funcion"](ohlc, **fam["parametros"])
    for s in senales.values():
        s.loc[s.index < desde, "entrada"] = False
    return simular(ohlc, senales, parametros_simulacion(mercado)), fam, mercado
