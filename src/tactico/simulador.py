"""
SIMULADOR TÁCTICO (operaciones con stop)
----------------------------------------
Simula, vela a vela, una cartera que abre y cierra operaciones con stop.
Es la versión de corto plazo del motor de backtest.

Reglas (las mismas que se aplicarán en vivo):
1. La señal se calcula al CIERRE de una vela y la orden se ejecuta en la
   APERTURA de la siguiente (nunca se opera con información del futuro).
2. Toda operación lleva stop desde el primer momento. Si el mínimo de una
   vela toca el stop, se sale al precio del stop (o a la apertura, si el
   precio abrió ya por debajo: el hueco se paga entero).
3. Tamaño por riesgo: si salta el stop se pierde el % fijado del capital
   (1,5 %), con un tope de peso por posición y de número de posiciones.
4. Costes en cada compra y venta (comisión + horquilla).
5. Stop dinámico opcional (sube con el precio, nunca baja).
6. Salida por tiempo opcional (máximo de velas en la operación).
7. Regla PDT opcional (acciones): no se cierra el mismo día de la entrada.

Solo largos en esta versión.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest.engine import ResultadoBacktest


@dataclass
class Parametros:
    riesgo: float = 0.015
    max_posiciones: int = 5
    max_peso: float = 0.25
    coste: float = 0.0025
    sin_intradia: bool = False


def simular(ohlc: dict[str, pd.DataFrame], senales: dict[str, pd.DataFrame], p: Parametros,
            calentamiento: int = 0) -> ResultadoBacktest:
    """
    ohlc    : {activo: DataFrame con open, high, low, close}
    senales : {activo: DataFrame con columnas
                 entrada (bool)  -> abrir al cierre de esta vela (se ejecuta en la siguiente)
                 salida  (bool)  -> cerrar al cierre de esta vela
                 stop    (float) -> distancia del stop inicial en precio
                 dinamico(float, opcional) -> distancia del stop dinámico (NaN = sin él)
                 max_velas (float, opcional) -> salida por tiempo (NaN = sin límite)}
    calentamiento : velas iniciales que no cuentan en el resultado (indicadores aún sin datos).
    """
    activos = [a for a in ohlc if a in senales and not ohlc[a].empty]
    indice = pd.DatetimeIndex(sorted(set().union(*[ohlc[a].index for a in activos])))
    T, N = len(indice), len(activos)

    def matriz(fuente, col, relleno=np.nan):
        return np.column_stack([fuente[a].reindex(indice)[col].to_numpy(dtype=float)
                                if col in fuente[a] else np.full(T, relleno) for a in activos])

    O, H, L, C = (matriz(ohlc, c) for c in ("open", "high", "low", "close"))
    E = np.nan_to_num(matriz(senales, "entrada", 0.0)).astype(bool)
    X = np.nan_to_num(matriz(senales, "salida", 0.0)).astype(bool)
    SD = matriz(senales, "stop")
    TR = matriz(senales, "dinamico")
    MV = matriz(senales, "max_velas")
    fechas = indice.normalize()

    caja = 1.0
    qty = np.zeros(N)
    precio_entrada = np.zeros(N)
    stop = np.zeros(N)
    t_entrada = np.full(N, -1)
    dist_pendiente = np.full(N, np.nan)
    entrada_pendiente = np.zeros(N, dtype=bool)
    salida_pendiente = np.zeros(N, dtype=bool)
    ultimo_cierre = np.full(N, np.nan)

    equity = np.zeros(T)
    pesos = np.zeros((T, N))
    rotacion = np.zeros(T)
    costes = np.zeros(T)
    operaciones = []
    equity_prev = 1.0

    def cerrar(i, t, precio, motivo):
        nonlocal caja
        valor = qty[i] * precio
        coste = valor * p.coste
        caja += valor - coste
        rotacion[t] += valor
        costes[t] += coste
        operaciones.append({
            "activo": activos[i], "entrada": indice[t_entrada[i]], "salida": indice[t], "lado": "largo",
            "resultado": float((precio * (1 - p.coste)) / (precio_entrada[i] * (1 + p.coste)) - 1),
            "dias": float((indice[t] - indice[t_entrada[i]]).total_seconds() / 86400), "motivo": motivo,
        })
        qty[i] = 0.0
        t_entrada[i] = -1

    for t in range(T):
        hay = ~np.isnan(O[t])
        # 1) Órdenes pendientes de la vela anterior, a la apertura de esta
        for i in np.where(salida_pendiente & hay & (qty > 0))[0]:
            if p.sin_intradia and fechas[t] == fechas[t_entrada[i]]:
                continue  # regla PDT: se cierra en la siguiente sesión
            cerrar(i, t, O[t, i], "señal")
            salida_pendiente[i] = False
        for i in np.where(entrada_pendiente & hay & (qty == 0))[0]:
            entrada_pendiente[i] = False
            d = dist_pendiente[i]
            if not (d > 0) or (qty > 0).sum() >= p.max_posiciones:
                continue
            precio = O[t, i]
            valor = min(p.riesgo * equity_prev / d * precio, p.max_peso * equity_prev, caja / (1 + p.coste))
            if valor <= 1e-4 * equity_prev:
                continue
            qty[i] = valor / precio
            caja -= valor * (1 + p.coste)
            rotacion[t] += valor
            costes[t] += valor * p.coste
            precio_entrada[i] = precio
            stop[i] = precio - d
            t_entrada[i] = t
        entrada_pendiente[:] = False

        # 2) Stops dentro de la vela
        for i in np.where((qty > 0) & ~np.isnan(L[t]))[0]:
            if p.sin_intradia and fechas[t] == fechas[t_entrada[i]]:
                continue
            if L[t, i] <= stop[i]:
                cerrar(i, t, min(O[t, i], stop[i]), "stop")
                salida_pendiente[i] = False

        # 3) Valoración al cierre, stop dinámico y salida por tiempo
        ultimo_cierre = np.where(np.isnan(C[t]), ultimo_cierre, C[t])
        valor_pos = qty * np.nan_to_num(ultimo_cierre)
        equity[t] = caja + valor_pos.sum()
        for i in np.where(qty > 0)[0]:
            if not np.isnan(TR[t, i]) and not np.isnan(C[t, i]):
                stop[i] = max(stop[i], C[t, i] - TR[t, i])
            if not np.isnan(MV[t, i]) and t - t_entrada[i] >= MV[t, i]:
                salida_pendiente[i] = True

        # 4) Señales al cierre de esta vela (se ejecutan en la siguiente)
        for i in range(N):
            if np.isnan(C[t, i]):
                continue
            if qty[i] > 0 and X[t, i]:
                salida_pendiente[i] = True
            elif qty[i] == 0 and E[t, i] and not np.isnan(SD[t, i]):
                entrada_pendiente[i] = True
                dist_pendiente[i] = SD[t, i]

        pesos[t] = valor_pos / equity[t] if equity[t] > 0 else 0
        rotacion[t] /= max(equity_prev, 1e-12)
        costes[t] /= max(equity_prev, 1e-12)
        equity_prev = equity[t]

    # Foto final para el escáner en vivo: posiciones abiertas y órdenes para la próxima vela
    abiertas = [{"activo": activos[i], "entrada": indice[t_entrada[i]], "precio_entrada": float(precio_entrada[i]),
                 "stop": float(stop[i]), "peso": float(pesos[T - 1, i]) if T else 0.0,
                 "cierre": float(ultimo_cierre[i])} for i in np.where(qty > 0)[0]]
    pendientes = ([{"activo": activos[i], "accion": "comprar", "distancia_stop": float(dist_pendiente[i])}
                   for i in np.where(entrada_pendiente)[0]]
                  + [{"activo": activos[i], "accion": "vender"} for i in np.where(salida_pendiente & (qty > 0))[0]])

    eq = pd.Series(equity, index=indice)
    rent = eq.pct_change().fillna(eq.iloc[0] - 1 if T else 0.0)
    corte = indice[min(calentamiento, T - 1)] if T else None
    sel = indice >= corte if T else slice(None)
    ops = pd.DataFrame(operaciones)
    if len(ops):
        ops = ops[ops["entrada"] >= corte]
    res = ResultadoBacktest(
        rentabilidad=rent[sel],
        liquidez=pd.Series(0.0, index=indice[sel]),
        pesos=pd.DataFrame(pesos, index=indice, columns=activos)[sel],
        rotacion=pd.Series(rotacion, index=indice)[sel],
        costes=pd.Series(costes, index=indice)[sel],
        operaciones=ops,
    )
    res.abiertas = abiertas
    res.pendientes = pendientes
    res.equity = eq
    return res
