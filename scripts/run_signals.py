"""
Pipeline diario, paso 2: señales, riesgo y alertas.

Qué hace:
  1. Escáneres: señal vigente de cada estrategia activa (config/sistema.yaml).
  2. Agente de riesgo: reparto entre estrategias, topes y kill-switch.
  3. Cartera ejecutable para poco capital.
  4. Alertas: compara con la última ejecución y avisa por Telegram de
     cada compra, venta o ajuste (con sonido). Por la noche, además, un
     resumen de la cartera (sin sonido).
  5. Guarda el estado (state/estado.json) y el informe (reports/senales.md).

Uso:
    python scripts/run_signals.py                 -> normal
    python scripts/run_signals.py --sin-telegram  -> no envía nada
    python scripts/run_signals.py --resumen       -> fuerza el resumen diario
    python scripts/run_signals.py --seco          -> no guarda el estado (pruebas)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import alertas, cartera_virtual, riesgo  # noqa: E402
from src.agents.escaner import calcular_senales, cargar_sistema, explicar, vista_por_clase  # noqa: E402
from src.alerts import telegram  # noqa: E402
from src.config import REPORTS_DIR, load_universe  # noqa: E402
from src.data.store import close_matrix  # noqa: E402


def main() -> int:
    enviar = "--sin-telegram" not in sys.argv
    seco = "--seco" in sys.argv
    forzar_resumen = "--resumen" in sys.argv

    universo = load_universe()
    clases = {a["ticker"]: a["clase"] for a in universo}
    precios = close_matrix(universo)
    sistema = cargar_sistema()
    capital = sistema["capital_eur"]

    # 1) Escáneres
    senales = calcular_senales(precios, sistema)
    vista = vista_por_clase(precios, universo, senales)

    # 2) Riesgo
    reparto = riesgo.reparto_estrategias(senales, precios, sistema)
    previo = cartera_virtual.cargar()
    cierres = cartera_virtual.ultimos_cierres(precios)
    virtual = cartera_virtual.actualizar_valor(previo, cierres, capital)
    factor, kill = riesgo.factor_kill_switch(virtual["drawdown"], sistema)
    modelo = riesgo.cartera_modelo(senales, reparto, sistema, factor)

    # 3) Cartera ejecutable
    ejecutable = riesgo.cartera_ejecutable(modelo, sistema).to_dict()

    # Explicaciones de cada posición
    detalle = {}
    for sid, d in senales.items():
        for activo in d["pesos"].index:
            motivo, salida = explicar(sid, precios, activo, dentro=True)
            info = detalle.setdefault(activo, {"cierre": cierres.get(activo), "estrategias": {}})
            info["estrategias"][sid] = {"estado": d["config"]["estado"], "motivo": motivo, "salida": salida}
    for activo in set(virtual["pesos_derivados"]) - set(ejecutable):
        info = detalle.setdefault(activo, {"cierre": cierres.get(activo), "estrategias": {}})
        if activo in modelo.index:
            info["motivo_venta"] = ("Sale de la cartera ejecutable por tamaño: ya no está entre las "
                                    f"{sistema['cartera_ejecutable']['max_posiciones']} posiciones mayores "
                                    f"o queda por debajo de {sistema['cartera_ejecutable']['minimo_posicion_eur']} €.")
        elif kill == "PAUSA":
            info["motivo_venta"] = "Kill-switch en pausa: todo a liquidez."
        else:
            antes = (previo or {}).get("detalle", {}).get(activo, {}).get("estrategias", {})
            textos = [explicar(sid, precios, activo, dentro=False)[0] for sid in antes] or ["La estrategia ya no lo quiere."]
            info["motivo_venta"] = " ".join(textos)

    # 4) Alertas
    mensajes_sonoros = []
    if previo is None:
        mensajes_sonoros.append(alertas.mensaje_cartera_inicial(ejecutable, capital, detalle))
    else:
        aviso_kill = alertas.mensaje_kill_switch(previo.get("kill_switch", "NORMAL"), kill, virtual["drawdown"])
        if aviso_kill:
            mensajes_sonoros.append(aviso_kill)
        for c in alertas.detectar_cambios(virtual["pesos_derivados"], ejecutable, sistema["alertas"]["umbral_ajuste"]):
            mensajes_sonoros.append(alertas.mensaje_cambio(c, capital, detalle, clases))

    fecha_datos = precios.index[-1].date().isoformat()
    estado = cartera_virtual.nuevo_estado(virtual, ejecutable, cierres, clases, kill, detalle, fecha_datos)

    es_noche = datetime.now(timezone.utc).hour >= 18
    resumen = alertas.mensaje_resumen(estado, modelo.to_dict(), reparto.to_dict(), capital, vista, kill)

    for m in mensajes_sonoros:
        print(m + "\n")
    print(resumen)

    if enviar:
        for m in mensajes_sonoros:
            telegram.send_message(m, silencioso=False)
        if es_noche or forzar_resumen:
            telegram.send_message(resumen, silencioso=True)

    # 5) Guardar
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "senales.md").write_text(
        alertas.informe_markdown(estado, modelo.to_dict(), reparto.to_dict(), vista, senales, capital, kill),
        encoding="utf-8")
    if not seco:
        cartera_virtual.guardar(estado)
    print(f"\n{len(mensajes_sonoros)} alerta(s). Estado {'NO ' if seco else ''}guardado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
