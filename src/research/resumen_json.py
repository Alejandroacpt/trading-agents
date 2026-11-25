"""
Resúmenes en JSON de las validaciones (laboratorios y validador mensual)
para el panel web. Solo cifras y veredictos: nada de configuración ni claves.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, 4)


def resumen(validaciones: list[dict], tipo: str) -> list[dict]:
    filas = []
    for v in validaciones:
        e, p, vd = v["estrategia"], v["periodos"], v.get("veredicto") or {}
        c, t = p.get("completo", {}), p.get("test", {})
        spy = v.get("spy") or {}
        filas.append({
            "id": e.get("id"), "nombre": e.get("nombre"), "mercado": e.get("mercado"), "tipo": tipo,
            "veredicto": vd.get("decision"), "fallos": vd.get("fallos", []),
            "sharpe": _num(c.get("sharpe")), "sharpe_test": _num(t.get("sharpe")),
            "cagr": _num(c.get("cagr")), "max_dd": _num(c.get("max_drawdown")),
            "operaciones": c.get("operaciones"), "aciertos": _num(c.get("aciertos")),
            "cagr_test": _num(spy.get("cagr")), "cagr_spy_test": _num(spy.get("cagr_spy")),
        })
    return filas


def guardar(validaciones: list[dict], tipo: str, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {"fecha": datetime.now(timezone.utc).isoformat(timespec="minutes"), "tipo": tipo,
             "estrategias": resumen(validaciones, tipo)}
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
