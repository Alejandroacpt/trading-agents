"""
MOTOR DE BACKTEST
-----------------
Simula día a día cómo habría evolucionado una cartera que sigue una
estrategia, con costes de operación incluidos.

La idea en una frase: la estrategia dice "qué porcentaje del capital
quiero en cada activo" (pesos objetivo) y el motor calcula cuánto se
habría ganado o perdido haciéndolo de verdad.

Reglas de la simulación (pensadas para NO engañarnos):
1. Retraso de ejecución: una señal calculada con el cierre del día t
   se ejecuta al cierre del día siguiente (t+1). Es lo que pasará en la
   realidad: el sistema corre de noche y operamos al día siguiente.
2. Costes: cada compra o venta paga un porcentaje (comisión + slippage)
   que depende de la clase de activo.
3. Deriva: entre rebalanceos los pesos se mueven solos con los precios
   (si un activo sube, pesa más). Solo se opera cuando la estrategia
   cambia su objetivo.
4. Liquidez: la parte del capital que no está invertida cobra el
   rendimiento de las letras del Tesoro (BIL), o 0 antes de 2007.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Coste por operación (un sentido: comprar O vender) en tanto por uno.
# 0.001 = 0,10 %. Incluye comisión aproximada + deslizamiento de precio.
COSTES_POR_CLASE = {
    "equity": 0.0010,
    "bonds": 0.0010,
    "commodities": 0.0010,
    "cash": 0.0005,
    "crypto": 0.0025,
    "forex": 0.0003,
}


@dataclass
class ResultadoBacktest:
    """Todo lo que devuelve una simulación."""

    rentabilidad: pd.Series          # rentabilidad diaria neta de la cartera
    liquidez: pd.Series              # rentabilidad diaria de la liquidez (para el Sharpe)
    pesos: pd.DataFrame              # pesos reales (con deriva) al cierre de cada día
    rotacion: pd.Series              # % de la cartera operado cada día
    costes: pd.Series                # coste pagado cada día (tanto por uno)
    operaciones: pd.DataFrame = field(default_factory=pd.DataFrame)  # una fila por operación cerrada

    @property
    def curva(self) -> pd.Series:
        """Valor de 1 € invertido al inicio."""
        return (1 + self.rentabilidad).cumprod()


def preparar_precios(precios: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Une los calendarios de todos los activos.

    Devuelve (precios_rellenos, cotiza) donde 'cotiza' indica qué días
    tuvo cotización real cada activo. Los días sin cotización se rellenan
    con el último precio (rentabilidad 0 ese día).
    """
    precios = precios.sort_index()
    cotiza = precios.notna()
    return precios.ffill(), cotiza


def run_backtest(
    precios: pd.DataFrame,
    objetivos: pd.DataFrame,
    clases: dict[str, str],
    rent_liquidez: pd.Series | None = None,
    retraso: int = 1,
    multiplicador_costes: float = 1.0,
    inicio: str | pd.Timestamp | None = None,
) -> ResultadoBacktest:
    """Ejecuta la simulación.

    precios   : cierres (columnas = activos), ya alineados en un calendario.
    objetivos : pesos objetivo decididos al cierre de cada día (mismas
                columnas). NaN = la estrategia aún no tiene opinión.
                Positivo = largo, negativo = corto. La suma de valores
                absolutos debe ser <= 1 (sin apalancamiento).
    clases    : {ticker: clase} para aplicar el coste correcto.
    rent_liquidez : rentabilidad diaria de la liquidez (índice = fechas).
    retraso   : días entre la señal y la ejecución (1 = al cierre siguiente).
    multiplicador_costes : 2.0 para el test de estrés de costes.
    inicio    : primer día de la simulación (antes se ignora).
    """
    precios, _ = preparar_precios(precios)
    activos = list(precios.columns)
    objetivos = objetivos.reindex(index=precios.index, columns=activos)

    # Retraso de ejecución: el objetivo del día t se ejecuta en t+retraso
    objetivos = objetivos.shift(retraso)

    rent_activos = precios.pct_change().fillna(0.0)
    if rent_liquidez is None:
        rent_liquidez = pd.Series(0.0, index=precios.index)
    rent_liquidez = rent_liquidez.reindex(precios.index).fillna(0.0)

    if inicio is not None:
        mascara = precios.index >= pd.Timestamp(inicio)
        precios, objetivos = precios[mascara], objetivos[mascara]
        rent_activos, rent_liquidez = rent_activos[mascara], rent_liquidez[mascara]

    coste_unitario = np.array([COSTES_POR_CLASE.get(clases.get(a, "equity"), 0.001) for a in activos])
    coste_unitario = coste_unitario * multiplicador_costes

    R = rent_activos.to_numpy()
    RL = rent_liquidez.to_numpy()
    T = objetivos.to_numpy()
    n_dias, n_act = R.shape

    pesos_fin = np.zeros((n_dias, n_act))   # pesos al cierre de cada día
    rent = np.zeros(n_dias)
    rotacion = np.zeros(n_dias)
    costes = np.zeros(n_dias)

    w = np.zeros(n_act)            # pesos actuales
    objetivo_previo = None

    for t in range(n_dias):
        # 1) Rentabilidad del día con los pesos que traíamos de ayer
        liquidez = 1.0 - w.sum()   # lo no invertido (los cortos generan liquidez)
        r_dia = float(w @ R[t] + liquidez * RL[t])
        valor = 1.0 + r_dia

        # 2) Deriva: los pesos se mueven con los precios
        if valor > 0:
            w = w * (1 + R[t]) / valor

        # 3) ¿La estrategia ha cambiado su objetivo? Entonces rebalanceamos al cierre
        objetivo = T[t]
        if not np.all(np.isnan(objetivo)):
            objetivo = np.nan_to_num(objetivo, nan=0.0)
            if objetivo_previo is None or not np.allclose(objetivo, objetivo_previo, atol=1e-9):
                operado = np.abs(objetivo - w)
                coste = float(operado @ coste_unitario)
                rotacion[t] = operado.sum()
                costes[t] = coste
                r_dia -= coste
                w = objetivo.copy()
                objetivo_previo = objetivo

        rent[t] = r_dia
        pesos_fin[t] = w

    idx = precios.index
    pesos_df = pd.DataFrame(pesos_fin, index=idx, columns=activos)
    resultado = ResultadoBacktest(
        rentabilidad=pd.Series(rent, index=idx, name="rentabilidad"),
        liquidez=pd.Series(RL, index=idx, name="liquidez"),
        pesos=pesos_df,
        rotacion=pd.Series(rotacion, index=idx, name="rotacion"),
        costes=pd.Series(costes, index=idx, name="costes"),
    )
    resultado.operaciones = extraer_operaciones(pesos_df, rent_activos)
    return resultado


def extraer_operaciones(pesos: pd.DataFrame, rent_activos: pd.DataFrame) -> pd.DataFrame:
    """Convierte la serie de pesos en una lista de operaciones.

    Una operación empieza cuando un activo pasa de 0 a tener posición
    (o cambia de largo a corto) y termina cuando vuelve a 0 o cambia de
    signo. Su resultado es la rentabilidad del activo durante ese tiempo
    (con el signo de la posición). Sirve para el % de aciertos.
    """
    filas = []
    for activo in pesos.columns:
        signo = np.sign(pesos[activo].round(8)).to_numpy()
        r = rent_activos[activo].reindex(pesos.index).fillna(0).to_numpy()
        inicio, lado = None, 0
        for t in range(len(signo)):
            # la posición tomada al cierre de t gana/pierde con la rentabilidad de t+1
            if lado != 0 and signo[t] != lado:
                tramo = r[inicio + 1 : t + 1]
                filas.append({
                    "activo": activo,
                    "entrada": pesos.index[inicio],
                    "salida": pesos.index[t],
                    "lado": "largo" if lado > 0 else "corto",
                    "resultado": float(np.prod(1 + lado * tramo) - 1),
                    "dias": t - inicio,
                })
                inicio, lado = None, 0
            if lado == 0 and signo[t] != 0:
                inicio, lado = t, signo[t]
    return pd.DataFrame(filas)
