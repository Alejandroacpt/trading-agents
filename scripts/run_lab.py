"""
Laboratorio semanal: prueba todas las familias en todos los mercados.

Qué hace:
  1. Valida cada combinación familia × mercado con todo el histórico.
  2. Apunta cada variante en el registro de pruebas (research/registro_pruebas.csv).
  3. Calcula el Sharpe deflactado con el total de pruebas de toda la vida del proyecto.
  4. Clasifica por mercado y detecta propuestas (aprobadas que no operan).
  5. Guarda reports/laboratorio/ultimo.md (+ copia con fecha) y avisa por Telegram.

Uso:
    python scripts/run_lab.py [--sin-telegram] [--solo MERCADO]
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.escaner import POR_ID, cargar_sistema  # noqa: E402
from src.alerts import telegram  # noqa: E402
from src.backtest import validator  # noqa: E402
from src.config import REPORTS_DIR, load_universe  # noqa: E402
from src.data.macro import cargar_tipos, forex_con_carry  # noqa: E402
from src.data.store import close_matrix  # noqa: E402
from src.research import laboratorio, registro  # noqa: E402

ICONO = {"APROBADA": "✅", "OBSERVACIÓN": "🟡", "RECHAZADA": "❌"}


def _n(x, dec=2):
    return "-" if x is None or x != x else f"{x:.{dec}f}".replace(".", ",")


def _p(x, dec=0):
    return "-" if x is None or x != x else f"{x * 100:.{dec}f} %".replace(".", ",")


def _spy(v):
    s = v.get("spy") or {}
    return f"{_p(s['cagr'])} / {_p(s['cagr_spy'])}" if s else "—"


def main() -> int:
    universo = load_universe()
    clases = {a["ticker"]: a["clase"] for a in universo}
    precios = close_matrix(universo)
    # Forex con carry incluido (rentabilidad total), si hay tipos descargados
    con_carry = not cargar_tipos().empty
    precios = forex_con_carry(precios)
    experimentos = laboratorio.todos_los_experimentos()
    if "--solo" in sys.argv:
        m = sys.argv[sys.argv.index("--solo") + 1]
        experimentos = [e for e in experimentos if e["mercado"] == m]

    validaciones = []
    for e in experimentos:
        print(f"Probando {e['nombre']}...")
        try:
            validaciones.append(validator.validar(e, precios, clases))
        except Exception as ex:  # noqa: BLE001 - un experimento roto no para el laboratorio
            print(f"  ERROR: {ex}")

    total = registro.registrar(validaciones, origen="laboratorio")
    validator.anadir_dsr(validaciones, n_minimo=total)
    for v in validaciones:
        v["veredicto"] = validator.veredicto(v)

    # Estrategias que ya operan, por mercado (con sus métricas, para comparar)
    sistema = cargar_sistema()
    en_vivo, metricas_vivo = {}, {}
    for c in sistema["estrategias"]:
        e_vivo = POR_ID[c["id"]]
        vv = validator.validar(e_vivo, precios, clases)
        metricas_vivo[c["id"]] = vv["periodos"]
        for m in laboratorio.mercado_de_estrategia(e_vivo):
            en_vivo.setdefault(m, []).append(c["id"])

    def describe_vivo(m_id):
        if not en_vivo.get(m_id):
            return "ninguna estrategia"
        return "; ".join(f"{POR_ID[i]['nombre']} (Sharpe test {_n(metricas_vivo[i]['test'].get('sharpe'))}, "
                         f"peor caída {_p(metricas_vivo[i]['completo']['max_drawdown'])})" for i in en_vivo[m_id])

    def mejora_lo_actual(v):
        """Aprobada y mejor que lo que ya opera en su mercado (Sharpe de test mayor y caída no peor)."""
        m_id = v["estrategia"]["mercado"]
        p = v["periodos"]
        for i in en_vivo.get(m_id, []):
            pv = metricas_vivo[i]
            if p["test"].get("sharpe", -9) <= pv["test"].get("sharpe", -9) or \
               p["completo"]["max_drawdown"] < pv["completo"]["max_drawdown"]:
                return False
        return True

    fecha = datetime.now(timezone.utc).date().isoformat()
    L = [f"# Laboratorio de estrategias · {fecha}", "",
         f"{len(validaciones)} experimentos (familia × mercado). Pruebas acumuladas en el registro: **{total}** "
         "(el Sharpe deflactado se calcula con este total).", "",
         "Forex medido " + ("**con carry** (diferencial de tipos de interés incluido)." if con_carry
                            else "**sin carry** (aún no hay tipos de interés descargados)."), "",
         "> Las propuestas no se activan solas: hay que decidir si entran en `config/sistema.yaml`.", ""]
    propuestas, aprobadas_peores, mejores = [], [], {}
    for m_id, mer in laboratorio.MERCADOS.items():
        vs = [v for v in validaciones if v["estrategia"]["mercado"] == m_id]
        if not vs:
            continue
        vs.sort(key=lambda v: (["APROBADA", "OBSERVACIÓN", "RECHAZADA"].index(v["veredicto"]["decision"]),
                               -v["periodos"]["test"].get("sharpe", -9)))
        mejores[m_id] = vs[0]
        L += [f"## {mer['nombre']}", "",
              f"En vivo hoy: {describe_vivo(m_id)}.", "",
              "| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |",
              "|---|---|---|---|---|---|---|---|"]
        for v in vs:
            p, vd = v["periodos"], v["veredicto"]
            L.append(f"| {v['estrategia']['nombre'].split(' · ')[0]} | {ICONO[vd['decision']]} {vd['decision']} | "
                     f"{_n(p['completo']['sharpe'])} | {_n(p['test'].get('sharpe'))} | "
                     f"{_p(p['completo']['max_drawdown'])} | {_p(v.get('dsr'))} | {_spy(v)} | {', '.join(vd['fallos']) or '—'} |")
            if vd["decision"] == "APROBADA":
                (propuestas if mejora_lo_actual(v) else aprobadas_peores).append(v)
        L.append("")

    L += ["## Propuestas", ""]
    if propuestas:
        for v in propuestas:
            p = v["periodos"]
            L.append(f"- **{v['estrategia']['nombre']}**: Sharpe {_n(p['completo']['sharpe'])} "
                     f"(test {_n(p['test']['sharpe'])}), peor caída {_p(p['completo']['max_drawdown'])}.")
    else:
        L.append("Ninguna esta semana: ningún experimento aprobado mejora lo que ya opera en su mercado.")
    if aprobadas_peores:
        L += ["", "Aprobadas que NO mejoran lo que ya opera en su mercado (no se proponen):"]
        L += [f"- {v['estrategia']['nombre']}: Sharpe test {_n(v['periodos']['test']['sharpe'])}, "
              f"peor caída {_p(v['periodos']['completo']['max_drawdown'])}. En vivo: "
              f"{describe_vivo(v['estrategia']['mercado'])}." for v in aprobadas_peores]

    carpeta = REPORTS_DIR / "laboratorio"
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = "\n".join(L) + "\n"
    (carpeta / f"{fecha}.md").write_text(texto, encoding="utf-8")
    (carpeta / "ultimo.md").write_text(texto, encoding="utf-8")
    from src.research import resumen_json  # noqa: E402
    resumen_json.guardar(validaciones, "diario", carpeta / "ultimo.json")
    print(texto)

    # Telegram: lo mejor de cada mercado y las propuestas
    msg = [f"🔬 Laboratorio semanal · {len(validaciones)} experimentos · {total} pruebas acumuladas", ""]
    for m_id, v in mejores.items():
        vd, p = v["veredicto"], v["periodos"]
        msg.append(f"{ICONO[vd['decision']]} {laboratorio.MERCADOS[m_id]['nombre']}: "
                   f"{v['estrategia']['nombre'].split(' · ')[0]} (Sharpe test {_n(p['test'].get('sharpe'))})")
    if propuestas:
        msg += ["", "📌 Propuestas para operar: " + "; ".join(v["estrategia"]["nombre"] for v in propuestas)]
    if "--sin-telegram" not in sys.argv:
        telegram.send_message("\n".join(msg), silencioso=not propuestas)
    print("\n".join(msg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
