# Corto: ruptura bajista con la tendencia bajista confirmada (cripto, 4 h)

- **Idea**: `cortos-cripto-corto_ruptura_bajista` · familia `corto_ruptura_bajista` (nueva)
- **Fuente**: encargo de Alejandro (26 nov 2026), reglas fijadas en `research/GUIA_INVESTIGADOR.md`.
  Canal de Donchian a la baja (Faith, *Way of the Turtle*, 2007) con filtro de tendencia de largo plazo.
- **Mercado / velas**: `cripto` (8 monedas), velas de 4 h, solo cortos.

## Reglas exactas

- Régimen: cierre diario de ayer por debajo de su media de 200 días Y esa media (la de ayer) por debajo de
  la de 20 días antes.
- Entrada en corto: cierre por debajo del mínimo de las N velas anteriores.
- Salida: cierre por encima del máximo de N/2 velas, o fin del régimen.
- Stop 3 ATR(14), stop dinámico 4 ATR. Financiación del corto 10 % anual.
- Parámetro de la fuente: **N = 60**. Rejilla fijada el 26 nov: N ∈ {30, 60, 120}.

## Cribado (2021-01-21 a 2024-06-30)

| Sharpe | Rentab. anual | SPY mismo periodo | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|---|
| 0,18 | +1,6 % | +12,3 % | −33 % | 131 | −0,14 | ❌ NO PASA (Sharpe < 0,5) |

- Por años: 2021 −3 %, **2022 +39 %**, 2023 −20 %, 2024 (1.er semestre) −2 %.
- Sin costes: Sharpe 0,40. Es la mejor de las tres: gana bien en el mercado bajista de 2022 y está
  descorrelacionada (−0,14), pero devuelve casi todo en cuanto la tendencia cambia (115 de 131 salidas son
  por stop; acierta el 34 %).
- Informativo, fuera del cribado (no cambia el veredicto): 2025-26 −21 % con 100 operaciones.

**Resultado: rechazada.** No pasa a validación completa ni a la comprobación con BITI/SETH.
Nota para el futuro: como "seguro" de cartera solo tendría sentido si se activa en mercados bajistas
largos tipo 2022, y no hay forma de saberlo de antemano con este régimen.
