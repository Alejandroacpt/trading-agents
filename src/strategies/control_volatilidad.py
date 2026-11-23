"""
CONTROL DE VOLATILIDAD
----------------------
Referencia: Moreira y Muir (2017), "Volatility-Managed Portfolios",
Journal of Finance.

Idea: cuando un activo se vuelve muy nervioso (sube su volatilidad),
suele ser mal momento para estar muy expuesto: las caídas grandes
llegan en racha. Reducir la exposición en esos periodos mejora la
relación rentabilidad/riesgo y recorta las peores caídas.

Cómo lo aplicamos (capa que se pone ENCIMA de cualquier estrategia):
  peso_final = peso_de_la_estrategia × mín(1, vol_objetivo / vol_actual)
  - vol_actual: volatilidad del último mes aprox. (media exponencial).
  - Solo reduce, nunca apalanca (el factor no pasa de 1).
  - Se recalcula una vez por semana (o cuando la estrategia cambia de
    opinión), para no operar cada día por pequeños cambios.

Diferencia con el paper: Moreira y Muir escalan la cartera entera y
permiten apalancamiento; aquí escalamos cada activo y solo a la baja,
que es lo que se puede ejecutar con poco capital.
"""

import pandas as pd

from src.strategies.indicadores import volatilidad_anual


def aplicar(objetivos: pd.DataFrame, precios: pd.DataFrame, vol_objetivo: float,
            centro_masa: int = 20) -> pd.DataFrame:
    base = objetivos.ffill()                     # objetivo vigente cada día
    vol = volatilidad_anual(precios, centro_masa).reindex(columns=base.columns)
    factor = (vol_objetivo / vol).clip(upper=1.0).fillna(1.0)
    escalado = base * factor

    # Días de recálculo: cuando cambia la estrategia o al cierre de cada semana
    cambia = (base.fillna(0).diff().abs().sum(axis=1) > 1e-12)
    semanas = base.index.to_series().groupby(base.index.to_period("W")).max()
    fin_semana = base.index.isin(semanas.values)
    recalcular = cambia | fin_semana

    salida = escalado.where(pd.Series(recalcular, index=base.index), axis=0)
    return salida.where(base.notna().any(axis=1), axis=0)


def con_control(estrategia_base: dict, id_: str, nombre: str, vol_defecto: float,
                vols: tuple, rejilla_base: list, max_dd: float, nota: str = "") -> dict:
    """Crea una estrategia nueva = estrategia base + control de volatilidad."""

    def senales(precios, vol_objetivo=vol_defecto, **params_base):
        obj = estrategia_base["senales"](precios, **params_base)
        return aplicar(obj, precios, vol_objetivo)

    return {
        **estrategia_base,
        "id": id_,
        "nombre": nombre,
        "referencia": estrategia_base["referencia"] + " + Moreira y Muir (2017), Volatility-Managed Portfolios, JF",
        "senales": senales,
        "parametros": {**estrategia_base["parametros"], "vol_objetivo": vol_defecto},
        "rejilla": [{**p, "vol_objetivo": v} for p in rejilla_base for v in vols],
        "max_drawdown_aceptable": max_dd,
        "nota_validacion": nota,
    }
