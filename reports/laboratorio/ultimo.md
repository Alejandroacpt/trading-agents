# Laboratorio de estrategias · 2026-11-23

25 experimentos (familia × mercado). Pruebas acumuladas en el registro: **139** (el Sharpe deflactado se calcula con este total).

> Las propuestas no se activan solas: hay que decidir si entran en `config/sistema.yaml`.

## Renta variable

En vivo hoy: Tendencia multi-horizonte (1-3-12 meses) (Sharpe test 0,51, peor caída -10 %); Filtro de tendencia de 10 meses (Faber) (Sharpe test 0,46, peor caída -18 %).

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Qué falla |
|---|---|---|---|---|---|---|
| Tendencia por media móvil | 🟡 OBSERVACIÓN | 0,48 | 0,46 | -43 % | 54 % | Sharpe deflactado (DSR), Drawdown máximo |
| Tendencia multi-horizonte | 🟡 OBSERVACIÓN | 0,58 | 0,43 | -26 % | 75 % | Sharpe deflactado (DSR) |
| Momentum temporal mensual | 🟡 OBSERVACIÓN | 0,60 | 0,42 | -24 % | 79 % | Sharpe deflactado (DSR) |
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,45 | 0,33 | -28 % | 48 % | Sharpe en test (2018+), Sharpe deflactado (DSR) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | 0,30 | -0,08 | -12 % | 18 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |

## Bonos

En vivo hoy: Tendencia multi-horizonte (1-3-12 meses) (Sharpe test 0,51, peor caída -10 %); Filtro de tendencia de 10 meses (Faber) (Sharpe test 0,46, peor caída -18 %).

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Qué falla |
|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,28 | 0,13 | -10 % | 10 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Momentum temporal mensual | ❌ RECHAZADA | 0,29 | -0,11 | -16 % | 11 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Tendencia por media móvil | ❌ RECHAZADA | 0,10 | -0,17 | -16 % | 1 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,17 | -0,25 | -7 % | 0 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Tendencia multi-horizonte | ❌ RECHAZADA | 0,21 | -0,33 | -13 % | 5 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |

## Materias primas

En vivo hoy: Tendencia multi-horizonte (1-3-12 meses) (Sharpe test 0,51, peor caída -10 %); Filtro de tendencia de 10 meses (Faber) (Sharpe test 0,46, peor caída -18 %).

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Qué falla |
|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | 🟡 OBSERVACIÓN | 0,53 | 0,82 | -27 % | 42 % | Sharpe deflactado (DSR) |
| Tendencia multi-horizonte | 🟡 OBSERVACIÓN | 0,43 | 0,70 | -41 % | 25 % | Sharpe deflactado (DSR), Drawdown máximo |
| Momentum temporal mensual | ❌ RECHAZADA | 0,40 | 0,60 | -42 % | 21 % | Sharpe post-publicación, Sharpe walk-forward, Sharpe deflactado (DSR), Drawdown máximo |
| Tendencia por media móvil | ❌ RECHAZADA | 0,28 | 0,53 | -39 % | 9 % | Sharpe post-publicación, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,20 | -0,05 | -26 % | 0 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |

## Cripto

En vivo hoy: Tendencia en cripto + control de volatilidad (Sharpe test 0,93, peor caída -40 %).

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Qué falla |
|---|---|---|---|---|---|---|
| Ruptura de canal (Donchian) | 🟡 OBSERVACIÓN | 1,17 | 1,04 | -62 % | 92 % | Drawdown máximo |
| Tendencia por media móvil | 🟡 OBSERVACIÓN | 1,28 | 0,94 | -64 % | 96 % | Drawdown máximo |
| Tendencia multi-horizonte | 🟡 OBSERVACIÓN | 1,18 | 0,68 | -58 % | 90 % | Sharpe deflactado (DSR) |
| Momentum temporal mensual | 🟡 OBSERVACIÓN | 1,10 | 0,62 | -69 % | 85 % | Sharpe deflactado (DSR), Drawdown máximo |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | 0,12 | -0,05 | -38 % | 1 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |

## Forex

En vivo hoy: ninguna estrategia.

| Familia | Veredicto | Sharpe completo | Sharpe test 2018+ | Peor caída | DSR | Qué falla |
|---|---|---|---|---|---|---|
| Momentum temporal mensual | ❌ RECHAZADA | -0,05 | -0,11 | -32 % | 0 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Tendencia por media móvil | ❌ RECHAZADA | -0,00 | -0,17 | -31 % | 0 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Ruptura de canal (Donchian) | ❌ RECHAZADA | 0,05 | -0,18 | -18 % | 1 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR) |
| Tendencia multi-horizonte | ❌ RECHAZADA | 0,02 | -0,21 | -20 % | 1 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |
| Reversión a la media (RSI-2) | ❌ RECHAZADA | -0,37 | -0,65 | -21 % | 0 % | Sharpe en test (2018+), Sharpe post-publicación, Robustez de parámetros, Sharpe walk-forward, Sharpe con costes x2, Sharpe deflactado (DSR), Drawdown máximo |

## Propuestas

Ninguna esta semana: ningún experimento aprobado mejora lo que ya opera en su mercado.
