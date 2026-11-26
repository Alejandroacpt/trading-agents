# Corto: vender los rebotes en tendencia bajista (cripto, 4 h)

- **Idea**: `cortos-cripto-corto_rebote` · familia `corto_rebote` (nueva, `src/tactico/familias.py`)
- **Fuente**: encargo de Alejandro (26 nov 2026), reglas fijadas en `research/GUIA_INVESTIGADOR.md`.
  Técnica clásica de venta de rebotes a la media en tendencia bajista (Elder, *Trading for a Living*, 1993).
- **Mercado / velas**: `cripto` (8 monedas de `config/tactico.yaml`), velas de 4 h, solo cortos.

## Reglas exactas

- Régimen bajista: cierre diario de AYER por debajo de su media de 50 días.
- Entrada en corto: el máximo de la vela toca la media exponencial de N velas, la vela cierra por debajo de
  ella y en negativo (cierre < apertura). Se ejecuta en la apertura de la vela siguiente.
- Salida: cierre por encima de la media de N velas, o 30 velas (5 días).
- Stop 2 ATR(14) por encima de la entrada, stop dinámico 3 ATR. Financiación del corto 10 % anual.
- Parámetro de la fuente: **N = 50**. Rejilla fijada el 26 nov (antes de ver resultados): N ∈ {20, 50, 100}.

## Cribado (solo datos anteriores a jul-2024: 2021-01-21 a 2024-06-30)

| Sharpe | Rentab. anual | SPY mismo periodo | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|---|
| −2,13 | −53,1 % | +12,3 % | −95 % | 1.081 | −0,18 | ❌ NO PASA |

- Por años (desarrollo): 2021 −1 %, **2022 −18 %**, 2023 −86 %, 2024 (1.er semestre) −34 %.
- Sin costes ni financiación tampoco funciona (Sharpe bruto −1,06): no es un problema de costes, la regla
  no tiene ventaja. Acierta el 19 % de las veces; la mayoría de operaciones salen enseguida porque el
  precio vuelve a cerrar por encima de la media (los rebotes en cripto siguen subiendo).
- Informativo, fuera del cribado (no cambia el veredicto): 2025-26 −82 % con 752 operaciones.

**Resultado: rechazada.** No pasa a validación completa. Ni siquiera gana en 2022, el año bajista.
