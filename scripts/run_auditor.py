"""
Informe semanal del auditor.

Compara el rendimiento en vivo de cada estrategia activa con su backtest,
revisa la calidad de ejecución y guarda el informe en
reports/auditor/AAAA-MM-DD.md (y reports/auditor/ultimo.md).

Uso:
    python scripts/run_auditor.py [--sin-telegram]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import auditor, cartera_virtual, diario  # noqa: E402
from src.agents.escaner import POR_ID, cargar_sistema  # noqa: E402
from src.alerts import telegram  # noqa: E402
from src.config import REPORTS_DIR, load_universe  # noqa: E402
from src.data.store import close_matrix  # noqa: E402


def main() -> int:
    estado = cartera_virtual.cargar()
    if not estado:
        print("Aún no hay cartera en vivo (state/estado.json).")
        return 0
    universo = load_universe()
    clases = {a["ticker"]: a["clase"] for a in universo}
    precios = close_matrix(universo)
    sistema = cargar_sistema()
    configs = {c["id"]: c for c in sistema["estrategias"]}
    estrategias = [POR_ID[c["id"]] for c in sistema["estrategias"]]

    ruta_alpaca = cartera_virtual.RUTA_ESTADO.parent / "alpaca.json"
    if ruta_alpaca.exists():
        estado = {**estado, "alpaca": json.loads(ruta_alpaca.read_text(encoding="utf-8"))}
    # Motor táctico: valor liquidativo en vivo frente a su backtest
    from src.agents import capital as gestor_capital
    from src.backtest.validator import validar
    from src.data import horario
    from src.tactico import laboratorio
    conf_tac = horario.cargar_config()
    filas_tac = []
    for item in conf_tac.get("estrategias") or []:
        eid = item["id"] if isinstance(item, dict) else item
        familia, mercado = eid.removeprefix("tac_").split("__")
        res, fam, _ = laboratorio.simular_en_vivo(eid, conf_tac["inicio_vivo"])
        ref = validar(laboratorio.experimento(familia, mercado), None, {})["periodos"]["completo"]
        nombre = fam["nombre"].replace("(4 h)", "(media sesión)") if mercado == "acciones" else fam["nombre"]
        filas_tac.append(auditor.fila(eid, nombre, item.get("estado", "aprobada") if isinstance(item, dict) else "aprobada",
                                      auditor.vivo_tactico(res.equity, conf_tac["inicio_vivo"]), ref, "táctico"))
    estado_cap = gestor_capital.cargar()
    ruta_tac = cartera_virtual.RUTA_ESTADO.parent / "tactico.json"
    tac = json.loads(ruta_tac.read_text(encoding="utf-8")) if ruta_tac.exists() else {}
    total = None
    if estado_cap.get("total"):
        f = estado_cap.get("fase", 0)
        total = {**estado_cap["total"], "aportado": gestor_capital.capital_aportado(sistema["capital"]),
                 "reparto": estado_cap.get("reparto", {}), "fase_nombre": sistema["fases"]["tramos"][f].get("nombre", f),
                 "valor_tactico": tac.get("valor_total_eur", 0.0),
                 "kill_tactico": ", ".join(sorted({e.get("kill_switch", "NORMAL") for e in tac.get("estrategias", {}).values()})) or "-"}
    a = auditor.auditar(estrategias, configs, precios, clases, estado, diario.cargar(),
                        estado.get("capital_eur", 1000.0), filas_tac, total)
    carpeta = REPORTS_DIR / "auditor"
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = auditor.informe_markdown(a)
    (carpeta / f"{a['fecha']}.md").write_text(texto, encoding="utf-8")
    (carpeta / "ultimo.md").write_text(texto, encoding="utf-8")
    from src.research.resumen_json import _num  # noqa: E402
    filas = [{"id": f["id"], "nombre": f["nombre"], "motor": f.get("motor", "estructural"), "estado": f["estado"],
              "dias": f["dias"], "rent_vivo": _num(f["rent_vivo"]), "dd_vivo": _num(f["dd_vivo"]),
              "semaforo": f["semaforo"], "motivo": f["motivo"],
              "ref": {k: _num(f["ref"].get(k)) for k in ("cagr", "sharpe", "max_drawdown")}} for f in a["estrategias"]]
    (carpeta / "ultimo.json").write_text(json.dumps({"fecha": a["fecha"], "estrategias": filas,
                                                      "ejecucion": {k: (_num(v) if isinstance(v, float) else v)
                                                                    for k, v in a["ejecucion"].items()}},
                                                     ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    resumen = auditor.resumen_telegram(a)
    print(texto)
    print(resumen)
    if "--sin-telegram" not in sys.argv:
        hay_alarma = any(f["semaforo"].startswith("🔴") for f in a["estrategias"])
        telegram.send_message(resumen, silencioso=not hay_alarma)
    return 0


if __name__ == "__main__":
    sys.exit(main())
