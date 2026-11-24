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
    a = auditor.auditar(estrategias, configs, precios, clases, estado, diario.cargar(),
                        estado.get("capital_eur", 1000.0))
    carpeta = REPORTS_DIR / "auditor"
    carpeta.mkdir(parents=True, exist_ok=True)
    texto = auditor.informe_markdown(a)
    (carpeta / f"{a['fecha']}.md").write_text(texto, encoding="utf-8")
    (carpeta / "ultimo.md").write_text(texto, encoding="utf-8")

    resumen = auditor.resumen_telegram(a)
    print(texto)
    print(resumen)
    if "--sin-telegram" not in sys.argv:
        hay_alarma = any(f["semaforo"].startswith("🔴") for f in a["estrategias"])
        telegram.send_message(resumen, silencioso=not hay_alarma)
    return 0


if __name__ == "__main__":
    sys.exit(main())
