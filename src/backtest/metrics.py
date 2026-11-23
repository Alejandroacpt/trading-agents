"""
MÉTRICAS DE RENDIMIENTO
-----------------------
Convierten una serie de rentabilidades diarias en los números que
usamos para juzgar una estrategia.

Glosario rápido:
- CAGR: rentabilidad anual compuesta ("cuánto crece al año de media").
- Volatilidad: cuánto oscila al año (desviación típica anualizada).
- Sharpe: rentabilidad por encima de la liquidez dividida entre la
  volatilidad. Por encima de 0,5 es bueno; por encima de 1, muy bueno.
- Drawdown máximo: la mayor caída desde un máximo hasta un mínimo.
- Sharpe deflactado (DSR): probabilidad de que el Sharpe real sea > 0,
  descontando la "suerte" de haber probado muchas variantes
  (Bailey y López de Prado, 2014).
"""

import numpy as np
import pandas as pd
from scipy import stats


def periodos_por_anio(rent: pd.Series) -> float:
    """Número de observaciones por año (252 en bolsa, 365 en cripto...)."""
    if len(rent) < 2:
        return 252.0
    anios = (rent.index[-1] - rent.index[0]).days / 365.25
    return len(rent) / anios if anios > 0 else 252.0


def sharpe(rent: pd.Series, liquidez: pd.Series | None = None) -> float:
    """Sharpe anualizado sobre la rentabilidad en exceso de la liquidez."""
    exceso = rent - (liquidez.reindex(rent.index).fillna(0) if liquidez is not None else 0)
    sd = exceso.std()
    if not sd or np.isnan(sd):
        return 0.0
    return float(exceso.mean() / sd * np.sqrt(periodos_por_anio(rent)))


def drawdown(rent: pd.Series) -> pd.Series:
    curva = (1 + rent).cumprod()
    return curva / curva.cummax() - 1


def maximo_dias_en_drawdown(rent: pd.Series) -> int:
    """Días naturales más largos pasados por debajo de un máximo anterior."""
    dd = drawdown(rent)
    en_dd = dd < -1e-9
    peor, inicio = 0, None
    for fecha, abajo in en_dd.items():
        if abajo and inicio is None:
            inicio = fecha
        elif not abajo and inicio is not None:
            peor = max(peor, (fecha - inicio).days)
            inicio = None
    if inicio is not None:
        peor = max(peor, (en_dd.index[-1] - inicio).days)
    return peor


def resumen(
    rent: pd.Series,
    liquidez: pd.Series | None = None,
    pesos: pd.DataFrame | None = None,
    rotacion: pd.Series | None = None,
    operaciones: pd.DataFrame | None = None,
) -> dict:
    """Tabla de métricas de un periodo."""
    rent = rent.dropna()
    if len(rent) < 20:
        return {}
    anios = (rent.index[-1] - rent.index[0]).days / 365.25
    ppa = periodos_por_anio(rent)
    total = float((1 + rent).prod())
    m = {
        "desde": rent.index[0].date(),
        "hasta": rent.index[-1].date(),
        "anios": round(anios, 1),
        "cagr": total ** (1 / anios) - 1 if anios > 0 else np.nan,
        "volatilidad": float(rent.std() * np.sqrt(ppa)),
        "sharpe": sharpe(rent, liquidez),
        "max_drawdown": float(drawdown(rent).min()),
        "dias_max_drawdown": maximo_dias_en_drawdown(rent),
    }
    if pesos is not None:
        p = pesos.reindex(rent.index)
        m["exposicion_media"] = float(p.abs().sum(axis=1).mean())
    if rotacion is not None:
        m["rotacion_anual"] = float(rotacion.reindex(rent.index).sum() / anios) if anios > 0 else np.nan
    if operaciones is not None and len(operaciones):
        ops = operaciones[(operaciones["salida"] >= rent.index[0]) & (operaciones["salida"] <= rent.index[-1])]
        m["operaciones"] = int(len(ops))
        m["operaciones_anio"] = len(ops) / anios if anios > 0 else np.nan
        m["aciertos"] = float((ops["resultado"] > 0).mean()) if len(ops) else np.nan
        m["dias_medios"] = float(ops["dias"].mean()) if len(ops) else np.nan
    return m


# ----------------------------------------------------------------------
# Sharpe probabilístico y deflactado (Bailey y López de Prado, 2014)
# ----------------------------------------------------------------------

def sharpe_probabilistico(rent: pd.Series, sr_referencia: float = 0.0, liquidez=None) -> float:
    """Probabilidad de que el Sharpe real supere 'sr_referencia'.

    Trabaja con Sharpe por periodo (diario), corrigiendo por asimetría y
    colas gruesas de las rentabilidades.
    """
    exceso = (rent - (liquidez.reindex(rent.index).fillna(0) if liquidez is not None else 0)).dropna()
    n = len(exceso)
    if n < 30 or exceso.std() == 0:
        return np.nan
    sr = exceso.mean() / exceso.std()
    asim = stats.skew(exceso)
    curt = stats.kurtosis(exceso, fisher=False)  # curtosis normal = 3
    denom = np.sqrt(max(1 - asim * sr + (curt - 1) / 4 * sr**2, 1e-12))
    return float(stats.norm.cdf((sr - sr_referencia) * np.sqrt(n - 1) / denom))


def sharpe_maximo_esperado(sharpes_diarios: list[float]) -> float:
    """Sharpe (diario) que cabría esperar como el MEJOR de N pruebas
    aunque ninguna tuviera ventaja real. Es el liston que hay que superar."""
    n = len(sharpes_diarios)
    if n < 2:
        return 0.0
    var = np.var(sharpes_diarios, ddof=1)
    gamma = 0.5772156649  # constante de Euler-Mascheroni
    z1 = stats.norm.ppf(1 - 1 / n)
    z2 = stats.norm.ppf(1 - 1 / (n * np.e))
    return float(np.sqrt(var) * ((1 - gamma) * z1 + gamma * z2))


def sharpe_maximo_por_suerte(n_pruebas: int, n_observaciones: int) -> float:
    """Sharpe (por periodo) que obtendría POR PURA SUERTE la mejor de
    'n_pruebas' estrategias sin ninguna ventaja real, con 'n_observaciones'
    días de datos. Bajo la hipótesis nula, el error del Sharpe estimado es
    ~1/sqrt(n_observaciones), y el máximo de N pruebas se aleja del cero
    según la fórmula de Bailey y López de Prado."""
    if n_pruebas < 2 or n_observaciones < 3:
        return 0.0
    gamma = 0.5772156649
    z1 = stats.norm.ppf(1 - 1 / n_pruebas)
    z2 = stats.norm.ppf(1 - 1 / (n_pruebas * np.e))
    return float(np.sqrt(1 / (n_observaciones - 1)) * ((1 - gamma) * z1 + gamma * z2))


def sharpe_deflactado(rent: pd.Series, sharpes_diarios_pruebas: list[float], liquidez=None) -> float:
    """DSR: probabilidad de que el Sharpe real sea > 0 teniendo en cuenta
    todas las variantes probadas. Por encima de 0,95 es convincente."""
    liston = sharpe_maximo_esperado(sharpes_diarios_pruebas)
    return sharpe_probabilistico(rent, liston, liquidez)


def sharpe_diario(rent: pd.Series, liquidez=None) -> float:
    exceso = (rent - (liquidez.reindex(rent.index).fillna(0) if liquidez is not None else 0)).dropna()
    return float(exceso.mean() / exceso.std()) if exceso.std() else 0.0
