"""
ACTUALIZACIÓN DIARIA DE DATOS
-----------------------------
Recorre todo el universo, descarga cada activo, decide si guarda la
descarga nueva, revisa la calidad y prepara un informe.

Es el primer paso del pipeline diario. Se lanza con:
    python scripts/update_data.py
"""

import time
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR, REPORTS_DIR, load_universe
from src.data import quality, store
from src.data.sources import download_asset


def update_all(
    assets: list[dict] | None = None,
    data_dir: Path = DATA_DIR,
    downloader=download_asset,
    hoy: pd.Timestamp | None = None,
    pausa_segundos: float = 0.5,
    ahora_utc: pd.Timestamp | None = None,
) -> list[dict]:
    """Actualiza todos los activos y devuelve una fila de estado por activo.

    downloader: función que descarga un activo. Por defecto, la real
    (Yahoo/Kraken). En los tests se sustituye por una que genera datos
    simulados, para poder probar todo sin internet.
    """
    assets = assets or load_universe()
    hoy = (hoy or pd.Timestamp.today()).normalize()
    resultados = []

    for asset in assets:
        ticker = asset["ticker"]
        path = store.ruta_csv(asset, data_dir)
        clase = asset["clase"]
        # Lo guardado también se limpia de velas incompletas (por si se
        # guardó alguna en una ejecución a mitad de sesión).
        old = store.quitar_vela_incompleta(store.load_prices(path), clase, ahora_utc)
        fila = {"ticker": ticker, "clase": clase, "nombre": asset.get("nombre", "")}

        # 1) Descargar (y quitar la vela de hoy si aún no ha cerrado)
        try:
            new, fuente = downloader(asset)
            new = store.quitar_vela_incompleta(new, clase, ahora_utc)
            fila["fuente"] = fuente
        except Exception as e:  # noqa: BLE001
            new, fila["fuente"] = pd.DataFrame(), "-"
            fila["error_descarga"] = str(e)[:200]

        # 2) Decidir si se guarda
        reemplazar, motivo = store.decide_replace(old, new)
        if reemplazar:
            store.save_prices(new, path)
            datos = store.load_prices(path)  # releemos lo guardado (ya redondeado)
        else:
            datos = old
            if not old.empty:
                store.save_prices(old, path)  # por si se le quitó una vela incompleta
        fila["guardado"] = reemplazar
        fila["motivo"] = motivo

        # 3) Revisar calidad: últimos 30 días (para el aviso diario)
        #    y todo el histórico (para el informe completo)
        recientes = quality.check_prices(datos, asset["clase"], hoy, ventana_dias=30)
        if "error_descarga" in fila:
            recientes.insert(0, {"nivel": "AVISO", "mensaje": "fallo de descarga: " + fila["error_descarga"]})
        fila["problemas_recientes"] = recientes
        fila["problemas_historicos"] = quality.check_prices(datos, asset["clase"], hoy)
        fila["estado"] = quality.resumen_estado(recientes)

        # 4) Datos básicos de la serie
        if not datos.empty:
            fila["desde"] = datos.index.min().date()
            fila["hasta"] = datos.index.max().date()
            fila["filas"] = len(datos)
            fila["ultimo_cierre"] = float(datos["close"].iloc[-1])
            if len(datos) > 1:
                fila["var_dia"] = float(datos["close"].iloc[-1] / datos["close"].iloc[-2] - 1)

        resultados.append(fila)
        time.sleep(pausa_segundos)  # pequeña pausa para no saturar a Yahoo

    return resultados


# ----------------------------------------------------------------------
# Informes
# ----------------------------------------------------------------------

ICONO = {"OK": "✅", "AVISO": "⚠️", "ERROR": "❌"}


def informe_markdown(resultados: list[dict], hoy: pd.Timestamp | None = None) -> str:
    """Informe completo en Markdown (se guarda en reports/data_status.md
    y se puede leer cómodamente en GitHub)."""
    hoy = (hoy or pd.Timestamp.today()).normalize()
    lineas = [
        f"# Estado de los datos · {hoy.date()}",
        "",
        "| Estado | Ticker | Activo | Clase | Desde | Hasta | Días | Último cierre | Var. día | Fuente |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultados:
        var = f"{r['var_dia']:+.2%}" if "var_dia" in r else "-"
        cierre = f"{r['ultimo_cierre']:,.4f}" if "ultimo_cierre" in r else "-"
        lineas.append(
            f"| {ICONO[r['estado']]} | {r['ticker']} | {r['nombre']} | {r['clase']} | "
            f"{r.get('desde', '-')} | {r.get('hasta', '-')} | {r.get('filas', 0)} | "
            f"{cierre} | {var} | {r['fuente']} |"
        )

    lineas += ["", "## Avisos de los últimos 30 días", ""]
    hay = False
    for r in resultados:
        for p in r["problemas_recientes"]:
            lineas.append(f"- **{r['ticker']}** · {p['nivel']}: {p['mensaje']}")
            hay = True
    if not hay:
        lineas.append("Ninguno.")

    lineas += [
        "",
        "## Revisión de todo el histórico",
        "",
        "Informativo: incidencias antiguas (cierres de mercado, saltos reales, huecos de la fuente).",
        "",
    ]
    for r in resultados:
        for p in r["problemas_historicos"]:
            lineas.append(f"- **{r['ticker']}** · {p['nivel']}: {p['mensaje']}")

    lineas += ["", "## Descargas no guardadas", ""]
    no_guardados = [r for r in resultados if not r["guardado"]]
    if no_guardados:
        for r in no_guardados:
            lineas.append(f"- **{r['ticker']}**: se mantienen los datos anteriores ({r['motivo']})")
    else:
        lineas.append("Ninguna: todas las descargas se guardaron.")

    return "\n".join(lineas) + "\n"


def resumen_telegram(resultados: list[dict], hoy: pd.Timestamp | None = None) -> str:
    """Mensaje corto para Telegram con el estado de los datos."""
    hoy = (hoy or pd.Timestamp.today()).normalize()
    total = len(resultados)
    ok = sum(r["estado"] == "OK" for r in resultados)

    lineas = [f"📊 Datos {hoy.date()}: {ok}/{total} activos OK"]
    for r in resultados:
        if r["estado"] != "OK":
            primer = r["problemas_recientes"][0]["mensaje"] if r["problemas_recientes"] else ""
            lineas.append(f"{ICONO[r['estado']]} {r['ticker']}: {primer}")

    # Pequeño resumen de mercado: variación del día de algunos activos clave
    clave = ["SPY", "QQQ", "TLT", "GLD", "BTC-USD", "EURUSD=X"]
    movs = [f"{r['ticker']} {r['var_dia']:+.1%}" for r in resultados if r["ticker"] in clave and "var_dia" in r]
    if movs:
        lineas.append("")
        lineas.append("Último día: " + " · ".join(movs))

    return "\n".join(lineas)


def guardar_informe(resultados: list[dict], reports_dir: Path = REPORTS_DIR, hoy=None) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "data_status.md"
    path.write_text(informe_markdown(resultados, hoy), encoding="utf-8")
    return path
