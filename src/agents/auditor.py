"""
AGENTE AUDITOR
--------------
Cada semana compara lo que pasa EN VIVO con lo que prometía el BACKTEST
y avisa si una estrategia se está degradando.

Para cada estrategia activa:
  - Rendimiento en vivo desde la puesta en marcha (mismo motor y mismos
    costes que el backtest, con los precios reales de cada día).
  - Banda esperada: con la rentabilidad y volatilidad del backtest, entre
    qué valores debería estar el resultado en vivo el 95 % de las veces.
  - Semáforo:
      🔴 DEGRADADA  caída en vivo peor que la peor del backtest, o tras 12
                   meses un Sharpe en vivo < 50 % del backtest -> proponer
                   reducir o retirar.
      🟠 VIGILAR    caída en vivo > 75 % de la peor del backtest, Sharpe en
                   vivo negativo tras 6 meses, o resultado fuera de la banda.
      🟢 OK         dentro de lo esperado.
      ⚪ POCOS DATOS menos de 3 meses: solo se vigila la caída.

Cubre los DOS motores: las estrategias del estructural (backtest diario)
y las del táctico (simulación de operaciones con las velas reales).

Además: cartera total (aportado frente a resultado, fase), desviación de
la cuenta paper frente a la cartera objetivo, calidad de ejecución (precio
real frente a referencia) y actividad de la semana.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.backtest import metrics
from src.backtest.engine import run_backtest
from src.backtest.validator import rent_liquidez, validar


def rendimiento_vivo(estrategia: dict, precios_todos: pd.DataFrame, clases: dict, inicio: str) -> pd.Series:
    cols = [c for c in estrategia["universo"] if c in precios_todos.columns]
    p = precios_todos[cols].dropna(how="all")
    liq = rent_liquidez(precios_todos, p.index)
    obj = estrategia["senales"](p, **estrategia["parametros"])
    # Se simula desde un poco antes para que la posición inicial ya esté construida
    res = run_backtest(p, obj, clases, liq, inicio=pd.Timestamp(inicio) - pd.Timedelta(days=10))
    return res.rentabilidad[res.rentabilidad.index > pd.Timestamp(inicio)]


def semaforo(vivo: pd.Series, ref: dict) -> tuple[str, str]:
    dias = (vivo.index[-1] - vivo.index[0]).days if len(vivo) > 1 else 0
    dd_vivo = metrics.drawdown(vivo).min() if len(vivo) else 0.0
    dd_ref = ref["max_drawdown"]
    rent_vivo = float((1 + vivo).prod() - 1) if len(vivo) else 0.0

    if dd_vivo <= dd_ref:
        return "🔴 DEGRADADA", f"Caída en vivo ({dd_vivo:.0%}) peor que la peor del backtest ({dd_ref:.0%}). Proponer retirarla."
    if dias >= 365:
        sr = metrics.sharpe(vivo)
        if sr < 0.5 * ref["sharpe"]:
            return "🔴 DEGRADADA", f"Tras {dias} días, Sharpe en vivo {sr:.2f} < 50 % del backtest ({ref['sharpe']:.2f}). Proponer reducirla."
    if dd_vivo <= 0.75 * dd_ref:
        return "🟠 VIGILAR", f"Caída en vivo ({dd_vivo:.0%}) cerca de la peor del backtest ({dd_ref:.0%})."
    if dias < 90:
        return "⚪ POCOS DATOS", f"{dias} días en vivo: aún no se puede juzgar (mínimo 3 meses)."
    if dias >= 182 and metrics.sharpe(vivo) < 0:
        return "🟠 VIGILAR", "Sharpe en vivo negativo tras 6 meses."
    t = dias / 365.25
    esperado = (1 + ref["cagr"]) ** t - 1
    margen = 1.96 * ref["volatilidad"] * np.sqrt(t)
    if not (esperado - margen <= rent_vivo <= esperado + margen):
        return "🟠 VIGILAR", (f"Resultado en vivo ({rent_vivo:+.1%}) fuera de la banda esperada "
                             f"({esperado - margen:+.1%} a {esperado + margen:+.1%}).")
    return "🟢 OK", "Dentro de lo esperado según el backtest."


def vivo_tactico(equity: pd.Series, inicio_vivo: str) -> pd.Series:
    """Rentabilidad diaria en vivo de una estrategia táctica (su valor liquidativo)."""
    e = equity[equity.index >= pd.Timestamp(inicio_vivo)]
    if e.empty:
        return pd.Series(dtype=float)
    diaria = e.groupby(e.index.normalize()).last()
    return diaria.pct_change().dropna()


def fila(id_, nombre, estado, vivo: pd.Series, ref: dict, motor: str) -> dict:
    luz, motivo = semaforo(vivo, ref) if len(vivo) else ("⚪ POCOS DATOS", "Aún sin días completos en vivo.")
    return {"id": id_, "nombre": nombre, "estado": estado, "motor": motor,
            "dias": (vivo.index[-1] - vivo.index[0]).days if len(vivo) > 1 else 0,
            "rent_vivo": float((1 + vivo).prod() - 1) if len(vivo) else 0.0,
            "dd_vivo": float(metrics.drawdown(vivo).min()) if len(vivo) else 0.0,
            "ref": ref, "semaforo": luz, "motivo": motivo}


def desviacion_cuenta(alp: dict) -> dict | None:
    """¿Coinciden las posiciones reales de la cuenta paper con la cartera objetivo?"""
    pos, obj, cap = alp.get("posiciones"), alp.get("objetivo"), alp.get("capital_gestionado_usd")
    if pos is None or obj is None or not cap:
        return None
    activos = set(pos) | set(obj)
    difs = {t: pos.get(t, 0.0) / cap - obj.get(t, 0.0) for t in activos}
    grandes = {t: d for t, d in difs.items() if abs(d) > 0.05}
    return {"total": float(sum(abs(d) for d in difs.values())), "grandes": grandes}


def calidad_ejecucion(diario: pd.DataFrame, dias: int = 7) -> dict:
    if diario.empty:
        return {"ordenes": 0, "ejecutadas": 0, "errores": 0, "coste_medio": np.nan, "alertas": 0}
    d = diario.copy()
    d["fecha"] = pd.to_datetime(d["fecha_utc"], errors="coerce", utc=True)
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    d = d[d["fecha"] >= desde]
    ordenes = d[(d["tipo"] == "orden") & (d["estado"].astype(str) != "simulada")]
    costes = pd.to_numeric(ordenes["coste_ejecucion"], errors="coerce").dropna()
    return {
        "ordenes": int(len(ordenes)),
        "ejecutadas": int((ordenes["estado"].astype(str) == "filled").sum()),
        "errores": int((ordenes["estado"].astype(str) == "error").sum()),
        "coste_medio": float(costes.mean()) if len(costes) else np.nan,
        "alertas": int((d["tipo"] == "alerta").sum()),
    }


def auditar(estrategias: list[dict], configs: dict, precios: pd.DataFrame, clases: dict,
            estado: dict, diario: pd.DataFrame, capital_inicial: float = 1000.0,
            filas_tacticas: list[dict] | None = None, capital: dict | None = None) -> dict:
    inicio = estado["virtual"]["inicio"]
    filas = []
    for e in estrategias:
        v = validar(e, precios, clases)
        ref = v["periodos"]["completo"]
        vivo = rendimiento_vivo(e, precios, clases, inicio)
        filas.append(fila(e["id"], e["nombre"], configs[e["id"]]["estado"], vivo, ref, "estructural"))
    filas += filas_tacticas or []

    v = estado["virtual"]
    alp = estado.get("alpaca", {})
    hist = alp.get("historial", [])
    paper = None
    if alp.get("fuente_capital") == "cuenta" and len(hist) >= 2:
        paper = hist[-1][1] / hist[0][1] - 1
    return {
        "fecha": datetime.now(timezone.utc).date().isoformat(),
        "inicio": inicio,
        "estrategias": filas,
        "virtual": {"valor": v["valor"], "maximo": v["maximo"], "rent": v["valor"] / capital_inicial - 1},
        "paper": {"modo": alp.get("modo", "-"), "fuente": alp.get("fuente_capital", "-"), "rent": paper,
                  "equity": alp.get("equity_cuenta_usd")},
        "ejecucion": calidad_ejecucion(diario),
        "kill_switch": estado.get("kill_switch", "NORMAL"),
        "desviacion": desviacion_cuenta(alp),
        "total": capital or {},
    }


def _pct(x, dec=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100 + 0.0:+.{dec}f} %".replace(".", ",")


def _num(x, dec=2):
    return f"{x:.{dec}f}".replace(".", ",")


def _eur(x, dec=2):
    return f"{x:,.{dec}f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def informe_markdown(a: dict) -> str:
    L = [f"# Informe del auditor · {a['fecha']}", "",
         f"En vivo desde el {a['inicio']}. Kill-switch: **{a['kill_switch']}**.", "",
         "## Estrategias", "",
         "| Motor | Estrategia | Estado | Días | Resultado en vivo | Caída en vivo | Backtest: CAGR / Sharpe / peor caída | Semáforo |",
         "|---|---|---|---|---|---|---|---|"]
    for f in a["estrategias"]:
        r = f["ref"]
        L.append(f"| {f.get('motor', 'estructural')} | {f['nombre']} | {f['estado']} | {f['dias']} | {_pct(f['rent_vivo'])} | {_pct(f['dd_vivo'])} | "
                 f"{_pct(r['cagr'])} / {_num(r['sharpe'])} / {_pct(r['max_drawdown'], 0)} | {f['semaforo']} |")
    L += [""] + [f"- **{f['nombre']}**: {f['motivo']}" for f in a["estrategias"]]
    v, p, e = a["virtual"], a["paper"], a["ejecucion"]
    t = a.get("total") or {}
    L += ["", "## Carteras", ""]
    if t:
        L += [f"- **Cartera total: {_eur(t['valor'])}** · aportado {_eur(t['aportado'])} · resultado {_eur(t['valor'] - t['aportado'])} "
              f"· caída desde máximo {_pct(t.get('drawdown', 0))} · fase {t.get('fase_nombre', '-')} "
              f"({t.get('reparto', {}).get('tactico', 0):.0%} táctico / {t.get('reparto', {}).get('estructural', 0):.0%} estructural)",
              f"- Motor táctico: {_eur(t.get('valor_tactico', 0))} · kill-switch {t.get('kill_tactico', '-')}"]
    L += [f"- Motor estructural: {_eur(v['valor'])} ({_pct(v['rent'])} sobre su capital); máximo {_eur(v['maximo'])}",
          f"- Cuenta paper (modo {p['modo']}, capital: {p['fuente']}): "
          + (f"{_pct(p['rent'])}" if p["rent"] is not None else "sin comparación (cuenta sin ajustar al capital del sistema)"),
          "- Cuenta paper frente a la cartera objetivo: " + (
              "sin datos todavía" if not a.get("desviacion") else
              f"desviación total {_pct(a['desviacion']['total'])}"
              + (" · grandes: " + ", ".join(f"{k} {_pct(d)}" for k, d in a["desviacion"]["grandes"].items())
                 if a["desviacion"]["grandes"] else " (todo en su sitio)")),
          "", "## Actividad de la semana", "",
          f"- Alertas: {e['alertas']}",
          f"- Órdenes paper: {e['ordenes']} (ejecutadas {e['ejecutadas']}, errores {e['errores']})",
          f"- Diferencia media entre el precio de ejecución y el de referencia: {_pct(e['coste_medio'], 2)} "
          "(positivo = peor para nosotros; incluye el movimiento del mercado desde el último cierre)", ""]
    return "\n".join(L) + "\n"


def resumen_telegram(a: dict) -> str:
    L = [f"🧾 Auditor semanal · {a['fecha']}"]
    for f in a["estrategias"]:
        L.append(f"{f['semaforo']} {f['nombre'].split(' (')[0]}: {_pct(f['rent_vivo'])} en vivo ({f['dias']} días)")
    v, e, t = a["virtual"], a["ejecucion"], a.get("total") or {}
    if t:
        L += ["", f"💼 Total: {_eur(t['valor'], 0)} (aportado {_eur(t['aportado'], 0)}, resultado {_eur(t['valor'] - t['aportado'], 0)})"]
    if a.get("desviacion") and a["desviacion"]["grandes"]:
        L += ["⚠️ La cuenta paper no coincide con el objetivo: " + ", ".join(a["desviacion"]["grandes"])]
    L += [f"Estructural: {_eur(v['valor'], 0)} ({_pct(v['rent'])})",
          f"Semana: {e['alertas']} alertas, {e['ordenes']} órdenes paper ({e['errores']} errores)"]
    alarmas = [f for f in a["estrategias"] if f["semaforo"].startswith(("🔴", "🟠"))]
    if alarmas:
        L += [""] + [f"⚠️ {f['nombre'].split(' (')[0]}: {f['motivo']}" for f in alarmas]
    return "\n".join(L)
