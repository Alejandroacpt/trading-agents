"""
DIARIO DE OPERACIONES
---------------------
Registro de todo lo que hace el sistema, en diario/operaciones.csv
(se puede abrir en Excel o directamente en GitHub):
  - tipo "alerta": cada cambio de la cartera ejecutable que se avisa por Telegram.
  - tipo "orden":  cada orden enviada (o simulada) a la cuenta paper de Alpaca.

Para las órdenes se guarda el precio de referencia (último cierre) y,
cuando Alpaca la ejecuta, el precio real. La columna coste_ejecucion es
la diferencia entre ambos (positivo = peor para nosotros). Ojo: incluye
el movimiento del mercado entre el cierre y la ejecución, no solo el
deslizamiento; promediada en muchas órdenes, mide el coste de operar
al día siguiente de la señal.
Sirve para auditar el sistema y, en la fase con dinero real, como base
para la declaración de la renta.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import ROOT

RUTA_DIARIO = ROOT / "diario" / "operaciones.csv"
COLUMNAS = [
    "fecha_utc", "tipo", "activo", "accion", "importe", "moneda", "peso_antes", "peso_despues",
    "precio_ref", "estado", "order_id", "precio_ejecucion", "cantidad_ejecutada", "coste_ejecucion",
    "estrategias", "detalle",
]
ESTADOS_FINALES = {"filled", "canceled", "cancelled", "expired", "rejected", "error", "simulada", "replaced"}


def cargar(ruta: Path = RUTA_DIARIO) -> pd.DataFrame:
    if not ruta.exists():
        return pd.DataFrame(columns=COLUMNAS).astype(object)
    # object: cada celda puede ser texto o número (pandas 3 es estricto con los tipos)
    return pd.read_csv(ruta, dtype={"order_id": str}).reindex(columns=COLUMNAS).astype(object)


def guardar(diario: pd.DataFrame, ruta: Path = RUTA_DIARIO) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    diario.reindex(columns=COLUMNAS).to_csv(ruta, index=False)


def anadir(diario: pd.DataFrame, filas: list[dict]) -> pd.DataFrame:
    if not filas:
        return diario
    ahora = datetime.now(timezone.utc).isoformat(timespec="minutes")
    nuevas = pd.DataFrame([{**{c: "" for c in COLUMNAS}, "fecha_utc": ahora, **f} for f in filas]).astype(object)
    return (pd.concat([diario, nuevas], ignore_index=True) if len(diario) else nuevas).astype(object)


def filas_alertas(cambios: list[dict], capital_eur: float, cierres: dict, detalle: dict) -> list[dict]:
    filas = []
    for c in cambios:
        info = detalle.get(c["activo"], {})
        filas.append({
            "tipo": "alerta", "activo": c["activo"], "accion": c["tipo"].lower(),
            "importe": round(abs(c["despues"] - c["antes"]) * capital_eur, 2), "moneda": "EUR",
            "peso_antes": round(c["antes"], 4), "peso_despues": round(c["despues"], 4),
            "precio_ref": cierres.get(c["activo"], ""),
            "estrategias": ";".join(info.get("estrategias", {}).keys()),
            "detalle": info.get("motivo_venta", "") if c["tipo"] == "VENTA" else "",
        })
    return filas


def filas_ordenes(resultados: list[dict], cierres: dict, modo: str) -> list[dict]:
    return [{
        "tipo": "orden", "activo": r["activo"], "accion": r["accion"], "importe": round(r["importe"], 2),
        "moneda": "USD", "precio_ref": cierres.get(r["activo"], ""), "estado": r["estado"],
        "order_id": r.get("order_id", ""), "detalle": r.get("error", "") or f"modo {modo}",
    } for r in resultados]


def actualizar_ejecuciones(diario: pd.DataFrame, cliente) -> pd.DataFrame:
    """Consulta en Alpaca las órdenes aún abiertas y apunta su precio de ejecución."""
    if diario.empty:
        return diario
    pendientes = diario[(diario["tipo"] == "orden") & diario["order_id"].notna() & (diario["order_id"] != "")
                        & ~diario["estado"].astype(str).str.lower().isin(ESTADOS_FINALES)]
    for i, fila in pendientes.iterrows():
        try:
            o = cliente.orden(str(fila["order_id"]))
        except Exception:  # noqa: BLE001
            continue
        diario.at[i, "estado"] = o.get("status", fila["estado"])
        if o.get("filled_avg_price"):
            precio = float(o["filled_avg_price"])
            diario.at[i, "precio_ejecucion"] = precio
            diario.at[i, "cantidad_ejecutada"] = float(o.get("filled_qty") or 0)
            ref = pd.to_numeric(fila["precio_ref"], errors="coerce")
            if ref and not pd.isna(ref):
                signo = 1 if fila["accion"] == "comprar" else -1  # comprar más caro / vender más barato = coste
                diario.at[i, "coste_ejecucion"] = round(signo * (precio / ref - 1), 5)
    return diario
