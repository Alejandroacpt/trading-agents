"""
AGENTE DE ALERTAS
-----------------
Compara la cartera nueva con la de la última ejecución y redacta los
mensajes de Telegram:
  - 🟢 COMPRA / 🔴 VENTA / 🔵 AJUSTE: con sonido, uno por cambio.
  - Resumen diario de la cartera: sin sonido, una vez al día (noche).
  - Avisos del kill-switch: con sonido.

Formato de cada alerta: activo, dirección, importe en €, % de la
cartera, estrategia, por qué y cuándo se saldría.
"""

from src.agents.escaner import NOMBRE_CLASE, POR_ID, _fmt


def _eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", ".")


def _pct(x: float, dec: int = 1) -> str:
    return f"{x * 100:.{dec}f} %".replace(".", ",")


def detectar_cambios(antes: dict, despues: dict, umbral: float) -> list[dict]:
    """Lista de cambios entre dos carteras {activo: peso}."""
    cambios = []
    for a in sorted(set(antes) | set(despues)):
        w0, w1 = antes.get(a, 0.0), despues.get(a, 0.0)
        if w0 <= 1e-9 and w1 > 1e-9:
            cambios.append({"activo": a, "tipo": "COMPRA", "antes": 0.0, "despues": w1})
        elif w0 > 1e-9 and w1 <= 1e-9:
            cambios.append({"activo": a, "tipo": "VENTA", "antes": w0, "despues": 0.0})
        elif abs(w1 - w0) >= umbral:
            cambios.append({"activo": a, "tipo": "AJUSTE", "antes": w0, "despues": w1})
    orden = {"VENTA": 0, "COMPRA": 1, "AJUSTE": 2}
    return sorted(cambios, key=lambda c: orden[c["tipo"]])


def mensaje_cambio(c: dict, capital: float, detalle: dict, clases: dict) -> str:
    a = c["activo"]
    icono = {"COMPRA": "🟢", "VENTA": "🔴", "AJUSTE": "🔵"}[c["tipo"]]
    importe = abs(c["despues"] - c["antes"]) * capital
    if c["tipo"] == "COMPRA":
        cabecera = f"{icono} COMPRA {a} · {_eur(importe)} ({_pct(c['despues'])} de la cartera)"
    elif c["tipo"] == "VENTA":
        cabecera = f"{icono} VENTA {a} · todo ({_eur(c['antes'] * capital)} aprox.)"
    else:
        verbo = "Aumentar" if c["despues"] > c["antes"] else "Reducir"
        cabecera = (f"{icono} AJUSTE {a} · {verbo} {_eur(importe)} "
                    f"({_pct(c['antes'])} → {_pct(c['despues'])})")

    lineas = [cabecera]
    info = detalle.get(a, {})
    for sid, exp in info.get("estrategias", {}).items():
        e = POR_ID[sid]
        estado = "aprobada" if exp.get("estado") == "aprobada" else "en observación"
        lineas.append(f"Estrategia: {e['nombre']} ({estado})")
        lineas.append(f"Por qué: {exp['motivo']}")
        lineas.append(f"Salida: {exp['salida']}")
    if c["tipo"] == "VENTA" and info.get("motivo_venta"):
        lineas.append(f"Por qué: {info['motivo_venta']}")
    clase = clases.get(a, "")
    cuando = "hoy" if clase == "crypto" else "en la próxima sesión, cerca del cierre"
    lineas.append(f"Ejecutar: {cuando}. Precio de referencia: {_fmt(info.get('cierre', 0))}.")
    return "\n".join(lineas)


def mensaje_cartera_inicial(cartera: dict, capital: float, detalle: dict) -> str:
    lineas = ["🚀 Cartera inicial del sistema (capital virtual de " + _eur(capital) + ")", ""]
    for a, w in sorted(cartera.items(), key=lambda x: -x[1]):
        sids = ", ".join(POR_ID[s]["nombre"].split(" (")[0] for s in detalle.get(a, {}).get("estrategias", {}))
        lineas.append(f"• {a}: {_eur(w * capital)} ({_pct(w)}) · {sids}")
    lineas.append(f"• Liquidez: {_eur((1 - sum(cartera.values())) * capital)} ({_pct(1 - sum(cartera.values()))})")
    lineas += ["", "A partir de ahora solo recibirás alertas cuando algo cambie."]
    return "\n".join(lineas)


def mensaje_kill_switch(anterior: str, actual: str, drawdown: float) -> str | None:
    if anterior == actual:
        return None
    textos = {
        "MITAD": f"⚠️ KILL-SWITCH: la cartera virtual cae un {_pct(-drawdown, 0)} desde su máximo. "
                 "La exposición se reduce a la mitad.",
        "PAUSA": f"🛑 KILL-SWITCH: la cartera virtual cae un {_pct(-drawdown, 0)} desde su máximo. "
                 "Todo a liquidez hasta revisión manual.",
        "NORMAL": "✅ Kill-switch desactivado: la cartera se ha recuperado. Exposición normal.",
    }
    return textos[actual]


def mensaje_resumen(estado: dict, modelo: dict, reparto: dict, capital: float, vista: dict, kill: str) -> str:
    v = estado["virtual"]
    inicial = capital
    rent = v["valor"] / inicial - 1
    dd = v["valor"] / v["maximo"] - 1
    lineas = [
        f"📈 Cartera virtual: {_eur(v['valor'])} ({_pct(rent)} desde el {v['inicio']}) · "
        f"caída desde máximo {_pct(dd)} · kill-switch {kill.lower()}",
        "",
        "Posiciones (ejecutables):",
    ]
    cartera = estado["cartera"]
    if cartera:
        for a, w in sorted(cartera.items(), key=lambda x: -x[1]):
            lineas.append(f"• {a} {_pct(w)} ({_eur(w * capital)})")
    lineas.append(f"• Liquidez {_pct(1 - sum(cartera.values()))}")
    lineas += ["", "Reparto entre estrategias: " + " · ".join(
        f"{POR_ID[s]['nombre'].split(' (')[0].split(' +')[0]} {_pct(r, 0)}" for s, r in reparto.items())]

    movs = []
    for clase in ("equity", "bonds", "commodities", "crypto", "forex"):
        filas = {f["ticker"]: f for f in vista.get(clase, [])}
        for t in ("SPY", "TLT", "GLD", "BTC-USD", "EURUSD=X"):
            if t in filas:
                movs.append(f"{t} {filas[t]['var_dia']:+.1%}".replace(".", ","))
    if movs:
        lineas += ["", "Último día: " + " · ".join(movs)]
    return "\n".join(lineas)


def informe_markdown(estado: dict, modelo: dict, reparto: dict, vista: dict, senales: dict,
                     capital: float, kill: str) -> str:
    """reports/senales.md: foto completa del sistema para leer en GitHub."""
    v = estado["virtual"]
    L = [
        f"# Señales y cartera · {estado['actualizado']} UTC",
        "",
        f"**Cartera virtual:** {_eur(v['valor'])} (inicio {v['inicio']} con {_eur(capital)}) · "
        f"máximo {_eur(v['maximo'])} · kill-switch **{kill}**",
        "",
        "## Reparto entre estrategias",
        "",
        "| Estrategia | Estado | Capital asignado | Activos que quiere |",
        "|---|---|---|---|",
    ]
    for sid, r in reparto.items():
        d = senales[sid]
        quiere = ", ".join(f"{a} {_pct(w, 0)}" for a, w in d["pesos"].sort_values(ascending=False).items()) or "nada (liquidez)"
        L.append(f"| {d['estrategia']['nombre']} | {d['config']['estado']} | {_pct(r, 0)} | {quiere} |")

    L += ["", "## Cartera", "", "| Activo | Modelo | Ejecutable | Importe |", "|---|---|---|---|"]
    for a in sorted(set(modelo) | set(estado["cartera"]), key=lambda x: -modelo.get(x, 0)):
        w_e = estado["cartera"].get(a, 0)
        L.append(f"| {a} | {_pct(modelo.get(a, 0))} | {_pct(w_e)} | {_eur(w_e * capital)} |")
    L.append(f"| Liquidez | {_pct(1 - sum(modelo.values()))} | {_pct(1 - sum(estado['cartera'].values()))} | "
             f"{_eur((1 - sum(estado['cartera'].values())) * capital)} |")
    L += ["", "*Modelo: lo que piden las estrategias tras el agente de riesgo. Ejecutable: máximo "
          "de posiciones y mínimo en € para poco capital.*", ""]

    L += ["## Escáneres por clase de activo", ""]
    for clase, filas in vista.items():
        L += [f"### {NOMBRE_CLASE.get(clase, clase)}", "", "| Activo | Fecha | Cierre | Día | En cartera de |", "|---|---|---|---|---|"]
        for f in filas:
            en = ", ".join(f"{POR_ID[s]['nombre'].split(' (')[0]} ({_pct(w, 0)})" for s, w in f["estrategias"].items()) or "—"
            L.append(f"| {f['ticker']} {f['nombre']} | {f['fecha']} | {_fmt(f['cierre'])} | {f['var_dia']:+.1%} | {en} |")
        L.append("")
    if "forex" in vista and not any(f["estrategias"] for f in vista["forex"]):
        L += ["*Forex: ninguna estrategia activa opera divisas (la TSMOM fue rechazada).*", ""]
    return "\n".join(L) + "\n"
