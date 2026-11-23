"""
CARTERA VIRTUAL
---------------
Lleva la cuenta de cómo le iría a quien siguiera las alertas al pie de
la letra con el capital de referencia (sin dinero real). Sirve para:
  - el kill-switch (necesita saber cuánto ha caído la cartera),
  - comparar más adelante el resultado en vivo con el backtest.

Se guarda en state/estado.json, que el pipeline sube al repositorio en
cada ejecución. Es una aproximación: supone que las órdenes se ejecutan
al último cierre conocido y cobra los mismos costes que el backtest.
En la semana 5 se complementará con la ejecución en Alpaca paper.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.backtest.engine import COSTES_POR_CLASE
from src.config import ROOT

RUTA_ESTADO = ROOT / "state" / "estado.json"


def cargar(ruta: Path = RUTA_ESTADO) -> dict | None:
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar(estado: dict, ruta: Path = RUTA_ESTADO) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def ultimos_cierres(precios: pd.DataFrame) -> dict:
    return {c: float(precios[c].dropna().iloc[-1]) for c in precios.columns if precios[c].notna().any()}


def actualizar_valor(estado: dict | None, cierres: dict, capital_inicial: float) -> dict:
    """Revaloriza la cartera que se tenía desde la última ejecución.

    Devuelve {"valor", "maximo", "drawdown", "pesos_derivados", "inicio", "historial"}.
    """
    if not estado:
        return {"valor": capital_inicial, "maximo": capital_inicial, "drawdown": 0.0,
                "pesos_derivados": {}, "inicio": datetime.now(timezone.utc).date().isoformat(), "historial": []}

    v = estado["virtual"]
    pesos = estado.get("cartera", {})
    refs = estado.get("precios_ref", {})
    rent_total, valores = 0.0, {}
    for t, w in pesos.items():
        r = cierres.get(t, refs.get(t)) / refs[t] - 1 if t in refs and refs[t] else 0.0
        rent_total += w * r
        valores[t] = w * (1 + r)
    valor = v["valor"] * (1 + rent_total)
    derivados = {t: x / (1 + rent_total) for t, x in valores.items()} if (1 + rent_total) > 0 else {}
    maximo = max(v["maximo"], valor)
    return {"valor": valor, "maximo": maximo, "drawdown": valor / maximo - 1,
            "pesos_derivados": derivados, "inicio": v["inicio"], "historial": v.get("historial", [])}


def coste_cambio(antes: dict, despues: dict, clases: dict) -> float:
    """Coste (tanto por uno del capital) de pasar de una cartera a otra."""
    activos = set(antes) | set(despues)
    return sum(abs(despues.get(a, 0) - antes.get(a, 0)) * COSTES_POR_CLASE.get(clases.get(a, "equity"), 0.001)
               for a in activos)


def nuevo_estado(virtual: dict, cartera: dict, cierres: dict, clases: dict, kill: str,
                 detalle: dict, fecha_datos: str) -> dict:
    """Aplica los cambios de cartera (descontando costes) y prepara el estado a guardar."""
    coste = coste_cambio(virtual["pesos_derivados"], cartera, clases)
    valor = virtual["valor"] * (1 - coste)
    maximo = max(virtual["maximo"], valor)
    hoy = datetime.now(timezone.utc).date().isoformat()
    historial = [h for h in virtual["historial"] if h[0] != hoy] + [[hoy, round(valor, 2)]]
    return {
        "actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "fecha_datos": fecha_datos,
        "cartera": {t: round(w, 6) for t, w in cartera.items()},
        "precios_ref": {t: cierres[t] for t in cartera if t in cierres},
        "detalle": detalle,
        "kill_switch": kill,
        "virtual": {"inicio": virtual["inicio"], "valor": round(valor, 2), "maximo": round(maximo, 2),
                    "historial": historial[-800:]},
    }
