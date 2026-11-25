# Laboratorio de estrategias · 2026-11-25

26 experimentos (familia × mercado). Pruebas acumuladas en el registro: **184** (el Sharpe deflactado se calcula con este total).

Forex medido **con carry** (diferencial de tipos de interés incluido).

> Las propuestas no se activan solas: hay que decidir si entran en `config/sistema.yaml`.

## Renta variable

En vivo hoy: ninguna estrategia.

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|
| Tendencia multi-horizonte | 🟡 OBSERVACIÓN | 0,59 | 0,45 | -26 % | 74 % | 7 % / 13 % | Sharpe deflactado (DSR), Bate al SPY (test) |
| Momentum temporal mensual | 🟡 OBSERVACIÓN | 0,61 | 0,45 | -24 % | 78 % | 8 % / 13 % | Sharpe deflactado (DSR), Bate al SPY (test) |
| Tendencia por media móvil | ❌ RECHAZADA | 0,48 | 0,46 | -43 % | 50 % | 7 % / 13 % | Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,45 | 0,33 | -28 % | 44 % | 5 % / 13 % | Sharpe en test, Sharpe deflactado (DSR), Bate al SPY (test) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | 0,30 | -0,05 | -12 % | 16 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |

## Bonos

En vivo hoy: ninguna estrategia.

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,28 | 0,13 | -10 % | 8 % | 3 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |
| Momentum temporal mensual | ❌ RECHAZADA | 0,29 | -0,11 | -16 % | 9 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |
| Tendencia por media móvil | ❌ RECHAZADA | 0,10 | -0,17 | -16 % | 1 % | 1 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,17 | -0,25 | -7 % | 0 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Tendencia multi-horizonte | ❌ RECHAZADA | 0,21 | -0,33 | -13 % | 4 % | 1 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |

## Materias primas

En vivo hoy: ninguna estrategia.

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | 🟡 OBSERVACIÓN | 0,53 | 0,82 | -27 % | 39 % | 12 % / 13 % | Sharpe deflactado (DSR) |
| Tendencia multi-horizonte | ❌ RECHAZADA | 0,43 | 0,69 | -41 % | 22 % | 11 % / 13 % | Sharpe walk-forward, Sharpe deflactado (DSR), Drawdown máximo |
| Momentum temporal mensual | ❌ RECHAZADA | 0,39 | 0,59 | -42 % | 18 % | 10 % / 13 % | Sharpe post-publicación, Sharpe walk-forward, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Tendencia por media móvil | ❌ RECHAZADA | 0,28 | 0,53 | -39 % | 7 % | 9 % / 13 % | Sharpe post-publicación, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,21 | -0,07 | -26 % | 0 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |

## Cripto

En vivo hoy: Tendencia en cripto + control de volatilidad (Sharpe test 0,93, peor caída -40 %).

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | 🟡 OBSERVACIÓN | 1,17 | 1,04 | -62 % | 90 % | 44 % / 13 % | Drawdown máximo |
| Tendencia por media móvil | 🟡 OBSERVACIÓN | 1,28 | 0,94 | -64 % | 95 % | 42 % / 13 % | Drawdown máximo |
| Tendencia multi-horizonte | 🟡 OBSERVACIÓN | 1,17 | 0,68 | -58 % | 88 % | 25 % / 13 % | Sharpe deflactado (DSR) |
| Momentum temporal mensual | 🟡 OBSERVACIÓN | 1,10 | 0,62 | -69 % | 82 % | 23 % / 13 % | Sharpe deflactado (DSR), Drawdown máximo |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | 0,12 | -0,05 | -38 % | 1 % | -1 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |

## Forex

En vivo hoy: ninguna estrategia.

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Test: rent. / SPY | Qué falla |
|---|---|---|---|---|---|---|---|
| Carry de divisas | ❌ RECHAZADA | 0,23 | 0,46 | -27 % | 7 % | 5 % / 13 % | Robustez de parámetros, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Tendencia por media móvil | ❌ RECHAZADA | 0,19 | -0,03 | -25 % | 4 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Momentum temporal mensual | ❌ RECHAZADA | -0,02 | -0,13 | -33 % | 0 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,09 | -0,13 | -23 % | 1 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo, Bate al SPY (test) |
| Tendencia multi-horizonte | ❌ RECHAZADA | 0,12 | -0,28 | -17 % | 2 % | 1 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Bate al SPY (test) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,25 | -0,44 | -17 % | 0 % | 2 % / 13 % | Sharpe en test, Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |

## Propuestas

Ninguna esta semana: ningún experimento aprobado mejora lo que ya opera en su mercado.
