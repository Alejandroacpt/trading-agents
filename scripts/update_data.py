"""
Script del pipeline diario (paso 1: datos).

Qué hace:
  1. Descarga los precios de todo el universo.
  2. Guarda los CSV en data/ y el informe en reports/data_status.md.
  3. Envía un resumen por Telegram (si está configurado).

Uso:
    python scripts/update_data.py            -> descarga y avisa por Telegram
    python scripts/update_data.py --sin-telegram
"""

import sys
from pathlib import Path

# Permite ejecutar el script desde la raíz del repo: python scripts/update_data.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import telegram  # noqa: E402
from src.data.update import guardar_informe, resumen_telegram, update_all  # noqa: E402


def main() -> int:
    enviar = "--sin-telegram" not in sys.argv

    print("Descargando datos del universo...")
    resultados = update_all()

    informe = guardar_informe(resultados)
    print(f"Informe guardado en {informe}")

    resumen = resumen_telegram(resultados)
    print("\n" + resumen)

    # Solo se avisa por Telegram si algún activo tiene problemas: el resumen
    # diario de la cartera (paso 2) ya incluye los movimientos del día.
    hay_problemas = any(r["estado"] != "OK" for r in resultados)
    if enviar and hay_problemas:
        telegram.send_message(resumen, silencioso=True)

    # El script termina con error solo si NO se pudo actualizar ningún activo
    # (señal de un fallo general: sin internet, Yahoo caído...). Así GitHub
    # te avisa por correo de que algo va mal.
    if not any(r["guardado"] for r in resultados):
        print("ERROR: no se actualizó ningún activo")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
