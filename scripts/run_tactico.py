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

from src.alerts import telegram  # noqa: E402
from src.config import ROOT  # noqa: E402
from src.data import horario  # noqa: E402
from src.tactico import laboratorio  # noqa: E402
from src.tactico.familias import FAMILIAS_TACTICAS  # noqa: E402
from src.tactico.simulador import simular  # noqa: E402

RUTA_ESTADO = ROOT / "state" / "tactico.json"


def _eur(x):
    return f"{x:,.0f} €".replace(",", ".")


def _precio(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if x < 1000 else f"{x:,.0f}".replace(",", ".")


def _pct(x):
    return f"{x * 100:+.1f} %".replace(".", ",")


def cartera_estrategia(estrategia_id: str, inicio_vivo: str):
    """Simula una estrategia táctica activa desde la puesta en marcha."""
    familia, mercado = estrategia_id.removeprefix("tac_").split("__")
    fam = FAMILIAS_TACTICAS[familia]
    ohlc = laboratorio.velas_de(fam, mercado)
    desde = pd.Timestamp(inicio_vivo)
    # Indicadores calculados con TODO el histórico (igual que en el backtest:
    # la media de 50 días y el momentum de 90 velas necesitan meses de datos).
    senales = fam["funcion"](ohlc, **fam["parametros"])
    for s in senales.values():
        s.loc[s.index < desde, "entrada"] = False   # solo cuentan entradas desde la puesta en marcha
    return simular(ohlc, senales, laboratorio.parametros_simulacion(mercado)), fam, mercado


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

    capital = conf["capital_virtual_eur"]
    reparto = capital / len(activas)       # v1: mismo capital para cada estrategia activa
    estado = {"actualizado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
              "capital_eur": capital, "estrategias": {}, "posiciones": {}, "pendientes": {},
              "cerradas": list(previo.get("cerradas", []))}
    mensajes = []
    claves_previas = set(previo.get("posiciones", {}))
    pendientes_previas = set(previo.get("pendientes", {}))
    cerradas_previas = set(previo.get("cerradas", []))
    for item in activas:
        eid = item["id"] if isinstance(item, dict) else item
        res, fam, mercado = cartera_estrategia(eid, conf["inicio_vivo"])
        nombre = fam["nombre"].replace("(4 h)", "(media sesión)") if mercado == "acciones" else fam["nombre"]
        estado_estrategia = item.get("estado", "aprobada") if isinstance(item, dict) else "aprobada"
        etiqueta = f"{nombre}" + (" · en observación" if estado_estrategia == "observacion" else "")
        cuando = "la apertura de la próxima sesión" if mercado == "acciones" else "la apertura de la próxima vela de 4 h"
        valor = reparto * float(res.equity.iloc[-1]) if len(res.equity) else reparto
        estado["estrategias"][eid] = {"valor_eur": round(valor, 2), "operaciones": int(len(res.operaciones))}
        for pos in res.abiertas:
            clave = f"{eid}|{pos['activo']}|{pos['entrada']}"
            estado["posiciones"][clave] = {**pos, "entrada": str(pos["entrada"]), "importe_eur": round(pos["peso"] * valor, 2)}
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
        # Señales nuevas: se avisan en cuanto aparecen (se ejecutan en la próxima apertura)
        for pend in res.pendientes:
            clave = f"{eid}|{pend['activo']}|{pend['accion']}"
            estado["pendientes"][clave] = pend
            if clave in pendientes_previas:
                continue
            if pend["accion"] == "comprar":
                ref = float(laboratorio.velas_de(fam, mercado)[pend["activo"]]["close"].iloc[-1])
                mensajes.append(f"⚡📣 SEÑAL DE COMPRA {pend['activo']} (motor táctico)\n"
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
        lineas = [f"⚡ Motor táctico activado · cartera virtual {_eur(estado['valor_total_eur'])}"]
        lineas += [f"• {v['activo']}: {_eur(v['importe_eur'])}, stop {_precio(v['stop'])}"
                   for v in estado["posiciones"].values()] or ["• Sin posiciones abiertas ahora mismo"]
        mensajes = ["\n".join(lineas)]

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
