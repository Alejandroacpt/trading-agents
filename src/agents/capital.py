"""
GESTIÓN DEL CAPITAL ENTRE MOTORES (plan v2)
-------------------------------------------
- Capital inicial + aportación mensual fija (config/sistema.yaml -> capital).
- Reparto entre motores según la FASE, que depende del capital total:
      < 5.000 €      -> 70 % táctico / 30 % estructural (agresivo)
      5.000-20.000 € -> 50 / 50
      > 20.000 €     -> 20 / 80 (largo plazo, menos volatilidad)
  Para cambiar de fase el capital tiene que estar al otro lado del umbral
  durante N días seguidos (histéresis), y así no se cambia de fase a cada
  rato cuando el capital ronda un umbral.
- Kill-switch sobre la cartera TOTAL (los dos motores juntos), medido
  desde su máximo. Las aportaciones suben el valor y el máximo a la vez,
  así que no cuentan como ganancia ni tapan una caída.

Cada aportación se reparte entre los motores con la fase vigente: el
estructural la recibe como liquidez y el táctico como "unidades" (como
un fondo: unidades = importe / valor liquidativo).

Estado compartido: state/capital.json (lo escribe el pipeline diario).
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import ROOT

RUTA = ROOT / "state" / "capital.json"


# ----------------------------------------------------------------------
# Aportaciones
# ----------------------------------------------------------------------

def aportaciones(conf: dict, hasta: date | str | None = None) -> list[tuple[str, float]]:
    """Lista de (fecha ISO, importe €) de las aportaciones mensuales ya vencidas
    (sin el capital inicial)."""
    hasta = pd.Timestamp(hasta or datetime.now(timezone.utc).date())
    importe = float(conf.get("aportacion_mensual_eur", 0) or 0)
    if importe <= 0 or not conf.get("primera_aportacion"):
        return []
    fechas = pd.date_range(pd.Timestamp(conf["primera_aportacion"]), hasta, freq="MS")
    dia = int(conf.get("dia_aportacion", 1))
    return [((f + pd.Timedelta(days=dia - 1)).date().isoformat(), importe)
            for f in fechas if f + pd.Timedelta(days=dia - 1) <= hasta]


def pendientes(conf: dict, aplicadas: list[str], hasta=None) -> list[tuple[str, float]]:
    hechas = set(aplicadas or [])
    return [(f, x) for f, x in aportaciones(conf, hasta) if f not in hechas]


def capital_aportado(conf: dict, hasta=None) -> float:
    return float(conf["inicial_eur"]) + sum(x for _, x in aportaciones(conf, hasta))


# ----------------------------------------------------------------------
# Fases
# ----------------------------------------------------------------------

def fase_por_valor(fases: list[dict], valor: float) -> int:
    for i, f in enumerate(fases):
        if f.get("hasta_eur") is None or valor < f["hasta_eur"]:
            return i
    return len(fases) - 1


def actualizar_fase(estado: dict, fases: list[dict], valor_total: float, histeresis_dias: int,
                    hoy: str | None = None) -> tuple[int, bool]:
    """Devuelve (fase vigente, ha cambiado). Guarda en estado el contador."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    actual = estado.get("fase", fase_por_valor(fases, valor_total))
    candidata = fase_por_valor(fases, valor_total)
    if candidata == actual:
        estado["candidata"] = None
        estado.update(fase=actual)
        return actual, False
    c = estado.get("candidata") or {}
    if c.get("fase") != candidata:
        c = {"fase": candidata, "desde": hoy, "dias": 0}
    if c.get("ultimo_dia") != hoy:
        c["dias"] = c.get("dias", 0) + 1
        c["ultimo_dia"] = hoy
    estado["candidata"] = c
    if c["dias"] >= histeresis_dias:
        estado["fase"] = candidata
        estado["candidata"] = None
        return candidata, True
    estado["fase"] = actual
    return actual, False


def reparto(fases: list[dict], fase: int) -> dict:
    f = fases[fase]
    return {"tactico": float(f["tactico"]), "estructural": float(f["estructural"])}


# ----------------------------------------------------------------------
# Estado compartido
# ----------------------------------------------------------------------

def cargar(ruta: Path = RUTA) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def guardar(estado: dict, ruta: Path = RUTA) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def fase_vigente(sistema: dict, estado: dict | None = None) -> tuple[int, dict]:
    """Fase guardada (o la que corresponde al capital inicial si aún no hay estado)."""
    estado = cargar() if estado is None else estado
    fases = sistema["fases"]["tramos"]
    f = estado.get("fase", fase_por_valor(fases, sistema["capital"]["inicial_eur"]))
    return f, reparto(fases, f)


def actualizar_total(estado: dict, valor_total: float, aportado_hoy: float, hoy: str | None = None) -> dict:
    """Valor y máximo de la cartera total. Las aportaciones suben ambos."""
    hoy = hoy or datetime.now(timezone.utc).date().isoformat()
    t = estado.get("total") or {"valor": valor_total, "maximo": valor_total, "historial": []}
    maximo = t.get("maximo", valor_total) + aportado_hoy
    maximo = max(maximo, valor_total)
    historial = [h for h in t.get("historial", []) if h[0] != hoy] + [[hoy, round(valor_total, 2)]]
    estado["total"] = {"valor": round(valor_total, 2), "maximo": round(maximo, 2),
                       "drawdown": round(valor_total / maximo - 1, 4) if maximo else 0.0,
                       "historial": historial[-800:]}
    return estado
