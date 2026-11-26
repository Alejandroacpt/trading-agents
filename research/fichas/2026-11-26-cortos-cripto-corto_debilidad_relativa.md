# Corto: las monedas más débiles frente a BTC (cripto, 4 h)

- **Idea**: `cortos-cripto-corto_debilidad_relativa` · familia `corto_debilidad_relativa` (nueva)
- **Fuente**: encargo de Alejandro (26 nov 2026), reglas fijadas en `research/GUIA_INVESTIGADOR.md`.
  Momentum transversal en cripto (Liu, Tsyvinski y Wu, 2022, *Journal of Finance*), lado corto.
- **Mercado / velas**: `cripto` (8 monedas; BTC solo como referencia, no se opera), velas de 4 h.

## Reglas exactas

- Régimen: BTC con cierre diario de ayer por debajo de su media de 50 días.
- En cada vela se ordenan las 7 monedas que no son BTC por su rendimiento de N velas MENOS el de BTC.
- Entrada en corto en las 2 peores; salida cuando una deja de estar entre las 3 peores o termina el régimen.
- Stop 3 ATR(14). Financiación del corto 10 % anual.
- Parámetro de la fuente: **N = 90**. Rejilla fijada el 26 nov: N ∈ {42, 90, 180}.

## Cribado (2021-01-21 a 2024-06-30)

| Sharpe | Rentab. anual | SPY mismo periodo | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|---|
| −0,66 | −15,2 % | +12,3 % | −52 % | 438 | −0,16 | ❌ NO PASA |

- Por años: 2021 −5 %, **2022 +9 %**, 2023 −26 %, 2024 (1.er semestre) −26 %.
- Sin costes: Sharpe −0,07. La moneda más débil del momento suele rebotar con fuerza (rotaciones entre
  altcoins): vender a las rezagadas no tiene ventaja ni antes de costes.
- Informativo, fuera del cribado (no cambia el veredicto): 2025-26 −7 % con 252 operaciones.

**Resultado: rechazada.** No pasa a validación completa.
