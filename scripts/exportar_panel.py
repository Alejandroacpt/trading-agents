"""
Exporta el estado de toda la red de agentes a web/data.json para el panel web.

Solo cifras, nombres de estrategias y textos de los informes: nunca claves,
tokens ni identificadores de cuenta (la web es pública).

Uso:
    python scripts/exportar_panel.py
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import capital as gestor_capital  # noqa: E402
from src.agents.escaner import POR_ID, cargar_sistema  # noqa: E402
from src.config import REPORTS_DIR, ROOT  # noqa: E402
from src.data import horario  # noqa: E402

ESTADO = ROOT / "state"
SALIDA = ROOT / "web" / "data.json"
BASE_CUENTA_USD = 100_000.0     # saldo inicial de la cuenta paper de Alpaca


def leer(ruta: Path) -> dict:
    try:
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def num(x, d=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) or math.isinf(x) else round(x, d)


def hora(t) -> str | None:
    if not t:
        return None
    try:
        ts = pd.Timestamp(str(t))
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return ts.isoformat(timespec="minutes")
    except Exception:  # noqa: BLE001
        return None


def nombre_tactico(eid: str) -> tuple[str, str]:
    from src.tactico.familias import FAMILIAS_TACTICAS
    familia, mercado = eid.removeprefix("tac_").split("__")
    nombre = FAMILIAS_TACTICAS.get(familia, {}).get("nombre", familia)
    nombre = nombre.replace("(4 h)", "(media sesión)") if mercado == "acciones" else nombre
    return nombre, mercado


DESCRIPCIONES = {
    "tac_momentum_tendencia__acciones": "Compra acciones y ETFs de EEUU que llevan semanas subiendo con fuerza, solo si están por "
                                        "encima de su media de 50 días. Stop por volatilidad que va subiendo con el precio.",
    "crypto_trend_vol": "Compra BTC, ETH y SOL cuando están por encima de su media de 100 días y ajusta el tamaño a su "
                        "volatilidad. Si no hay tendencia, liquidez.",
}


def operaciones_cerradas(d: pd.DataFrame) -> list[dict]:
    """Empareja compras y ventas ejecutadas (FIFO) para sacar el resultado real de cada operación cerrada."""
    o = d[(d["tipo"] == "orden") & (d["estado"].astype(str) == "filled")].copy()
    if o.empty:
        return []
    o["fecha"] = pd.to_datetime(o["fecha_ejecucion"].fillna(o["fecha_utc"]), errors="coerce", utc=True)
    o = o.sort_values("fecha")
    abiertos: dict[str, list] = {}
    cerradas = []
    for r in o.itertuples():
        q, p = float(r.cantidad_ejecutada or 0), float(r.precio_ejecucion or 0)
        if q <= 0 or p <= 0:
            continue
        if r.accion == "comprar":
            abiertos.setdefault(r.activo, []).append([q, p, r.fecha])
            continue
        restante, coste, entrada = q, 0.0, None
        while restante > 1e-9 and abiertos.get(r.activo):
            lote = abiertos[r.activo][0]
            usar = min(restante, lote[0])
            coste += usar * lote[1]
            entrada = entrada or lote[2]
            lote[0] -= usar
            restante -= usar
            if lote[0] <= 1e-9:
                abiertos[r.activo].pop(0)
        vendido = q - restante
        if vendido > 0:
            pl = vendido * p - coste
            cerradas.append({"activo": r.activo, "entrada": hora(entrada), "salida": hora(r.fecha),
                             "precio_entrada": num(coste / vendido), "precio_salida": num(p),
                             "resultado_usd": num(pl, 2), "resultado_pct": num(pl / coste if coste else 0)})
    return sorted(cerradas, key=lambda c: c["salida"] or "", reverse=True)


def main() -> int:
    ahora = datetime.now(timezone.utc)
    sistema = cargar_sistema()
    conf_cap = sistema["capital"]
    conf_tac = horario.cargar_config()
    est, tac, alp = leer(ESTADO / "estado.json"), leer(ESTADO / "tactico.json"), leer(ESTADO / "alpaca.json")
    cap, vig = leer(ESTADO / "capital.json"), leer(ESTADO / "vigilante.json")
    aud = leer(REPORTS_DIR / "auditor" / "ultimo.json")
    lab_d, lab_t = leer(REPORTS_DIR / "laboratorio" / "ultimo.json"), leer(REPORTS_DIR / "laboratorio" / "tactico.json")
    bib = leer(REPORTS_DIR / "validacion" / "ultimo.json")

    # --- Cartera
    t = cap.get("total") or {}
    fases = sistema["fases"]["tramos"]
    fase = cap.get("fase", 0)
    aportado = gestor_capital.capital_aportado(conf_cap)
    historial = [{"fecha": f, "total": v} for f, v in (t.get("historial") or [])]
    aport = [(pd.Timestamp(f), x) for f, x in gestor_capital.aportaciones(conf_cap)]
    for h in historial:
        h["aportado"] = float(conf_cap["inicial_eur"]) + sum(x for f, x in aport if f <= pd.Timestamp(h["fecha"]))
    hist_tac = dict(tac.get("historial") or [])
    hist_est = dict((est.get("virtual") or {}).get("historial") or [])
    for h in historial:
        h["tactico"], h["estructural"] = hist_tac.get(h["fecha"]), hist_est.get(h["fecha"])

    # SPY desde el inicio, como referencia
    spy_rent = None
    try:
        from src.config import load_universe
        from src.data.store import close_matrix
        spy = close_matrix([a for a in load_universe() if a["ticker"] == "SPY"])["SPY"].dropna()
        base = spy[spy.index <= pd.Timestamp(conf_cap["inicio"])]
        if len(base):
            spy_rent = num(spy.iloc[-1] / base.iloc[-1] - 1)
    except Exception:  # noqa: BLE001
        pass

    equity = alp.get("equity_cuenta_usd")
    cartera = {
        "total": num(t.get("valor"), 2), "aportado": aportado, "resultado": num((t.get("valor") or 0) - aportado, 2),
        "drawdown": num(t.get("drawdown")), "fase": fases[fase].get("nombre"), "fase_n": fase,
        "reparto": cap.get("reparto") or {"tactico": fases[fase]["tactico"], "estructural": fases[fase]["estructural"]},
        "siguiente_fase_eur": fases[fase].get("hasta_eur"), "histeresis_dias": sistema["fases"]["histeresis_dias"],
        "aportacion_mensual": conf_cap.get("aportacion_mensual_eur"), "inicio": conf_cap.get("inicio"),
        "historial": historial, "spy_rent": spy_rent,
        "cuenta_real": {"equity_usd": num(equity, 2),
                        "resultado_usd": num((equity or BASE_CUENTA_USD) - BASE_CUENTA_USD, 2),
                        "capital_gestionado_usd": num(alp.get("capital_gestionado_usd"), 2),
                        "invertido_usd": num(alp.get("valor_posiciones_usd"), 2)},
    }

    # --- Motores
    motores = [
        {"id": "tactico", "nombre": "Motor táctico", "valor": num(tac.get("valor_total_eur"), 2),
         "parte": cartera["reparto"].get("tactico"), "modo": conf_tac.get("modo"),
         "kill_switch": ", ".join(sorted({e.get("kill_switch", "NORMAL") for e in (tac.get("estrategias") or {}).values()})) or "NORMAL",
         "descripcion": "Operaciones de días a semanas en acciones y ETFs de EEUU (velas de media sesión)."},
        {"id": "estructural", "nombre": "Motor estructural", "valor": num((est.get("virtual") or {}).get("valor"), 2),
         "parte": cartera["reparto"].get("estructural"), "modo": "paper",
         "kill_switch": est.get("kill_switch", "NORMAL"),
         "descripcion": "Tendencias largas con datos diarios. En la fase agresiva, solo cripto."},
    ]

    # --- Estrategias en vivo (con el semáforo del auditor)
    filas_aud = {f["id"]: f for f in aud.get("estrategias", [])}
    vivas = []
    for item in conf_tac.get("estrategias") or []:
        eid = item["id"] if isinstance(item, dict) else item
        nombre, mercado = nombre_tactico(eid)
        f = filas_aud.get(eid, {})
        e_tac = (tac.get("estrategias") or {}).get(eid, {})
        vivas.append({"id": eid, "nombre": nombre, "motor": "táctico", "mercado": mercado,
                      "estado": item.get("estado", "aprobada") if isinstance(item, dict) else "aprobada",
                      "descripcion": DESCRIPCIONES.get(eid, ""), "valor": num(e_tac.get("valor_eur"), 2),
                      "operaciones_vivo": e_tac.get("operaciones"), "semaforo": f.get("semaforo"), "motivo": f.get("motivo"),
                      "rent_vivo": f.get("rent_vivo"), "ref": f.get("ref")})
    for c in sistema["estrategias"]:
        f = filas_aud.get(c["id"], {})
        vivas.append({"id": c["id"], "nombre": POR_ID[c["id"]]["nombre"], "motor": "estructural", "mercado": "cripto",
                      "estado": c["estado"], "descripcion": DESCRIPCIONES.get(c["id"], ""),
                      "invertida": bool(est.get("cartera")), "semaforo": f.get("semaforo"), "motivo": f.get("motivo"),
                      "rent_vivo": f.get("rent_vivo"), "ref": f.get("ref")})

    ids_vivos = {v["id"] for v in vivas}
    candidatas = [s for s in (lab_t.get("estrategias", []) + lab_d.get("estrategias", []) + bib.get("estrategias", []))
                  if s.get("veredicto") in ("APROBADA", "OBSERVACIÓN") and s.get("id") not in ids_vivos]
    vistos, cand = set(), []
    for s in candidatas:
        if s["id"] not in vistos:
            vistos.add(s["id"])
            cand.append(s)
    todas = lab_t.get("estrategias", []) + lab_d.get("estrategias", []) + bib.get("estrategias", [])
    recuento = {k: sum(1 for s in todas if s.get("veredicto") == k) for k in ("APROBADA", "OBSERVACIÓN", "RECHAZADA")}
    rechazadas = sorted([s for s in todas if s.get("veredicto") == "RECHAZADA"],
                        key=lambda s: -(s.get("sharpe_test") or -9))[:12]

    # --- Posiciones abiertas (simulación táctica + datos reales de Alpaca)
    det = alp.get("detalle_posiciones") or {}
    posiciones = []
    for p in (tac.get("posiciones") or {}).values():
        r = det.get(p["activo"].replace("/", ""), {})
        posiciones.append({"activo": p["activo"], "motor": "táctico", "entrada": hora(p["entrada"]),
                           "precio_entrada": num(r.get("avg_entry_price") or p["precio_entrada"]),
                           "precio_actual": num(r.get("current_price")), "stop": num(p["stop"]),
                           "stop_real": (alp.get("stops") or {}).get(p["activo"]) is not None,
                           "invertido_usd": num(r.get("cost_basis"), 2), "valor_usd": num(r.get("market_value"), 2),
                           "resultado_usd": num(r.get("unrealized_pl"), 2), "resultado_pct": num(r.get("unrealized_plpc")),
                           "importe_eur": num(p.get("importe_eur"), 2)})
    for a, w in (est.get("cartera") or {}).items():
        r = det.get(a.replace("-", ""), {})
        posiciones.append({"activo": a, "motor": "estructural", "entrada": None,
                           "precio_entrada": num(r.get("avg_entry_price")), "precio_actual": num(r.get("current_price")),
                           "stop": None, "stop_real": False, "invertido_usd": num(r.get("cost_basis"), 2),
                           "valor_usd": num(r.get("market_value"), 2), "resultado_usd": num(r.get("unrealized_pl"), 2),
                           "resultado_pct": num(r.get("unrealized_plpc")),
                           "importe_eur": num(w * ((est.get("virtual") or {}).get("valor") or 0), 2)})
    pendientes = [{"activo": p["activo"], "accion": p["accion"], "importe_eur": num(p.get("importe_eur"), 2),
                   "motivo": p.get("motivo")} for p in (tac.get("pendientes") or {}).values()]

    # --- Diario: operaciones cerradas y actividad reciente
    ruta_d = ROOT / "diario" / "operaciones.csv"
    d = pd.read_csv(ruta_d) if ruta_d.exists() else pd.DataFrame(columns=["tipo"])
    cerradas = operaciones_cerradas(d) if len(d) else []
    actividad = []
    for r in d.tail(60).itertuples():
        if r.tipo == "alerta":
            actividad.append({"fecha": hora(r.fecha_utc), "tipo": "señal", "activo": r.activo, "accion": r.accion,
                              "texto": str(r.detalle) if isinstance(r.detalle, str) else ""})
        elif r.tipo == "orden" and str(r.estado) == "filled":
            actividad.append({"fecha": hora(r.fecha_ejecucion if isinstance(r.fecha_ejecucion, str) else r.fecha_utc),
                              "tipo": "orden", "activo": r.activo, "accion": r.accion,
                              "texto": f"{r.cantidad_ejecutada:g} a {float(r.precio_ejecucion):.2f} $"})
    actividad = sorted(actividad, key=lambda a: a["fecha"] or "", reverse=True)[:25]

    # --- Investigador y laboratorio
    from src.research import cribado as mod_cribado, registro
    cr = mod_cribado.cargar()
    ideas = []
    for r in cr.iloc[::-1].head(30).itertuples():
        ideas.append({"fecha": r.fecha, "idea": r.idea, "fuente": r.fuente if isinstance(r.fuente, str) else "",
                      "url": r.url if isinstance(r.url, str) and str(r.url).startswith("https://") else "",
                      "familia": r.familia, "mercado": r.mercado, "pasa": str(r.pasa) == "True",
                      "sharpe": num(r.sharpe), "cagr": num(r.cagr), "max_dd": num(r.max_dd),
                      "correlacion": num(getattr(r, "correlacion", None)), "motivo": r.motivo})
    fichas = []
    carpeta_f = ROOT / "research" / "fichas"
    for f in sorted(carpeta_f.glob("*.md"), reverse=True)[:12] if carpeta_f.exists() else []:
        titulo = next((ln.lstrip("# ").strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.startswith("#")), f.stem)
        fichas.append({"archivo": f.name, "fecha": f.name[:10], "titulo": titulo})
    investigacion = {"pruebas": registro.numero_pruebas(), "cribadas": int(len(cr)),
                     "pasaron": int((cr["pasa"].astype(str) == "True").sum()) if len(cr) else 0,
                     "ideas": ideas, "fichas": fichas,
                     "proxima": "sábados a las 08:53 (Madrid)"}

    # --- Agentes: última ejecución y si va al día
    fecha_inv = max([str(x) for x in cr["fecha"].dropna()] + [f["fecha"] for f in fichas], default=None) if len(cr) or fichas else None
    laborable = ahora.weekday() < 5

    def agente(nombre, que, cuando, ultima, limite_h):
        u = hora(ultima)
        ok = None
        if u:
            ok = (ahora - pd.Timestamp(u).to_pydatetime()) < timedelta(hours=limite_h)
        return {"nombre": nombre, "que": que, "cuando": cuando, "ultima": u, "al_dia": ok}

    agentes = [
        agente("Datos y motor estructural", "Descarga precios, calcula señales y reparto, aportaciones y kill-switch",
               "2 veces al día", est.get("actualizado"), 30),
        agente("Escáner táctico", "Busca señales de compra y venta en 34 acciones/ETFs con velas de 1 hora",
               "cada hora (laborables)", tac.get("actualizado"), 6 if laborable else 30),
        agente("Ejecución", "Envía órdenes y stops a Alpaca paper y comprueba que la cuenta cuadra",
               "tras cada escaneo", alp.get("actualizado"), 6 if laborable else 30),
        agente("Auditor", "Compara el resultado en vivo con el backtest y mide el coste real",
               "lunes", aud.get("fecha"), 24 * 8),
        agente("Laboratorio", "Prueba todas las familias de estrategias en todos los mercados",
               "domingos", lab_t.get("fecha") or lab_d.get("fecha"), 24 * 8),
        agente("Investigador (IA)", "Busca ideas nuevas en papers, YouTube, TradingView y foros, y las criba",
               "sábados", fecha_inv, 24 * 8),
        agente("Vigilante", "Avisa por Telegram si algo deja de funcionar",
               "cada 4 horas", vig.get("revisado"), 6),
    ]

    datos = {
        "generado": ahora.isoformat(timespec="minutes"), "cartera": cartera, "motores": motores,
        "estrategias": {"vivas": vivas, "candidatas": cand[:10], "recuento": recuento, "rechazadas": rechazadas},
        "posiciones": posiciones, "pendientes": pendientes, "cerradas": cerradas[:30], "actividad": actividad,
        "investigacion": investigacion, "agentes": agentes,
        "avisos": [v["texto"] for v in (vig.get("activos") or {}).values()],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    print(f"Panel exportado: {SALIDA} ({SALIDA.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
