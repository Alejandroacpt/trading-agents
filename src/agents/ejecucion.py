"""
AGENTE DE EJECUCIÓN (PAPER)
---------------------------
Lleva la cuenta paper de Alpaca a la cartera ejecutable que decide el
agente de riesgo. Cada ejecución:
  1. Cancela las órdenes pendientes de los activos que gestiona el
     sistema (para no duplicar: se recalcula todo desde cero).
  2. Lee las posiciones reales de la cuenta paper.
  3. Calcula la diferencia con la cartera objetivo y envía las órdenes:
     ventas primero (liberan liquidez) y compras después.

Capital de referencia:
  - Si la cuenta paper tiene un saldo parecido al capital del sistema
    (se recomienda reiniciarla a ~1.150 $ ≈ 1.000 €), se usa el valor
    real de la cuenta: así el resultado paper es el resultado de verdad.
  - Si sigue con los 100.000 $ por defecto, se usa como presupuesto el
    valor de la cartera virtual convertido a dólares, y el resto del
    saldo se ignora.

Modos (config/sistema.yaml -> alpaca.modo):
  - simulacion: calcula y registra las órdenes, pero NO las envía.
  - paper:      las envía a la cuenta paper.
"""

from datetime import datetime, timezone

from src.broker.alpaca import es_cripto, normalizar


def capital_referencia(cuenta: dict, valor_virtual_eur: float, eurusd: float) -> tuple[float, str]:
    """Dólares que gestiona el sistema dentro de la cuenta paper."""
    presupuesto = valor_virtual_eur * eurusd
    equity = float(cuenta.get("equity", 0))
    if 0 < equity <= presupuesto * 2:
        return equity, "cuenta"          # cuenta ajustada al capital del sistema
    return presupuesto, "presupuesto"    # cuenta con saldo por defecto: se usa una parte


def posiciones_gestionadas(posiciones: list[dict], universo: list[str]) -> dict:
    """{ticker: {"valor": $, "cantidad": n, "precio": $}} solo de activos del universo."""
    por_simbolo = {normalizar(t if not es_cripto(t) else t.replace("-", "/")): t for t in universo}
    salida = {}
    for p in posiciones:
        t = por_simbolo.get(normalizar(p["symbol"]))
        if t:
            salida[t] = {"valor": float(p["market_value"]), "cantidad": float(p["qty"]),
                         "precio": float(p["current_price"])}
    return salida


def calcular_ordenes(cartera: dict, capital_usd: float, actuales: dict, minimo_usd: float) -> list[dict]:
    """Órdenes para pasar de las posiciones actuales a la cartera objetivo.

    cartera  : {ticker: peso objetivo}
    actuales : {ticker: {"valor", "cantidad", "precio"}}
    """
    ordenes = []
    for t in sorted(set(cartera) | set(actuales)):
        objetivo = cartera.get(t, 0.0) * capital_usd
        actual = actuales.get(t, {}).get("valor", 0.0)
        diferencia = objetivo - actual
        if objetivo <= 0 and actual > 0:
            ordenes.append({"activo": t, "accion": "cerrar", "importe": actual})
        elif abs(diferencia) >= minimo_usd:
            if diferencia > 0:
                ordenes.append({"activo": t, "accion": "comprar", "importe": diferencia})
            else:
                precio = actuales[t]["precio"]
                cantidad = min(-diferencia / precio, actuales[t]["cantidad"])
                ordenes.append({"activo": t, "accion": "vender", "importe": -diferencia, "cantidad": cantidad})
    # Primero las ventas, para liberar liquidez
    return sorted(ordenes, key=lambda o: 0 if o["accion"] in ("cerrar", "vender") else 1)


def ejecutar(ordenes: list[dict], cliente, modo: str, universo: list[str]) -> list[dict]:
    """Cancela pendientes y envía las órdenes. Devuelve el resultado de cada una."""
    gestionados = {normalizar(t.replace("-", "/")) for t in universo}
    if modo == "paper":
        for o in cliente.ordenes_abiertas():
            if normalizar(o["symbol"]) in gestionados:
                cliente.cancelar(o["id"])

    marca = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    resultados = []
    for i, o in enumerate(ordenes):
        r = {**o, "estado": "simulada", "order_id": ""}
        if modo == "paper":
            ref = f"ta-{marca}-{i}"
            try:
                if o["accion"] == "cerrar":
                    resp = cliente.cerrar_posicion(o["activo"])
                elif o["accion"] == "vender":
                    resp = cliente.vender_cantidad(o["activo"], o["cantidad"], ref)
                else:
                    resp = cliente.comprar_importe(o["activo"], o["importe"], ref)
                r["estado"] = resp.get("status", "enviada")
                r["order_id"] = resp.get("id", "")
            except Exception as e:  # noqa: BLE001 - una orden fallida no debe parar las demás
                r["estado"] = "error"
                r["error"] = str(e)[:200]
        resultados.append(r)
    return resultados
