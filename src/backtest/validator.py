"""
VALIDADOR DE ESTRATEGIAS
------------------------
Decide si una estrategia entra en el sistema. Ninguna estrategia opera
(ni siquiera en paper) sin pasar por aquí.

Pruebas que hace a cada estrategia:
1. Backtest completo con costes, con los parámetros del paper.
2. Periodo de TEST (2018 en adelante): datos que tratamos como "no
   vistos". Los parámetros vienen del paper, no los hemos ajustado.
3. Periodo POST-PUBLICACIÓN: ¿sigue funcionando desde que se publicó?
   (McLean y Pontiff, 2016: de media, las anomalías pierden ~58 %
   de su rentabilidad tras publicarse.)
4. ROBUSTEZ: ¿funciona también con parámetros vecinos? Si solo
   funciona con un valor concreto, es casualidad.
5. WALK-FORWARD: cada año se elige el mejor parámetro con los datos
   pasados y se aplica al año siguiente. Simula decidir sin conocer
   el futuro.
6. ESTRÉS DE COSTES: ¿aguanta con el doble de costes?
7. SHARPE DEFLACTADO: ¿es significativo después de haber probado
   ~30 variantes en total?
8. DRAWDOWN: ¿la peor caída es aceptable para su papel?
"""

import numpy as np
import pandas as pd

from src.backtest import metrics
from src.backtest.engine import run_backtest

INICIO_TEST = pd.Timestamp("2018-01-01")

# Umbrales de aprobación (documento de arquitectura, sección 4)
UMBRALES = {
    "sharpe_test": 0.4,
    "sharpe_post_publicacion": 0.3,
    "sharpe_robustez": 0.3,       # Sharpe mínimo de cada variante de la rejilla
    "fraccion_robusta": 2 / 3,    # % de variantes que deben superarlo
    "sharpe_costes_x2": 0.3,
    "sharpe_walk_forward": 0.3,
    "dsr": 0.90,
}


def rent_liquidez(precios_todos: pd.DataFrame, indice: pd.DatetimeIndex) -> pd.Series:
    """Rentabilidad diaria de la liquidez (BIL), 0 antes de que exista."""
    if "BIL" not in precios_todos:
        return pd.Series(0.0, index=indice)
    bil = precios_todos["BIL"].dropna().pct_change()
    return bil.reindex(indice).fillna(0.0)


def recortar(serie, desde=None, hasta=None):
    if desde is not None:
        serie = serie[serie.index >= pd.Timestamp(desde)]
    if hasta is not None:
        serie = serie[serie.index < pd.Timestamp(hasta)]
    return serie


def preparar_universo(estrategia: dict, precios_todos: pd.DataFrame) -> pd.DataFrame:
    universo = [t for t in estrategia["universo"] if t in precios_todos.columns]
    return precios_todos[universo].dropna(how="all")


def ejecutar(estrategia, precios, clases, liquidez, params, inicio=None, mult_costes=1.0):
    objetivos = estrategia["senales"](precios, **params)
    return run_backtest(precios, objetivos, clases, liquidez, retraso=1,
                        multiplicador_costes=mult_costes, inicio=inicio), objetivos


def referencia_comprar_y_mantener(precios, clases, liquidez, inicio) -> pd.Series:
    """Benchmark: repartir a partes iguales entre los activos del universo
    (sin BIL) y rebalancear cada mes. Sirve para comparar."""
    from src.strategies.indicadores import fines_de_mes

    activos = [a for a in precios.columns if a != "BIL"]
    fm = fines_de_mes(precios.index)
    disponibles = precios[activos].ffill().notna()
    objetivos = disponibles.loc[fm].astype(float)
    objetivos = objetivos.div(objetivos.sum(axis=1).replace(0, np.nan), axis=0)
    objetivos = objetivos.reindex(precios.index).reindex(columns=precios.columns)
    return run_backtest(precios, objetivos, clases, liquidez, inicio=inicio).rentabilidad


def walk_forward(rents: dict, liquidez: pd.Series, anios_minimos: int = 3) -> tuple[pd.Series, list]:
    """Cada año natural elige la variante con mejor Sharpe en TODO el
    pasado disponible y usa su rentabilidad ese año."""
    claves = list(rents)
    indice = rents[claves[0]].index
    primer_anio = indice[0].year + anios_minimos
    trozos, elecciones = [], []
    for anio in range(primer_anio, indice[-1].year + 1):
        corte = pd.Timestamp(f"{anio}-01-01")
        mejor = max(claves, key=lambda k: metrics.sharpe(recortar(rents[k], hasta=corte), liquidez))
        trozo = recortar(rents[mejor], desde=corte, hasta=pd.Timestamp(f"{anio + 1}-01-01"))
        trozos.append(trozo)
        elecciones.append((anio, mejor))
    if not trozos:
        return pd.Series(dtype=float), []
    return pd.concat(trozos), elecciones


def validar(estrategia: dict, precios_todos: pd.DataFrame, clases: dict) -> dict:
    """Ejecuta todas las pruebas de una estrategia (salvo el DSR, que
    necesita conocer las pruebas de todas las estrategias)."""
    precios = preparar_universo(estrategia, precios_todos)
    liquidez = rent_liquidez(precios_todos, precios.index)

    # 1) Todas las variantes de la rejilla, para fijar un inicio común
    objetivos_rejilla = {}
    for params in estrategia["rejilla"]:
        objetivos_rejilla[_clave(params)] = estrategia["senales"](precios, **params)
    # Inicio: primer día en que la estrategia tiene opinión sobre al menos
    # 'min_activos' activos (para no evaluar una "cartera" de un solo activo)
    minimo = estrategia.get("min_activos", 1)
    inicio = max(
        o.index[o.notna().sum(axis=1) >= minimo][0] for o in objetivos_rejilla.values()
    )

    # 2) Backtest de cada variante desde ese inicio
    resultados = {}
    for params in estrategia["rejilla"]:
        k = _clave(params)
        resultados[k] = run_backtest(precios, objetivos_rejilla[k], clases, liquidez, inicio=inicio)

    clave_defecto = _clave(estrategia["parametros"])
    if clave_defecto not in resultados:
        objetivos = estrategia["senales"](precios, **estrategia["parametros"])
        resultados[clave_defecto] = run_backtest(precios, objetivos, clases, liquidez, inicio=inicio)
    base = resultados[clave_defecto]
    rent = base.rentabilidad
    liq = base.liquidez

    def tabla(desde=None, hasta=None):
        r = recortar(rent, desde, hasta)
        return metrics.resumen(r, liq, base.pesos, base.rotacion, base.operaciones)

    periodos = {
        "completo": tabla(),
        "desarrollo": tabla(hasta=INICIO_TEST),
        "test": tabla(desde=INICIO_TEST),
        "post_publicacion": tabla(desde=estrategia["publicacion"]),
    }

    # 3) Robustez
    sharpes_rejilla = {k: metrics.sharpe(r.rentabilidad, r.liquidez) for k, r in resultados.items()}
    sharpes_test_rejilla = {k: metrics.sharpe(recortar(r.rentabilidad, INICIO_TEST), r.liquidez)
                            for k, r in resultados.items()}

    # 4) Walk-forward
    rent_wf, elecciones = walk_forward({k: r.rentabilidad for k, r in resultados.items()}, liq)
    wf = metrics.resumen(rent_wf, liq) if len(rent_wf) else {}

    # 5) Costes x2
    obj_def = estrategia["senales"](precios, **estrategia["parametros"])
    caro = run_backtest(precios, obj_def, clases, liquidez, inicio=inicio, multiplicador_costes=2.0)

    # 6) Referencia
    bench = referencia_comprar_y_mantener(precios, clases, liquidez, inicio)

    return {
        "estrategia": estrategia,
        "inicio": inicio,
        "resultado": base,
        "periodos": periodos,
        "sharpes_rejilla": sharpes_rejilla,
        "sharpes_test_rejilla": sharpes_test_rejilla,
        "walk_forward": wf,
        "elecciones_wf": elecciones,
        "sharpe_costes_x2": metrics.sharpe(caro.rentabilidad, caro.liquidez),
        "referencia": {
            "completo": metrics.resumen(bench, liq),
            "test": metrics.resumen(recortar(bench, INICIO_TEST), liq),
        },
        "rent_referencia": bench,
        "ppa": metrics.periodos_por_anio(rent),
    }


def anadir_dsr(validaciones: list[dict], n_minimo: int = 0) -> None:
    """Calcula el Sharpe deflactado de cada estrategia teniendo en cuenta
    TODAS las variantes probadas en TODAS las estrategias.

    El listón es el Sharpe que alcanzaría por suerte la mejor de N
    estrategias sin ventaja real, dado el número de días de datos.
    (No usamos la dispersión entre variantes: mezclar cripto con el resto
    la inflaría y castigaría a todas por igual.)
    """
    # N = las pruebas de esta tanda o el total histórico del registro, lo que sea mayor
    n_pruebas = max(sum(len(v["sharpes_rejilla"]) for v in validaciones), n_minimo)
    for v in validaciones:
        r = v["resultado"]
        sr0_diario = metrics.sharpe_maximo_por_suerte(n_pruebas, len(r.rentabilidad))
        v["n_pruebas"] = n_pruebas
        v["sharpe_suerte_anual"] = sr0_diario * np.sqrt(v["ppa"])
        v["dsr"] = metrics.sharpe_probabilistico(r.rentabilidad, sr0_diario, r.liquidez)
        v["psr"] = metrics.sharpe_probabilistico(r.rentabilidad, 0.0, r.liquidez)


def veredicto(v: dict) -> dict:
    """Aplica los umbrales y devuelve APROBADA / OBSERVACIÓN / RECHAZADA."""
    e = v["estrategia"]
    p = v["periodos"]
    pruebas = {}

    pruebas["Sharpe en test (2018+)"] = (p["test"].get("sharpe", 0), UMBRALES["sharpe_test"])

    pp = p["post_publicacion"]
    if pp and pp.get("anios", 0) >= 3:
        pruebas["Sharpe post-publicación"] = (pp["sharpe"], UMBRALES["sharpe_post_publicacion"])

    rejilla = list(v["sharpes_rejilla"].values())
    fraccion = np.mean([s > UMBRALES["sharpe_robustez"] for s in rejilla])
    pruebas["Robustez de parámetros"] = (fraccion, UMBRALES["fraccion_robusta"])

    if v["walk_forward"]:
        pruebas["Sharpe walk-forward"] = (v["walk_forward"]["sharpe"], UMBRALES["sharpe_walk_forward"])

    pruebas["Sharpe con costes x2"] = (v["sharpe_costes_x2"], UMBRALES["sharpe_costes_x2"])
    pruebas["Sharpe deflactado (DSR)"] = (v.get("dsr", np.nan), UMBRALES["dsr"])
    pruebas["Drawdown máximo"] = (p["completo"]["max_drawdown"], -e["max_drawdown_aceptable"])

    detalle = {nombre: {"valor": val, "umbral": umb, "ok": bool(val >= umb) if not np.isnan(val) else False}
               for nombre, (val, umb) in pruebas.items()}
    fallos = [n for n, d in detalle.items() if not d["ok"]]

    criticos = {"Sharpe en test (2018+)", "Robustez de parámetros"}
    if p["test"].get("sharpe", 0) <= 0 or (criticos & set(fallos) and len(fallos) >= 2):
        decision = "RECHAZADA"
    elif not fallos:
        decision = "APROBADA"
    elif len(fallos) <= 2:
        decision = "OBSERVACIÓN"
    else:
        decision = "RECHAZADA"

    return {"decision": decision, "detalle": detalle, "fallos": fallos}


def _clave(params: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in params.items())
