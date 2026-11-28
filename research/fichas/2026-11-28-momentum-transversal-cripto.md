# Momentum transversal semanal en cripto (Liu, Tsyvinski y Wu, 2022)

- **Idea**: `momentum-transversal-cripto` · familia nueva táctica `momentum_transversal` (velas de 4 h) ·
  mercado `cripto` (8 monedas: BTC, ETH, SOL, AVAX, LINK, DOGE, LTC, BCH)
- **Fuente**: Yukun Liu, Aleh Tsyvinski y Xi Wu (2022), *Common Risk Factors in Cryptocurrency*, Journal of
  Finance 77(2), 1133-1177 — https://www.nber.org/papers/w25882 (doi 10.1111/jofi.13119) · resumen en
  Alpha Architect: https://alphaarchitect.com/factors-investing-in-cryptocurrency/
  El paper encuentra que tres factores (mercado, tamaño y **momentum**) explican la rentabilidad de las
  criptomonedas, con carteras que se rehacen cada semana según el rendimiento de las semanas anteriores.
- **Por qué ahora**: prioridad 1 (táctico agresivo, cripto en 4 h/diario, pocas operaciones) y es la
  versión en compras de la idea `corto_debilidad_relativa` (que en corto perdía). Rotar hacia las monedas
  más fuertes cada semana es algo que el sistema no hace (opera cada activo por separado).

## Reglas exactas

- Cada lunes a las 00:00 UTC (primera vela de 4 h de la semana) se ordenan las 8 monedas por su
  rendimiento de las últimas 3 semanas (126 velas de 4 h).
- Se compran las 2 mejores (el quintil superior de 8 monedas ≈ 2); se vende una cuando, en un lunes, deja
  de estar entre las 2 mejores.
- Adaptaciones al sistema: **solo compras** (el paper es largo-corto; Alpaca no permite cortos en cripto),
  stop de 3 ATR(14) y tamaño por riesgo como el resto de familias de 4 h; tras un stop solo se vuelve a
  entrar en un lunes. Costes de cripto del simulador (0,25 % por operación).

**Parámetros de la fuente, sin tocar**: 3 semanas de rendimiento pasado, rebalanceo semanal, quintil
superior (2 de 8). Nota: no pude volver a abrir el PDF hoy para comprobar el horizonte exacto del factor
CMOM; el paper prueba 1 a 4 semanas y el factor se construye con el de 3 semanas.

## Cribado (2021-01-21 a 2024-06-30, solo datos antes del test) · ❌ NO PASA

| Sharpe | Rentab. anual | Peor caída | Operaciones | Correlación con lo que opera | Veredicto |
|---|---|---|---|---|---|
| 0,13 | −0,3 % | −51 % | 217 | 0,18 | ❌ NO PASA |

- Sin costes (diagnóstico, mismos parámetros): Sharpe 0,35, +5,9 % anual, caída −47 %. Hay muy poca ventaja
  incluso antes de costes: el momentum transversal entre 8 monedas grandes no reproduce el del paper
  (que usa cientos de monedas, incluidas muy pequeñas, y gana sobre todo con la pata corta y el tamaño).
- Por años: 2021 +16 % · 2022 −32 % · 2023 +41 % · 2024 (hasta junio) −11 %. Sin filtro de régimen, en
  2022 compra "las que menos caen" y cae igual.
- Correlación baja (0,18) con el momentum en acciones, pero sin ventaja no aporta.
- **Resultado: rechazada.** No pasa a validación ni se repite con otros parámetros (`laboratorio: False`).
