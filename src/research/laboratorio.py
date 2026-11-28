"""
LABORATORIO DE ESTRATEGIAS
--------------------------
Prueba TODAS las familias de estrategias en CADA mercado por separado,
con todo el histórico disponible y el mismo validador estricto que la
biblioteca principal. Se ejecuta cada semana.

Para cada mercado responde: ¿qué tipo de estrategia ha funcionado de
verdad aquí, con costes, fuera de muestra y después de publicarse?

Resultados:
  - Clasificación por mercado (reports/laboratorio/ultimo.md).
  - Propuestas: experimentos APROBADOS que no están operando. El
    laboratorio nunca cambia por su cuenta las estrategias en vivo: las
    propone y la decisión es de Alejandro.
  - Cada variante probada queda en el registro de pruebas, que endurece
    el listón del Sharpe deflactado para todo el sistema.
"""

from functools import partial

from src.research.familias import FAMILIAS

MERCADOS = {
    "renta_variable": {"nombre": "Renta variable", "activos": ["SPY", "QQQ", "VGK", "EWJ", "EEM"],
                       "largo_corto": False, "max_dd": 0.30, "min_activos": 4},
    "bonos": {"nombre": "Bonos", "activos": ["IEF", "TLT"],
              "largo_corto": False, "max_dd": 0.25, "min_activos": 2},
    "materias_primas": {"nombre": "Materias primas", "activos": ["GLD", "SLV", "USO", "DBC"],
                        "largo_corto": False, "max_dd": 0.35, "min_activos": 4},
    "cripto": {"nombre": "Cripto", "activos": ["BTC-USD", "ETH-USD", "SOL-USD"],
               "largo_corto": False, "max_dd": 0.60, "min_activos": 1},
    "forex": {"nombre": "Forex", "activos": ["EURUSD=X", "GBPUSD=X", "JPY=X", "AUDUSD=X", "CHF=X"],
              "largo_corto": True, "max_dd": 0.20, "min_activos": 4},
}

# Mercados SOLO para el investigador: mezclan clases de activo (p. ej. acciones
# + bonos de refugio). El laboratorio semanal no los recorre: solo se prueban
# las familias que los declaran en su campo "mercados", con el cribado.
MERCADOS_INVESTIGACION = {
    # VAA-G4 con los ETFs que ya descargamos: SPY, VGK (en lugar de EFA/VEA),
    # EEM y IEF (en lugar de AGG/BND) como ofensivos; IEF y BIL (en lugar de SHY) de refugio.
    "multiactivo": {"nombre": "Multiactivo (acciones + bonos)", "activos": ["SPY", "VGK", "EEM", "IEF"],
                    "largo_corto": False, "max_dd": 0.30, "min_activos": 4},
}


def experimento(familia_id: str, mercado_id: str) -> dict:
    """Construye una 'estrategia' validable: familia aplicada a un mercado."""
    fam, mer = FAMILIAS[familia_id], {**MERCADOS, **MERCADOS_INVESTIGACION}[mercado_id]
    funcion = partial(fam["funcion"], activos=mer["activos"], largo_corto=mer["largo_corto"])

    def senales(precios, **params):
        return funcion(precios, **params)

    return {
        "id": f"lab_{familia_id}__{mercado_id}",
        "nombre": f"{fam['nombre']} · {mer['nombre']}",
        "familia": familia_id,
        "mercado": mercado_id,
        "papel": "laboratorio",
        "referencia": fam["referencia"],
        "publicacion": fam["publicacion"],
        "universo": mer["activos"] + ["BIL"],
        "inicio": "disponibles",
        "min_activos": mer["min_activos"],
        "senales": senales,
        "parametros": fam["parametros"],
        "rejilla": fam["rejilla"],
        "max_drawdown_aceptable": mer["max_dd"],
    }


def todos_los_experimentos() -> list[dict]:
    """Cada familia en cada mercado donde tiene sentido (por defecto, todos)."""
    return [experimento(f, m) for m in MERCADOS for f, fam in FAMILIAS.items()
            if m in fam.get("mercados", MERCADOS)]


def mercado_de_estrategia(estrategia: dict) -> set[str]:
    """Mercados que toca una estrategia de la biblioteca (para comparar)."""
    activos = set(estrategia["universo"]) - {"BIL"}
    return {m for m, d in MERCADOS.items() if activos & set(d["activos"])}
