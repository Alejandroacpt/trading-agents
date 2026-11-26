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
8. Orden limitada opcional en la entrada (columna "limite"): solo se
   ejecuta si el precio llega al límite en la vela siguiente (si no, se
   cancela) y paga la comisión de órdenes limitadas.
9. Cortos opcionales (columna "corto" = True en la vela de entrada): la
   operación gana si el precio baja. Todo se refleja: el stop va por
   encima de la entrada (salta si el MÁXIMO lo toca), el stop dinámico
   baja con el precio y nunca sube, y la orden limitada vende si el precio
   SUBE hasta el límite. Paga además una financiación anual sobre el valor
   de la posición (préstamo del activo / tasa de los perpetuos), cobrada
   vela a vela.
   SOLO INVESTIGACIÓN: Alpaca no permite cortos en cripto ni con fracciones,
   así que la ejecución en vivo no sabe operar cortos (se haría con ETFs
   inversos o en otro bróker).
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
    coste_limitada: float | None = None   # comisión de las órdenes limitadas (None = la misma)
    financiacion_corto: float = 0.0       # coste anual de mantener un corto (fracción del valor)


def simular(ohlc: dict[str, pd.DataFrame], senales: dict[str, pd.DataFrame], p: Parametros,
            calentamiento: int = 0) -> ResultadoBacktest:
    """
    ohlc    : {activo: DataFrame con open, high, low, close}
    senales : {activo: DataFrame con columnas
                 entrada (bool)  -> abrir al cierre de esta vela (se ejecuta en la siguiente)
                 salida  (bool)  -> cerrar al cierre de esta vela
                 stop    (float) -> distancia del stop inicial en precio
                 dinamico(float, opcional) -> distancia del stop dinámico (NaN = sin él)
                 max_velas (float, opcional) -> salida por tiempo (NaN = sin límite)
                 limite (float, opcional)    -> precio límite de la entrada (NaN = a mercado)
                 corto (bool, opcional)      -> la entrada de esta vela es en corto}
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
    LIM = matriz(senales, "limite")
    CO = np.nan_to_num(matriz(senales, "corto", 0.0)).astype(bool)
    fechas = indice.normalize()

    caja = 1.0
    qty = np.zeros(N)
    lado = np.ones(N)                 # +1 largo, -1 corto
    corto_pendiente = np.zeros(N, dtype=bool)
    precio_entrada = np.zeros(N)
    stop = np.zeros(N)
    t_entrada = np.full(N, -1)
    dist_pendiente = np.full(N, np.nan)
    limite_pendiente = np.full(N, np.nan)
    entrada_pendiente = np.zeros(N, dtype=bool)
    salida_pendiente = np.zeros(N, dtype=bool)
    ultimo_cierre = np.full(N, np.nan)

    equity = np.zeros(T)
    pesos = np.zeros((T, N))
    rotacion = np.zeros(T)
    costes = np.zeros(T)
    operaciones = []
    equity_prev = 1.0

    def valor_posicion(i, precio):
        # Largo: cantidad × precio. Corto: lo que se puso de garantía más (o menos) lo ganado al bajar.
        return qty[i] * precio if lado[i] > 0 else qty[i] * (2 * precio_entrada[i] - precio)

    def cerrar(i, t, precio, motivo):
        nonlocal caja
        valor = valor_posicion(i, precio)
        coste = qty[i] * precio * p.coste
        caja += valor - coste
        rotacion[t] += qty[i] * precio
        costes[t] += coste
        if lado[i] > 0:
            resultado = (precio * (1 - p.coste)) / (precio_entrada[i] * (1 + p.coste)) - 1
        else:
            resultado = (precio_entrada[i] * (1 - p.coste) - precio * (1 + p.coste)) / precio_entrada[i]
        operaciones.append({
            "activo": activos[i], "entrada": indice[t_entrada[i]], "salida": indice[t],
            "lado": "largo" if lado[i] > 0 else "corto",
            "resultado": float(resultado),
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
            coste_e = p.coste
            precio = O[t, i]
            lim = limite_pendiente[i]
            s = -1.0 if corto_pendiente[i] else 1.0
            if not np.isnan(lim):
                if s * O[t, i] <= s * lim:
                    precio = O[t, i]          # abrió mejor que el límite: se ejecuta a la apertura
                elif (s > 0 and L[t, i] <= lim) or (s < 0 and H[t, i] >= lim):
                    precio = lim              # el precio llegó al límite durante la vela
                else:
                    continue                  # no llegó: la orden se cancela
                coste_e = p.coste if p.coste_limitada is None else p.coste_limitada
            valor = min(p.riesgo * equity_prev / d * precio, p.max_peso * equity_prev, caja / (1 + coste_e))
            if valor <= 1e-4 * equity_prev:
                continue
            qty[i] = valor / precio
            caja -= valor * (1 + coste_e)
            rotacion[t] += valor
            costes[t] += valor * coste_e
            precio_entrada[i] = precio
            lado[i] = s
            stop[i] = precio - s * d
            t_entrada[i] = t
        entrada_pendiente[:] = False

        # 2) Stops dentro de la vela
        for i in np.where((qty > 0) & ~np.isnan(L[t]))[0]:
            if p.sin_intradia and fechas[t] == fechas[t_entrada[i]]:
                continue
            if lado[i] > 0 and L[t, i] <= stop[i]:
                cerrar(i, t, min(O[t, i], stop[i]), "stop")
                salida_pendiente[i] = False
            elif lado[i] < 0 and H[t, i] >= stop[i]:
                cerrar(i, t, max(O[t, i], stop[i]), "stop")
                salida_pendiente[i] = False

        # Financiación de los cortos: proporcional al tiempo desde la vela anterior
        if p.financiacion_corto and t > 0:
            anios = (indice[t] - indice[t - 1]).total_seconds() / (365 * 86400)
            for i in np.where((qty > 0) & (lado < 0) & (t_entrada < t))[0]:   # no la vela en que se abre
                coste_f = qty[i] * np.nan_to_num(ultimo_cierre[i], nan=precio_entrada[i]) * p.financiacion_corto * anios
                caja -= coste_f
                costes[t] += coste_f

        # 3) Valoración al cierre, stop dinámico y salida por tiempo
        ultimo_cierre = np.where(np.isnan(C[t]), ultimo_cierre, C[t])
        cierre_ok = np.nan_to_num(ultimo_cierre)
        valor_pos = np.where(lado > 0, qty * cierre_ok, qty * (2 * precio_entrada - cierre_ok))
        valor_pos = np.where(qty > 0, valor_pos, 0.0)
        equity[t] = caja + valor_pos.sum()
        for i in np.where(qty > 0)[0]:
            if not np.isnan(TR[t, i]) and not np.isnan(C[t, i]):
                if lado[i] > 0:
                    stop[i] = max(stop[i], C[t, i] - TR[t, i])
                else:
                    stop[i] = min(stop[i], C[t, i] + TR[t, i])
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
                limite_pendiente[i] = LIM[t, i]
                corto_pendiente[i] = CO[t, i]

        # Peso con signo: negativo en los cortos
        pesos[t] = np.where(lado > 0, 1.0, -1.0) * qty * cierre_ok / equity[t] if equity[t] > 0 else 0
        rotacion[t] /= max(equity_prev, 1e-12)
        costes[t] /= max(equity_prev, 1e-12)
        equity_prev = equity[t]

    # Foto final para el escáner en vivo: posiciones abiertas y órdenes para la próxima vela
    abiertas = [{"activo": activos[i], "lado": "largo" if lado[i] > 0 else "corto",
                 "entrada": indice[t_entrada[i]], "precio_entrada": float(precio_entrada[i]),
                 "stop": float(stop[i]), "peso": float(pesos[T - 1, i]) if T else 0.0,
                 "cierre": float(ultimo_cierre[i])} for i in np.where(qty > 0)[0]]
    pendientes = ([{"activo": activos[i], "accion": "vender en corto" if corto_pendiente[i] else "comprar",
                    "distancia_stop": float(dist_pendiente[i])}
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
