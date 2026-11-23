"""
REGISTRO DE PRUEBAS
-------------------
Cada variante de estrategia que se prueba queda apuntada en
research/registro_pruebas.csv, una sola vez (repetirla con datos más
recientes actualiza sus números, pero no cuenta como prueba nueva).

¿Para qué? Para el Sharpe deflactado: cuantas más ideas se prueban, más
fácil es encontrar una que "funcione" por pura suerte. El listón para
aprobar una estrategia sube con el número TOTAL de pruebas hechas en
toda la vida del proyecto, no solo con las de hoy. Así el sistema no se
engaña a sí mismo por mucho que investigue.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import ROOT

RUTA = ROOT / "research" / "registro_pruebas.csv"
COLUMNAS = ["clave", "estrategia", "familia", "mercado", "parametros", "primera_fecha", "ultima_fecha",
            "sharpe_completo", "sharpe_test", "origen"]


def cargar(ruta: Path = RUTA) -> pd.DataFrame:
    if not ruta.exists():
        return pd.DataFrame(columns=COLUMNAS).astype(object)
    return pd.read_csv(ruta).reindex(columns=COLUMNAS).astype(object)


def numero_pruebas(ruta: Path = RUTA) -> int:
    return len(cargar(ruta))


def registrar(validaciones: list[dict], origen: str, ruta: Path = RUTA) -> int:
    """Añade/actualiza las variantes de cada validación. Devuelve el total de pruebas."""
    reg = cargar(ruta).set_index("clave", drop=False) if ruta.exists() else cargar(ruta)
    hoy = datetime.now(timezone.utc).date().isoformat()
    filas = {}
    for v in validaciones:
        e = v["estrategia"]
        for params, sr in v["sharpes_rejilla"].items():
            clave = f"{e['id']}|{params}"
            filas[clave] = {
                "clave": clave, "estrategia": e["id"], "familia": e.get("familia", e["id"]),
                "mercado": e.get("mercado", "multi"), "parametros": params,
                "primera_fecha": reg.loc[clave, "primera_fecha"] if clave in reg.index else hoy,
                "ultima_fecha": hoy, "sharpe_completo": round(sr, 3),
                "sharpe_test": round(v["sharpes_test_rejilla"].get(params, float("nan")), 3),
                "origen": reg.loc[clave, "origen"] if clave in reg.index else origen,
            }
    nuevas = pd.DataFrame(list(filas.values()), columns=COLUMNAS).set_index("clave", drop=False)
    if len(reg):
        reg = reg.drop(index=[c for c in nuevas.index if c in reg.index])
        reg = pd.concat([reg, nuevas])
    else:
        reg = nuevas
    ruta.parent.mkdir(parents=True, exist_ok=True)
    reg.reset_index(drop=True).sort_values(["primera_fecha", "clave"]).to_csv(ruta, index=False)
    return len(reg)
