# Laboratorio táctico (velas de 1 hora) · 2026-11-25

12 experimentos. Pruebas acumuladas en el registro: **184**.

Simulación con stop en cada operación, tamaño por riesgo (1,5 % del capital del motor), entrada en la vela siguiente a la señal, costes por operación (cripto 0,25 %, acciones 0,05 %) y, en acciones, sin cierres el mismo día (norma PDT). Test desde julio de 2024; mínimo 100 operaciones.

| Experimento | Veredicto | Sharpe completo | Sharpe test | CAGR | Peor caída | Operaciones | % aciertos | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|---|---|
| Momentum con tendencia diaria (media sesión) · Acciones y ETFs | 🟡 OBSERVACIÓN | 0,96 | 0,99 | 13,2 % | -20 % | 520 | 38 % | 12 % / 14 % | Sharpe deflactado (DSR) |
| Momentum con tendencia diaria (4 h) · Cripto | ❌ RECHAZADA | 0,13 | 0,38 | -1,3 % | -58 % | 945 | 29 % | 7 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura con tendencia diaria (4 h) · Cripto | ❌ RECHAZADA | 0,26 | 0,33 | 3,5 % | -45 % | 387 | 30 % | 6 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura con tendencia diaria (media sesión) · Acciones y ETFs | ❌ RECHAZADA | 0,94 | 0,27 | 14,0 % | -14 % | 316 | 44 % | 3 % / 14 % | Sharpe en test, Sharpe deflactado (DSR), Bate al SPY (test) |
| Momentum horario con stop dinámico · Acciones y ETFs | ❌ RECHAZADA | 0,32 | 0,20 | 3,8 % | -30 % | 2632 | 39 % | 2 % / 14 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | ❌ RECHAZADA | 0,42 | -0,58 | 5,3 % | -32 % | 1083 | 30 % | -9 % / 14 % | Sharpe en test, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Retroceso en tendencia con orden limitada (media sesión) · Acciones y ETFs | ❌ RECHAZADA | -0,26 | -0,76 | -3,2 % | -26 % | 1637 | 60 % | -8 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | ❌ RECHAZADA | -0,83 | -1,22 | -11,7 % | -57 % | 5223 | 50 % | -16 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Retroceso en tendencia con orden limitada (4 h) · Cripto | ❌ RECHAZADA | -0,81 | -1,42 | -10,7 % | -59 % | 1247 | 57 % | -17 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura horaria (canal de N velas) · Cripto | ❌ RECHAZADA | -1,14 | -1,97 | -43,3 % | -98 % | 2243 | 21 % | -52 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Momentum horario con stop dinámico · Cripto | ❌ RECHAZADA | -3,44 | -4,60 | -76,9 % | -100 % | 6715 | 22 % | -82 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Reversión horaria (RSI-2 con tendencia) · Cripto | ❌ RECHAZADA | -6,05 | -7,81 | -71,5 % | -100 % | 6929 | 40 % | -76 % / 14 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |

## Diagnóstico: ¿hay ventaja antes de costes?

Mismos experimentos (parámetros por defecto) sin costes. Si el Sharpe bruto es bueno y el neto malo, la idea tiene algo pero opera demasiado o con stops demasiado ajustados para sus costes.

| Experimento | Sharpe bruto | Sharpe neto | Operaciones | Duración media | Resultado medio por operación (neto) |
|---|---|---|---|---|---|
| Momentum con tendencia diaria (media sesión) · Acciones y ETFs | 1,09 | 0,96 | 520 | 421 h | 0,60 % |
| Momentum con tendencia diaria (4 h) · Cripto | 0,60 | 0,13 | 945 | 101 h | -0,00 % |
| Ruptura con tendencia diaria (4 h) · Cripto | 0,48 | 0,26 | 387 | 153 h | 0,49 % |
| Ruptura con tendencia diaria (media sesión) · Acciones y ETFs | 1,01 | 0,94 | 316 | 663 h | 1,59 % |
| Momentum horario con stop dinámico · Acciones y ETFs | 0,95 | 0,32 | 2632 | 80 h | 0,03 % |
| Ruptura horaria (canal de N velas) · Acciones y ETFs | 0,68 | 0,42 | 1083 | 185 h | 0,21 % |
| Retroceso en tendencia con orden limitada (media sesión) · Acciones y ETFs | 0,16 | -0,26 | 1637 | 63 h | -0,07 % |
| Reversión horaria (RSI-2 con tendencia) · Acciones y ETFs | 0,55 | -0,83 | 5223 | 34 h | -0,06 % |
| Retroceso en tendencia con orden limitada (4 h) · Cripto | 0,53 | -0,81 | 1247 | 15 h | -0,20 % |
| Ruptura horaria (canal de N velas) · Cripto | -0,07 | -1,14 | 2243 | 37 h | -0,50 % |
| Momentum horario con stop dinámico · Cripto | -0,15 | -3,44 | 6715 | 15 h | -0,54 % |
| Reversión horaria (RSI-2 con tendencia) · Cripto | 0,75 | -6,05 | 6929 | 4 h | -0,43 % |

## Candidatas para el motor táctico

- 🟡 **Momentum con tendencia diaria (media sesión) · Acciones y ETFs** (`tac_momentum_tendencia__acciones`)
