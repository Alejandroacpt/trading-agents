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

import json  # noqa: E402

from src.agents import alertas, capital as gestor_capital, cartera_virtual, diario, riesgo  # noqa: E402
from src.agents.escaner import POR_ID, calcular_senales, cargar_sistema, explicar, vista_por_clase  # noqa: E402
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
    conf_capital = sistema["capital"]
    estado_capital = gestor_capital.cargar()
    fase, parte = gestor_capital.fase_vigente(sistema, estado_capital)
    hoy = datetime.now(timezone.utc).date().isoformat()

    # 1) Escáneres
    senales = calcular_senales(precios, sistema)
    vista = vista_por_clase(precios, universo, senales)

    # 2) Riesgo
    reparto = riesgo.reparto_estrategias(senales, precios, sistema)
    previo = cartera_virtual.cargar()
    if previo is not None and previo.get("motor") != "estructural":
        # Paso al plan por fases: la cartera virtual pasa a ser solo la parte del motor estructural
        previo = cartera_virtual.ajustar_capital(previo, conf_capital["inicial_eur"] * parte["estructural"])
        previo["motor"], previo["aportaciones"] = "estructural", []
    if previo is None:
        capital = gestor_capital.capital_aportado(conf_capital) * parte["estructural"]
    else:
        for fecha, importe in gestor_capital.pendientes(conf_capital, previo.get("aportaciones")):
            cartera_virtual.aportar(previo, importe * parte["estructural"], fecha)
            print(f"Aportación del {fecha}: {importe * parte['estructural']:.2f} € al motor estructural")
        capital = previo["capital_eur"]
    cierres = cartera_virtual.ultimos_cierres(precios)
    virtual = cartera_virtual.actualizar_valor(previo, cierres, capital)

    # Cartera total (estructural + táctico): fase y kill-switch
    ruta_tac = cartera_virtual.RUTA_ESTADO.parent / "tactico.json"
    tac = json.loads(ruta_tac.read_text(encoding="utf-8")) if ruta_tac.exists() else {}
    valor_tactico = tac.get("valor_total_eur", conf_capital["inicial_eur"] * parte["tactico"])
    valor_tactico += sum(x * parte["tactico"] for _, x in gestor_capital.pendientes(conf_capital, tac.get("aportaciones")))
    nuevas = gestor_capital.pendientes(conf_capital, estado_capital.get("aportaciones"))
    estado_capital.setdefault("aportaciones", []).extend(f for f, _ in nuevas)
    gestor_capital.actualizar_total(estado_capital, virtual["valor"] + valor_tactico, sum(x for _, x in nuevas), hoy)
    total = estado_capital["total"]
    fases = sistema["fases"]["tramos"]
    fase, cambio_fase = gestor_capital.actualizar_fase(estado_capital, fases, total["valor"],
                                                      sistema["fases"]["histeresis_dias"], hoy)
    mensaje_fase = None
    if cambio_fase:
        parte = gestor_capital.reparto(fases, fase)
        objetivo_est = total["valor"] * parte["estructural"]
        if previo is not None:
            cartera_virtual.aportar(previo, objetivo_est - virtual["valor"], f"cambio-fase-{hoy}")
            virtual = cartera_virtual.actualizar_valor(previo, cierres, previo["capital_eur"])
            capital = previo["capital_eur"]
        estado_capital["ajuste_tactico"] = {"id": f"cambio-fase-{hoy}", "valor_eur": round(total["valor"] * parte["tactico"], 2)}
        mensaje_fase = (f"🔀 Cambio de fase: cartera total {total['valor']:,.0f} €. Nuevo reparto: "
                        f"{parte['tactico']:.0%} táctico / {parte['estructural']:.0%} estructural.").replace(",", ".")
    estado_capital["reparto"] = parte
    factor, kill = riesgo.factor_kill_switch(total["drawdown"], sistema)
    sistema["capital_eur"] = virtual["valor"]          # importes mínimos de la cartera ejecutable
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
            apartadas = [sid for sid in antes if sid not in senales]
            if apartadas and len(apartadas) == len(antes):
                textos = ["Las estrategias que lo tenían (" + ", ".join(POR_ID[s]["nombre"] for s in apartadas)
                          + ") ya no operan: en la fase agresiva el motor estructural solo usa tendencia en cripto."]
            else:
                textos = ([explicar(sid, precios, activo, dentro=False)[0] for sid in antes if sid in senales]
                          or ["La estrategia ya no lo quiere."])
            info["motivo_venta"] = " ".join(textos)

    # 4) Alertas
    mensajes_sonoros = []
    if mensaje_fase:
        mensajes_sonoros.append(mensaje_fase)
    if previo is None:
        mensajes_sonoros.append(alertas.mensaje_cartera_inicial(ejecutable, virtual["valor"], detalle))
        cambios = alertas.detectar_cambios({}, ejecutable, 0.0)
    else:
        aviso_kill = alertas.mensaje_kill_switch(previo.get("kill_switch", "NORMAL"), kill, virtual["drawdown"])
        if aviso_kill:
            mensajes_sonoros.append(aviso_kill)
        cambios = alertas.detectar_cambios(virtual["pesos_derivados"], ejecutable, sistema["alertas"]["umbral_ajuste"])
        for c in cambios:
            mensajes_sonoros.append(alertas.mensaje_cambio(c, virtual["valor"], detalle, clases))

    fecha_datos = precios.index[-1].date().isoformat()
    estado = cartera_virtual.nuevo_estado(virtual, ejecutable, cierres, clases, kill, detalle, fecha_datos, capital)
    estado["motor"] = "estructural"
    estado["aportaciones"] = (previo or {}).get("aportaciones") or [f for f, _ in gestor_capital.aportaciones(conf_capital)]

    es_noche = datetime.now(timezone.utc).hour >= 18
    resumen = alertas.mensaje_resumen(estado, modelo.to_dict(), reparto.to_dict(), capital, vista, kill,
                                      total=total, parte=parte, valor_tactico=valor_tactico,
                                      aportado=gestor_capital.capital_aportado(conf_capital))

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
        gestor_capital.guardar(estado_capital)
        if cambios:
            d = diario.anadir(diario.cargar(), diario.filas_alertas(cambios, virtual["valor"], cierres, detalle))
            diario.guardar(d)
    print(f"\n{len(mensajes_sonoros)} alerta(s). Estado {'NO ' if seco else ''}guardado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
