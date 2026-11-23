"""
INFORME DE VALIDACIÓN
---------------------
Genera reports/validacion/informe.md y los gráficos de cada estrategia.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo guardar imágenes
import matplotlib.ticker  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest import metrics  # noqa: E402
from src.backtest.validator import INICIO_TEST, UMBRALES  # noqa: E402

ICONO = {"APROBADA": "✅", "OBSERVACIÓN": "🟡", "RECHAZADA": "❌"}
COLOR_ESTRATEGIA = "#2a6fdb"
COLOR_REFERENCIA = "#9aa0a6"


def _pct(x, dec=1):
    return "-" if x is None or pd.isna(x) else f"{x * 100:.{dec}f} %".replace(".", ",")


def _num(x, dec=2):
    return "-" if x is None or pd.isna(x) else f"{x:.{dec}f}".replace(".", ",")


def grafico(v: dict, carpeta: Path) -> Path:
    """Curva de capital (escala logarítmica) y drawdown frente a la referencia."""
    e = v["estrategia"]
    rent = v["resultado"].rentabilidad
    ref = v["rent_referencia"].reindex(rent.index).fillna(0)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1.3]})
    ax1.plot((1 + rent).cumprod(), color=COLOR_ESTRATEGIA, lw=1.6, label=e["nombre"])
    ax1.plot((1 + ref).cumprod(), color=COLOR_REFERENCIA, lw=1.2, label="Referencia: comprar y mantener el universo")
    ax1.set_yscale("log")
    ax1.yaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1, 1.5, 2, 3, 5, 7)))
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    ax1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax1.axvline(INICIO_TEST, color="#444", ls="--", lw=0.8)
    ax1.text(INICIO_TEST, ax1.get_ylim()[1], "  inicio test", va="top", fontsize=8, color="#444")
    ax1.axvline(pd.Timestamp(e["publicacion"]), color="#c77700", ls=":", lw=0.8)
    ax1.text(pd.Timestamp(e["publicacion"]), ax1.get_ylim()[0], "  publicación", va="bottom", fontsize=8, color="#c77700")
    ax1.set_ylabel("Valor de 1 € (escala log.)")
    ax1.legend(loc="upper left", fontsize=8, frameon=False)
    ax1.grid(alpha=0.25)
    ax1.set_title(f"{e['nombre']} · {v['veredicto']['decision']}", fontsize=11, loc="left")

    ax2.fill_between(rent.index, metrics.drawdown(rent) * 100, 0, color=COLOR_ESTRATEGIA, alpha=0.35, lw=0)
    ax2.plot(ref.index, metrics.drawdown(ref) * 100, color=COLOR_REFERENCIA, lw=0.9)
    ax2.set_ylabel("Caída desde\nmáximo (%)")
    ax2.grid(alpha=0.25)
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    ruta = carpeta / f"{e['id']}.png"
    fig.savefig(ruta, dpi=130)
    plt.close(fig)
    return ruta


def grafico_resumen(validaciones: list[dict], carpeta: Path) -> Path:
    """Sharpe de cada estrategia en el periodo completo y en el de test."""
    nombres = [v["estrategia"]["nombre"].split(" (")[0] for v in validaciones]
    completo = [v["periodos"]["completo"]["sharpe"] for v in validaciones]
    test = [v["periodos"]["test"]["sharpe"] for v in validaciones]

    fig, ax = plt.subplots(figsize=(9, 4))
    y = range(len(nombres))
    ax.barh([i + 0.2 for i in y], completo, height=0.38, color="#b3c7ee", label="Periodo completo")
    ax.barh([i - 0.2 for i in y], test, height=0.38, color=COLOR_ESTRATEGIA, label="Test (2018+)")
    ax.axvline(UMBRALES["sharpe_test"], color="#d33", ls="--", lw=1)
    ax.text(UMBRALES["sharpe_test"], len(nombres) - 0.4, f" umbral {UMBRALES['sharpe_test']}", color="#d33", fontsize=8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(nombres)
    ax.invert_yaxis()
    ax.set_xlabel("Sharpe neto de costes")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    ruta = carpeta / "resumen.png"
    fig.savefig(ruta, dpi=130)
    plt.close(fig)
    return ruta


def informe(validaciones: list[dict], carpeta: Path, fecha_datos) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    grafico_resumen(validaciones, carpeta)
    for v in validaciones:
        grafico(v, carpeta)

    n_pruebas = validaciones[0].get("n_pruebas", 0)
    L = [
        "# Validación de estrategias",
        "",
        f"*Datos hasta {fecha_datos}. Costes incluidos. Ejecución al cierre del día siguiente a la señal. "
        f"{n_pruebas} variantes probadas en total.*",
        "",
        "> Esto es investigación de un sistema, no asesoramiento financiero.",
        "",
        "## Resumen",
        "",
        "| Estrategia | Papel | Veredicto | Sharpe completo | Sharpe test 2018+ | CAGR | Peor caída | Referencia: peor caída |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in validaciones:
        e, p, vd = v["estrategia"], v["periodos"], v["veredicto"]
        L.append(
            f"| {e['nombre']} | {e['papel']} | {ICONO[vd['decision']]} {vd['decision']} | "
            f"{_num(p['completo']['sharpe'])} | {_num(p['test']['sharpe'])} | {_pct(p['completo']['cagr'])} | "
            f"{_pct(p['completo']['max_drawdown'], 0)} | {_pct(v['referencia']['completo']['max_drawdown'], 0)} |"
        )
    L += ["", "![Resumen](resumen.png)", ""]

    L += [
        "## Criterios de aprobación",
        "",
        f"- Sharpe neto en test (2018 en adelante) > {UMBRALES['sharpe_test']}",
        f"- Sharpe neto desde la publicación del paper > {UMBRALES['sharpe_post_publicacion']} (si hay 3+ años)",
        f"- Robustez: al menos {UMBRALES['fraccion_robusta']:.0%} de las variantes de parámetros con Sharpe > {UMBRALES['sharpe_robustez']}",
        f"- Walk-forward (elegir cada año el mejor parámetro con datos pasados): Sharpe > {UMBRALES['sharpe_walk_forward']}",
        f"- Con el doble de costes: Sharpe > {UMBRALES['sharpe_costes_x2']}",
        f"- Sharpe deflactado (probabilidad de que no sea suerte tras {n_pruebas} pruebas) > {UMBRALES['dsr']}",
        "- Peor caída dentro del límite de su papel",
        "",
        "Sin fallos → APROBADA. Uno o dos fallos no críticos → OBSERVACIÓN. Sharpe de test negativo, "
        "o fallo de robustez/test junto con otros → RECHAZADA.",
        "",
    ]

    for v in validaciones:
        e, p, vd = v["estrategia"], v["periodos"], v["veredicto"]
        L += [
            f"## {ICONO[vd['decision']]} {e['nombre']}: {vd['decision']}",
            "",
            f"**Referencia:** {e['referencia']}. **Parámetros:** "
            + ", ".join(f"{k} = {val}" for k, val in e["parametros"].items())
            + f". **Universo:** {', '.join(t for t in e['universo'] if t != 'BIL')}.",
            "",
            f"![{e['nombre']}]({e['id']}.png)",
            "",
            "| Periodo | Desde | Años | CAGR | Volatilidad | Sharpe | Peor caída | Operaciones/año | % aciertos | Exposición media |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        etiquetas = {"completo": "Completo", "desarrollo": "Desarrollo (< 2018)", "test": "Test (2018+)",
                     "post_publicacion": "Desde la publicación"}
        for k, etiqueta in etiquetas.items():
            m = p[k]
            if not m:
                continue
            L.append(
                f"| {etiqueta} | {m['desde']} | {_num(m['anios'], 1)} | {_pct(m['cagr'])} | {_pct(m['volatilidad'])} | "
                f"{_num(m['sharpe'])} | {_pct(m['max_drawdown'], 0)} | {_num(m.get('operaciones_anio'), 1)} | "
                f"{_pct(m.get('aciertos'), 0)} | {_pct(m.get('exposicion_media'), 0)} |"
            )
        ref = v["referencia"]
        L.append(
            f"| *Referencia (comprar y mantener)* | | | {_pct(ref['completo']['cagr'])} | {_pct(ref['completo']['volatilidad'])} | "
            f"{_num(ref['completo']['sharpe'])} | {_pct(ref['completo']['max_drawdown'], 0)} | | | 100 % |"
        )
        L += ["", "**Pruebas:**", "", "| Prueba | Resultado | Umbral | |", "|---|---|---|---|"]
        for nombre, d in vd["detalle"].items():
            es_frac = nombre.startswith("Robustez") or nombre.startswith("Sharpe deflactado")
            es_dd = nombre.startswith("Drawdown")
            val = _pct(d["valor"], 0) if (es_frac or es_dd) else _num(d["valor"])
            umb = _pct(d["umbral"], 0) if (es_frac or es_dd) else _num(d["umbral"])
            L.append(f"| {nombre} | {val} | {'≥' if not es_dd else 'mejor que'} {umb} | {'✅' if d['ok'] else '❌'} |")
        L += [
            "",
            "**Variantes de parámetros (Sharpe completo / test):** "
            + "; ".join(f"{k}: {_num(s)} / {_num(v['sharpes_test_rejilla'][k])}" for k, s in v["sharpes_rejilla"].items()),
            "",
        ]
        if e.get("nota_validacion"):
            L += [f"**Nota:** {e['nota_validacion']}", ""]

    ruta = carpeta / "informe.md"
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")
    return ruta
