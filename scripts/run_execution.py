"""
Pipeline diario, paso 3: ejecución en la cuenta paper de Alpaca.

Qué hace:
  1. Actualiza en el diario el precio de las órdenes que ya se ejecutaron.
  2. Lee la cuenta paper y sus posiciones.
  3. Calcula las órdenes para igualar la cartera ejecutable del paso 2.
  4. En modo "paper" las envía (en modo "simulacion" solo las apunta).
  5. Guarda el diario y el estado de la cuenta paper.

Uso:
    python scripts/run_execution.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import cartera_virtual, diario, ejecucion  # noqa: E402
from src.agents.escaner import cargar_sistema  # noqa: E402
from src.config import ROOT  # noqa: E402
from src.data import horario  # noqa: E402
from src.alerts import telegram  # noqa: E402
from src.broker.alpaca import ClienteAlpaca  # noqa: E402
from src.config import load_universe  # noqa: E402
from src.data.store import close_matrix  # noqa: E402


def main() -> int:
    sistema = cargar_sistema()
    conf = sistema.get("alpaca", {"modo": "simulacion", "orden_minima_usd": 10})
    modo = conf["modo"]

    estado = cartera_virtual.cargar()
    if not estado:
        print("No hay estado: ejecuta antes scripts/run_signals.py")
        return 0
    try:
        cliente = ClienteAlpaca()
    except RuntimeError as e:
        print(f"Ejecución omitida: {e}")
        return 0

    ruta_tac = ROOT / "state" / "tactico.json"
    ruta_alp = ROOT / "state" / "alpaca.json"
    tactico = json.loads(ruta_tac.read_text(encoding="utf-8")) if ruta_tac.exists() else None
    conf_tac = horario.cargar_config()
    incluir_tactico = conf_tac.get("modo") == "paper" and bool(conf_tac.get("estrategias"))

    universo = [a["ticker"] for a in load_universe() if a["clase"] not in ("forex", "cash")]
    for m in conf_tac["mercados"].values():
        universo += [ejecucion.ticker_comun(t) for t in m["activos"] if ejecucion.ticker_comun(t) not in universo]
    precios = close_matrix(load_universe())
    cierres = cartera_virtual.ultimos_cierres(precios)
    eurusd = cierres.get("EURUSD=X", 1.08)
    objetivo, total_eur = ejecucion.objetivo_combinado(estado, tactico, incluir_tactico)

    # 1) Ejecuciones pendientes de pasadas anteriores
    d = diario.actualizar_ejecuciones(diario.cargar(), cliente)

    # 2) Cuenta y posiciones
    cuenta = cliente.cuenta()
    actuales = ejecucion.posiciones_gestionadas(cliente.posiciones(), universo)
    capital_usd, fuente = ejecucion.capital_referencia(cuenta, total_eur, eurusd)

    # 3) Órdenes
    ordenes = ejecucion.calcular_ordenes(objetivo, capital_usd, actuales, conf["orden_minima_usd"],
                                         conf.get("banda_rebalanceo", 0.0))

    # 4) Envío (o simulación)
    todas = ejecucion.ejecutar(ordenes, cliente, modo, universo)
    resultados = [r for r in todas if r["estado"] != "ya_pendiente"]
    if len(todas) > len(resultados):
        print(f"  {len(todas) - len(resultados)} orden(es) ya pendientes de pasadas anteriores: se mantienen")
    d = diario.anadir(d, diario.filas_ordenes(resultados, cierres, modo))
    diario.guardar(d)

    # 5) Estado de la cuenta paper
    hoy = datetime.now(timezone.utc).date().isoformat()
    equity = float(cuenta.get("equity", 0))
    previo = (json.loads(ruta_alp.read_text(encoding="utf-8")) if ruta_alp.exists()
              else estado.get("alpaca", {}))
    historial = [h for h in previo.get("historial", []) if h[0] != hoy] + [[hoy, round(equity, 2)]]
    alpaca = {
        "modo": modo,
        "fuente_capital": fuente,
        "capital_gestionado_usd": round(capital_usd, 2),
        "equity_cuenta_usd": round(equity, 2),
        "valor_posiciones_usd": round(sum(p["valor"] for p in actuales.values()), 2),
        "eurusd": eurusd,
        "actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "historial": historial[-800:],
        "incluye_tactico": incluir_tactico,
        "objetivo": {t: round(w, 4) for t, w in sorted(objetivo.items(), key=lambda x: -x[1])},
    }
    ruta_alp.write_text(json.dumps(alpaca, indent=2, ensure_ascii=False), encoding="utf-8")
    if "alpaca" in estado:      # antes se guardaba aquí; ahora va en state/alpaca.json
        estado.pop("alpaca")
        cartera_virtual.guardar(estado)

    # Informe por pantalla y Telegram
    print(f"Modo {modo} · capital gestionado {capital_usd:,.2f} $ ({fuente}) · equity cuenta {equity:,.2f} $")
    for r in resultados:
        print(f"  {r['accion']:8s} {r['activo']:8s} {r['importe']:>10,.2f} $  -> {r['estado']} {r.get('error', '')}")
    if not resultados:
        print("  Sin órdenes: la cuenta ya coincide con la cartera.")

    errores = [r for r in resultados if r["estado"] == "error"]
    if modo == "paper" and resultados:
        lineas = [f"🤖 Paper Alpaca: {len(resultados)} orden(es)"]
        for r in resultados:
            icono = "❌" if r["estado"] == "error" else "✔️"
            lineas.append(f"{icono} {r['accion']} {r['activo']} {r['importe']:,.0f} $ ({r['estado']})".replace(",", "."))
        telegram.send_message("\n".join(lineas), silencioso=not errores)
    return 0


if __name__ == "__main__":
    sys.exit(main())
