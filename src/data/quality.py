"""
CONTROL DE CALIDAD DE LOS DATOS
-------------------------------
Antes de que una estrategia use los precios, revisamos que tengan
sentido. Un dato malo (un precio a cero, un hueco de semanas, un salto
absurdo) puede generar una señal falsa de compra o venta.

Este módulo NO corrige nada: solo avisa. Cada problema se marca como:
  - "ERROR":  el dato no es usable (p. ej. precios negativos o vacíos)
  - "AVISO":  conviene revisarlo, pero puede ser real (p. ej. un
              desplome de cripto del 40 % en un día)
"""

import pandas as pd

from src.config import CLASES_7_DIAS

# Movimiento diario máximo "normal" por clase de activo.
# Por encima se avisa (no tiene por qué ser un error).
SALTO_MAXIMO = {
    "crypto": 0.40,
    "commodities": 0.30,
    "equity": 0.25,
    "bonds": 0.15,
    "forex": 0.10,
    "cash": 0.02,
}

# Días naturales sin datos a partir de los cuales consideramos que hay
# un hueco (los fines de semana y festivos son normales en bolsa).
#   cripto: se tolera que falte 1 día suelto; 2 seguidos ya es hueco
#   bolsa: fin de semana + festivo es normal; más de 6 días, no
HUECO_MAXIMO = {"7dias": 2, "laborables": 6}

# Días naturales de antigüedad del último dato antes de avisar de que
# la serie está "parada" (la fuente ha dejado de actualizarse).
ANTIGUEDAD_MAXIMA = {"7dias": 2, "laborables": 4}


def check_prices(
    df: pd.DataFrame,
    clase: str,
    hoy: pd.Timestamp | None = None,
    ventana_dias: int | None = None,
) -> list[dict]:
    """Revisa una tabla de precios y devuelve la lista de problemas.

    ventana_dias: si se indica, solo se revisan los últimos N días
    (lo usamos en el aviso diario, para no repetir cada día problemas
    antiguos ya conocidos, como el cierre de bolsa tras el 11-S).
    Si es None, se revisa todo el histórico.
    """
    problemas = []

    def add(nivel, msg):
        problemas.append({"nivel": nivel, "mensaje": msg})

    if df.empty:
        add("ERROR", "no hay datos")
        return problemas

    tipo = "7dias" if clase in CLASES_7_DIAS else "laborables"
    hoy = (hoy or pd.Timestamp.today()).normalize()

    serie_completa = df
    if ventana_dias:
        # Incluimos un día extra antes de la ventana para poder calcular
        # el primer rendimiento y el primer hueco dentro de ella.
        inicio = hoy - pd.Timedelta(days=ventana_dias)
        anteriores = df[df.index < inicio].tail(1)
        df = pd.concat([anteriores, df[df.index >= inicio]])
        if df.empty:
            df = serie_completa.tail(1)

    # 1) Valores vacíos en los precios
    vacios = int(df[["open", "high", "low", "close"]].isna().sum().sum())
    if vacios:
        add("AVISO", f"{vacios} valores vacíos en open/high/low/close")

    # 2) Precios cero o negativos (imposibles en estos activos)
    no_positivos = int((df[["open", "high", "low", "close"]] <= 0).sum().sum())
    if no_positivos:
        add("ERROR", f"{no_positivos} precios <= 0")

    # 3) Coherencia de la vela: el mínimo no puede superar al cierre, etc.
    #    (se permite un margen mínimo por redondeos)
    #    En forex NO se comprueba: Yahoo da máximos/mínimos poco fiables en
    #    divisas (~2 % de las velas) y las estrategias solo usan el cierre.
    if clase != "forex":
        tol = 1e-6 * df["close"].abs()
        incoherentes = (
            (df["low"] > df[["open", "close"]].min(axis=1) + tol)
            | (df["high"] < df[["open", "close"]].max(axis=1) - tol)
        ).sum()
        if incoherentes:
            add("AVISO", f"{int(incoherentes)} velas con high/low incoherentes")

    # 4) Saltos diarios extremos
    rendimientos = df["close"].pct_change().abs()
    limite = SALTO_MAXIMO.get(clase, 0.25)
    saltos = rendimientos[rendimientos > limite]
    if len(saltos):
        peores = ", ".join(f"{d.date()} ({r:.0%})" for d, r in saltos.nlargest(3).items())
        add("AVISO", f"{len(saltos)} saltos diarios > {limite:.0%}: {peores}")

    # 5) Huecos: periodos largos sin ningún dato
    dias_entre = df.index.to_series().diff().dt.days
    huecos = dias_entre[dias_entre > HUECO_MAXIMO[tipo]]
    if len(huecos):
        mayor = huecos.idxmax()
        add("AVISO", f"{len(huecos)} huecos; el mayor, {int(huecos.max())} días hasta {mayor.date()}")

    # 6) Serie parada: el último dato es demasiado antiguo
    ultimo = serie_completa.index.max()
    antiguedad = (hoy - ultimo).days
    if antiguedad > ANTIGUEDAD_MAXIMA[tipo]:
        add("AVISO", f"último dato del {ultimo.date()} ({antiguedad} días)")

    return problemas


def resumen_estado(problemas: list[dict]) -> str:
    """Convierte la lista de problemas en un estado: OK, AVISO o ERROR."""
    niveles = {p["nivel"] for p in problemas}
    if "ERROR" in niveles:
        return "ERROR"
    if "AVISO" in niveles:
        return "AVISO"
    return "OK"
