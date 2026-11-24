"""
Vigilante: comprueba que el sistema sigue vivo y avisa por Telegram si no.

Cada 4 horas (workflow vigilante.yml) revisa:
  - que el pipeline diario, el escáner táctico y la ejecución en Alpaca se
    han ejecutado hace poco (por la hora guardada en sus estados),
  - que los datos diarios no están atrasados,
  - si algún workflow ha fallado desde la última revisión.
Avisa una vez cuando aparece un problema (con sonido), recuerda cada 24 h
si sigue, y avisa cuando se resuelve. Estado en state/vigilante.json.

Uso:
    python scripts/vigilante.py [--sin-telegram]
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import telegram  # noqa: E402
from src.config import ROOT  # noqa: E402

ESTADO = ROOT / "state"
RUTA = ESTADO / "vigilante.json"
REPO = os.getenv("GITHUB_REPOSITORY", "Alejandroacpt/trading-agents")


def _leer(nombre: str) -> dict:
    p = ESTADO / nombre
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _hora(texto: str | None) -> datetime | None:
    if not texto:
        return None
    t = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def es_laborable(ahora: datetime) -> bool:
    """De lunes 00:00 a viernes 23:59 UTC (horario del escáner táctico cada hora)."""
    return ahora.weekday() < 5


def problemas_de_estado(ahora: datetime, estados: dict) -> dict[str, str]:
    """{clave: descripción} de lo que está parado o atrasado."""
    p = {}
    limites = [
        ("pipeline", "estado.json", "Pipeline diario (estructural y aportaciones)", timedelta(hours=28)),
        ("tactico", "tactico.json", "Escáner táctico",
         timedelta(hours=5) if es_laborable(ahora) else timedelta(hours=8)),
        ("alpaca", "alpaca.json", "Ejecución en Alpaca",
         timedelta(hours=5) if es_laborable(ahora) else timedelta(hours=28)),
    ]
    for clave, archivo, nombre, limite in limites:
        t = _hora(estados.get(archivo, {}).get("actualizado"))
        if t is None:
            p[clave] = f"{nombre}: no hay estado guardado"
        elif ahora - t > limite:
            horas = (ahora - t).total_seconds() / 3600
            p[clave] = f"{nombre}: sin ejecutarse desde hace {horas:.0f} h (último: {t:%d/%m %H:%M} UTC)"
    fecha = estados.get("estado.json", {}).get("fecha_datos")
    if fecha:
        dias = (ahora.date() - datetime.fromisoformat(fecha).date()).days
        if dias > 4:
            p["datos"] = f"Datos diarios atrasados: el último cierre es del {fecha} ({dias} días)"
    return p


def workflows_fallidos(desde: datetime) -> dict[str, str]:
    """Ejecuciones con error desde la última revisión (API de GitHub con el token del workflow)."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return {}
    import requests
    r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs",
                     params={"status": "failure", "per_page": 30,
                             "created": f">={desde.strftime('%Y-%m-%dT%H:%M:%SZ')}"},
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                     timeout=30)
    if r.status_code != 200:
        return {"api": f"No se pudo consultar GitHub (HTTP {r.status_code})"}
    salida = {}
    for run in r.json().get("workflow_runs", []):
        salida[f"fallo-{run['id']}"] = (f"Falló «{run['name']}» el {_hora(run['created_at']):%d/%m %H:%M} UTC: "
                                        f"{run['html_url']}")
    return salida


def main() -> int:
    ahora = datetime.now(timezone.utc)
    previo = _leer("vigilante.json")
    ultima = _hora(previo.get("revisado")) or (ahora - timedelta(hours=4))
    estados = {n: _leer(n) for n in ("estado.json", "tactico.json", "alpaca.json")}

    actuales = problemas_de_estado(ahora, estados)
    # La primera vez no se miran fallos antiguos (ya resueltos): solo desde ahora
    fallos = workflows_fallidos(ultima - timedelta(minutes=5)) if previo else {}
    activos_previos = previo.get("activos", {})

    nuevos = {k: v for k, v in actuales.items() if k not in activos_previos}
    resueltos = [activos_previos[k]["texto"] for k in activos_previos if k not in actuales]
    recordar = [v["texto"] for k, v in activos_previos.items()
                if k in actuales and ahora - _hora(v["avisado"]) > timedelta(hours=24)]

    mensajes = []
    if nuevos or fallos:
        mensajes.append("🚨 Vigilante: algo no va bien\n" + "\n".join(f"• {t}" for t in [*nuevos.values(), *fallos.values()]))
    if recordar:
        mensajes.append("⏰ Vigilante: sigue sin resolverse\n" + "\n".join(f"• {t}" for t in recordar))
    if resueltos:
        mensajes.append("✅ Vigilante: resuelto\n" + "\n".join(f"• {t}" for t in resueltos))

    activos = {}
    for k, texto in actuales.items():
        antes = activos_previos.get(k)
        avisado = ahora.isoformat() if (antes is None or texto in recordar) else antes["avisado"]
        activos[k] = {"texto": texto, "avisado": avisado}
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    RUTA.write_text(json.dumps({"revisado": ahora.isoformat(timespec="minutes"), "activos": activos},
                               indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n\n".join(mensajes) if mensajes else "Todo en orden.")
    if mensajes and "--sin-telegram" not in sys.argv:
        for m in mensajes:
            telegram.send_message(m, silencioso=m.startswith("✅"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
