"""
Escáner táctico (cada hora en horario de EEUU, cada 2 horas el resto).

Qué hace:
  1. Actualiza las velas de 1 hora (solo los últimos días).
  2. Para cada estrategia táctica activa (config/tactico.yaml), repite la
     simulación desde la puesta en marcha con los datos reales: así la
     cartera táctica virtual sigue exactamente las mismas reglas validadas
     (stops incluidos).
  3. Compara con la última ejecución y avisa por Telegram de cada entrada
     (con su stop) y cada salida (con su resultado).
  4. Guarda el estado en state/tactico.json.

Uso:
    python scripts/run_tactico.py [--historico] [--sin-telegram]
      --historico  descarga todo el histórico horario (la primera vez)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import capital as gestor_capital  # noqa: E402
from src.agents.escaner import cargar_sistema  # noqa: E402
from src.alerts import telegram  # noqa: E402
from src.config import ROOT  # noqa: E402
from src.data import horario  # noqa: E402
from src.tactico import laboratorio  # noqa: E402
from src.tactico.familias import FAMILIAS_TACTICAS  # noqa: E402

RUTA_ESTADO = ROOT / "state" / "tactico.json"


def _eur(x):
    return f"{x:,.0f} €".replace(",", ".")


def _precio(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x < 1000 else f"{x:,.0f}".replace(",", ".")


def _pct(x):
    return f"{x * 100:+.1f} %".replace(".", ",")


def _tramo(ts: pd.Timestamp, mercado: str) -> str:
    """Vela agregada a la que pertenece una vela de 1 hora."""
    if mercado == "cripto":
        return str(ts.floor("4h"))
    ny = ts.tz_localize("UTC").tz_convert("America/New_York")
    return f"{ny.date()}-{int(ny.hour >= 13)}"


def stop_tocado(pos: dict, mercado: str, ultima_agregada: pd.Timestamp) -> bool:
    """¿El precio ha tocado el stop en la vela agregada que aún está en curso?

    El simulador solo ve velas completas; en la cuenta real no se espera a que
    termine la vela (hasta 4 horas): en cuanto una vela de 1 hora toca el stop
    se vende. En acciones no se vende el mismo día de la compra (norma PDT,
    igual que en el simulador)."""
    horas = laboratorio.ohlc_mercado(mercado).get(pos["activo"])
    if horas is None or horas.empty:
        return False
    tramo_cerrado = _tramo(ultima_agregada, mercado)
    en_curso = horas[(horas.index > ultima_agregada)]
    en_curso = en_curso[[_tramo(t, mercado) != tramo_cerrado for t in en_curso.index]]
    if en_curso.empty:
        return False
    if mercado == "acciones":
        hoy_ny = en_curso.index[-1].tz_localize("UTC").tz_convert("America/New_York").date()
        entrada_ny = pd.Timestamp(pos["entrada"]).tz_localize("UTC").tz_convert("America/New_York").date()
        if entrada_ny == hoy_ny:
            return False
    return bool(en_curso["low"].min() <= pos["stop"])


def factor_riesgo_tactico(equity: pd.Series, inicio_vivo: str, conf_ks: dict, dd_total: float) -> tuple[float, str, float]:
    """Kill-switch del motor táctico: el peor de (caída del propio motor desde su
    máximo en vivo, caída de la cartera total). Solo afecta a las entradas nuevas."""
    vivo = equity[equity.index >= pd.Timestamp(inicio_vivo)]
    dd_motor = float(vivo.iloc[-1] / vivo.cummax().iloc[-1] - 1) if len(vivo) else 0.0
    dd = min(dd_motor, dd_total)
    if dd <= -conf_ks["pausa"]:
        return 0.0, "PAUSA", dd_motor
    if dd <= -conf_ks["reducir_a_la_mitad"]:
        return 0.5, "MITAD", dd_motor
    return 1.0, "NORMAL", dd_motor


def cartera_estrategia(estrategia_id: str, inicio_vivo: str):
    """Simula una estrategia táctica activa desde la puesta en marcha."""
    return laboratorio.simular_en_vivo(estrategia_id, inicio_vivo)


def main() -> int:
    conf = horario.cargar_config()
    for linea in horario.actualizar(historico="--historico" in sys.argv):
        print(linea)
    laboratorio.ohlc_mercado.cache_clear()
    laboratorio.ohlc_agregado.cache_clear()

    activas = conf.get("estrategias") or []
    previo = json.loads(RUTA_ESTADO.read_text(encoding="utf-8")) if RUTA_ESTADO.exists() else {}
    if not activas:
        print("Motor táctico sin estrategias activas (ninguna aprobada todavía). Solo se actualizan datos.")
        return 0

    # Capital del motor: su parte de la fase (config/sistema.yaml), llevado en
    # "unidades" como un fondo: valor = unidades x valor liquidativo de la estrategia.
    sistema = cargar_sistema()
    conf_capital = sistema["capital"]
    estado_capital = gestor_capital.cargar()
    _, parte = gestor_capital.fase_vigente(sistema, estado_capital)
    ids = [item["id"] if isinstance(item, dict) else item for item in activas]
    resultados = {eid: cartera_estrategia(eid, conf["inicio_vivo"]) for eid in ids}
    liquidativo = {eid: float(r[0].equity.iloc[-1]) if len(r[0].equity) else 1.0 for eid, r in resultados.items()}
    unidades = dict(previo.get("unidades", {}))
    aplicadas = list(previo.get("aportaciones", []))
    avisos_capital = []
    if set(unidades) != set(ids):
        # Primera vez o cambia la lista de estrategias: el valor actual se reparte a partes iguales
        valor_actual = (sum(unidades[e] * liquidativo.get(e, 1.0) for e in unidades if e in liquidativo)
                        if unidades else previo.get("valor_total_eur", conf_capital["inicial_eur"] * parte["tactico"]))
        unidades = {e: valor_actual / len(ids) / liquidativo[e] for e in ids}
    for fecha, importe in gestor_capital.pendientes(conf_capital, aplicadas):
        for e in ids:
            unidades[e] += importe * parte["tactico"] / len(ids) / liquidativo[e]
        aplicadas.append(fecha)
        avisos_capital.append(f"Aportación del {fecha}: {_eur(importe * parte['tactico'])} al motor táctico")
    ajuste = estado_capital.get("ajuste_tactico")
    ajustes = list(previo.get("ajustes", []))
    if ajuste and ajuste["id"] not in ajustes:
        unidades = {e: ajuste["valor_eur"] / len(ids) / liquidativo[e] for e in ids}
        ajustes.append(ajuste["id"])
        avisos_capital.append(f"Cambio de fase: motor táctico ajustado a {_eur(ajuste['valor_eur'])}")
    for a in avisos_capital:
        print(a)

    estado = {"actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
              "modo": conf.get("modo", "simulacion"), "reparto_fase": parte["tactico"],
              "unidades": unidades, "aportaciones": aplicadas, "ajustes": ajustes,
              "estrategias": {}, "posiciones": {}, "pendientes": {},
              "cerradas": list(previo.get("cerradas", []))}
    riesgo_conf = conf["riesgo"]
    mensajes = []
    claves_previas = set(previo.get("posiciones", {}))
    pendientes_previas = set(previo.get("pendientes", {}))
    cerradas_previas = set(previo.get("cerradas", []))
    for item in activas:
        eid = item["id"] if isinstance(item, dict) else item
        res, fam, mercado = resultados[eid]
        nombre = fam["nombre"].replace("(4 h)", "(media sesión)") if mercado == "acciones" else fam["nombre"]
        estado_estrategia = item.get("estado", "aprobada") if isinstance(item, dict) else "aprobada"
        etiqueta = f"{nombre}" + (" · en observación" if estado_estrategia == "observacion" else "")
        cuando = "la apertura de la próxima sesión" if mercado == "acciones" else "la apertura de la próxima vela de 4 h"
        valor = unidades[eid] * liquidativo[eid]
        estado["estrategias"][eid] = {"valor_eur": round(valor, 2), "liquidativo": round(liquidativo[eid], 6),
                                      "operaciones": int(len(res.operaciones))}
        invertido = sum(p["peso"] for p in res.abiertas) * valor
        dd_total = (estado_capital.get("total") or {}).get("drawdown", 0.0)
        factor, kill, dd_motor = factor_riesgo_tactico(res.equity, conf["inicio_vivo"], riesgo_conf["kill_switch"], dd_total)
        estado["estrategias"][eid].update(kill_switch=kill, caida_motor=round(dd_motor, 4))
        kill_previo = (previo.get("estrategias", {}).get(eid) or {}).get("kill_switch", "NORMAL")
        if kill != kill_previo:
            mensajes.append(f"⚡🛡️ Kill-switch del motor táctico: {kill_previo} → {kill} "
                            f"(caída del motor {_pct(dd_motor)}, cartera total {_pct(dd_total)}). "
                            + ("Entradas nuevas a la mitad de tamaño." if kill == "MITAD" else
                               "Sin entradas nuevas; las posiciones abiertas siguen con su stop." if kill == "PAUSA" else
                               "Vuelve el tamaño normal."))
        velas_mercado = laboratorio.velas_de(fam, mercado)
        for pos in res.abiertas:
            clave = f"{eid}|{pos['activo']}|{pos['entrada']}"
            estado["posiciones"][clave] = {**pos, "entrada": str(pos["entrada"]), "estrategia": eid,
                                           "importe_eur": round(pos["peso"] * valor, 2)}
            if clave not in claves_previas:
                caida = pos["stop"] / pos["precio_entrada"] - 1
                mensajes.append(
                    f"⚡🟢 COMPRA {pos['activo']} (motor táctico) · {_eur(pos['peso'] * valor)}\n"
                    f"Estrategia: {etiqueta}\n"
                    f"Entrada: {_precio(pos['precio_entrada'])} · Stop: {_precio(pos['stop'])} ({_pct(caida)})\n"
                    f"Riesgo si salta el stop: ~{_eur(abs(caida) * pos['peso'] * valor)}")
        if len(res.operaciones):
            for _, op in res.operaciones.iterrows():
                clave = f"{eid}|{op['activo']}|{op['entrada']}|{op['salida']}"
                if clave in cerradas_previas:
                    continue
                estado["cerradas"].append(clave)
                motivo = "saltó el stop" if op["motivo"] == "stop" else "señal de salida"
                mensajes.append(f"⚡🔴 VENTA {op['activo']} (motor táctico) · {motivo} · resultado {_pct(op['resultado'])}\n"
                                f"Estrategia: {etiqueta}")
        # Stop tocado en la vela en curso: se vende ya en la cuenta real
        for pos in res.abiertas:
            if stop_tocado(pos, mercado, velas_mercado[pos["activo"]].index[-1]):
                clave = f"{eid}|{pos['activo']}|vender"
                estado["pendientes"][clave] = {"activo": pos["activo"], "accion": "vender", "estrategia": eid,
                                               "motivo": "stop"}
                if clave not in pendientes_previas:
                    mensajes.append(f"⚡🛑 STOP TOCADO {pos['activo']} (motor táctico): se vende ya\n"
                                    f"Estrategia: {etiqueta}\nStop: {_precio(pos['stop'])}")
        # Señales nuevas: se avisan en cuanto aparecen (se ejecutan en la próxima apertura)
        n_abiertas = len(res.abiertas)
        for pend in res.pendientes:
            clave = f"{eid}|{pend['activo']}|{pend['accion']}"
            pend = dict(pend)
            if pend["accion"] == "comprar":
                # Importe estimado con la misma regla que el simulador (riesgo por operación,
                # tope por posición y liquidez disponible), al último cierre.
                ref_p = float(velas_mercado[pend["activo"]]["close"].iloc[-1])
                importe = factor * min(riesgo_conf["riesgo_por_operacion"] * valor / pend["distancia_stop"] * ref_p,
                                       riesgo_conf["max_peso_posicion"] * valor, max(valor - invertido, 0.0))
                if n_abiertas >= riesgo_conf["max_posiciones"] or importe <= 0:
                    continue
                n_abiertas += 1
                invertido += importe
                pend["importe_eur"] = round(importe, 2)
            pend["estrategia"] = eid
            if clave in estado["pendientes"]:      # ya marcada (stop tocado)
                continue
            estado["pendientes"][clave] = pend
            if clave in pendientes_previas:
                continue
            if pend["accion"] == "comprar":
                ref = float(velas_mercado[pend["activo"]]["close"].iloc[-1])
                mensajes.append(f"⚡📣 SEÑAL DE COMPRA {pend['activo']} (motor táctico) · ~{_eur(pend['importe_eur'])}\n"
                                f"Estrategia: {etiqueta}\n"
                                f"Se compra en {cuando}. Último precio: {_precio(ref)} · "
                                f"stop aprox. {_precio(ref - pend['distancia_stop'])} ({_pct(-pend['distancia_stop'] / ref)})")
            else:
                mensajes.append(f"⚡📣 SEÑAL DE VENTA {pend['activo']} (motor táctico)\n"
                                f"Estrategia: {etiqueta}\nSe vende en {cuando}.")
    ultimas = [df.index.max() for m in ("cripto", "acciones") for df in laboratorio.ohlc_mercado(m).values()]
    estado["ultima_vela"] = str(max(ultimas)) if ultimas else previo.get("ultima_vela", "")
    estado["valor_total_eur"] = round(sum(e["valor_eur"] for e in estado["estrategias"].values()), 2)

    if not previo.get("posiciones") and not previo.get("ultima_vela"):
        # Primera ejecución con estrategias activas: un solo resumen, no el historial entero
        lineas = [f"⚡ Motor táctico activado · {_eur(estado['valor_total_eur'])} "
                  f"({parte['tactico']:.0%} de la cartera, fase agresiva)"]
        lineas += [f"• {v['activo']}: {_eur(v['importe_eur'])}, stop {_precio(v['stop'])}"
                   for v in estado["posiciones"].values()] or ["• Sin posiciones abiertas ahora mismo"]
        mensajes = ["\n".join(lineas)]

    mensajes = avisos_capital + mensajes if avisos_capital and previo.get("unidades") else mensajes
    RUTA_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    RUTA_ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    for m in mensajes:
        print(m + "\n")
    if "--sin-telegram" not in sys.argv:
        for m in mensajes:
            telegram.send_message(m, silencioso=False)
    print(f"Cartera táctica virtual: {_eur(estado['valor_total_eur'])} · {len(estado['posiciones'])} posiciones abiertas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
