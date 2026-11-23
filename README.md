# Red de agentes de trading

Sistema que vigila ~20 activos (ETFs, materias primas, cripto y forex), aplica estrategias públicas validadas y envía alertas de compra/venta por Telegram, con paper trading para medir resultados sin dinero real.

> Proyecto personal de investigación. No es asesoramiento financiero.

## Estado

| Semana | Entregable | Estado |
|---|---|---|
| 1 | Repositorio, capa de datos de los 4 mercados, Telegram, conexión con Alpaca paper | ✅ código listo |
| 2–3 | Motor de backtest + validador de estrategias | — |
| 4 | Escáneres diarios + agente de riesgo + alertas | — |
| 5 | Paper trading automático + diario + auditor semanal | — |

## Cómo funciona (semana 1)

Dos veces al día, GitHub ejecuta el **Pipeline diario** en sus servidores (no hace falta tener el ordenador encendido):

1. Descarga el histórico diario de todos los activos de `config/universe.yaml` (Yahoo Finance; Kraken de respaldo para cripto).
2. Revisa la calidad de los datos (precios imposibles, huecos, saltos extremos, series paradas).
3. Guarda los precios en `data/` y el informe en `reports/data_status.md`.
4. Envía un resumen a Telegram.

## Estructura

```
config/universe.yaml        <- activos vigilados (edítalo para añadir/quitar)
src/data/sources.py         <- descarga de Yahoo / Kraken
src/data/store.py           <- guardado en CSV
src/data/quality.py         <- control de calidad
src/data/update.py          <- orquesta la actualización e informes
src/alerts/telegram.py      <- envío de mensajes
scripts/update_data.py      <- paso 1 del pipeline diario
scripts/test_connections.py <- prueba Telegram y Alpaca
tests/                      <- pruebas automáticas (datos simulados)
.github/workflows/          <- tareas programadas de GitHub
data/                       <- precios (los rellena el robot)
reports/                    <- informes (los rellena el robot)
```

## Puesta en marcha

Los secretos se guardan en GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Nunca se escriben en el código.

| Secreto | De dónde sale |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather en Telegram, al crear el bot |
| `TELEGRAM_CHAT_ID` | Lo muestra el workflow "Probar conexiones" tras escribir al bot |
| `ALPACA_API_KEY` | Panel de Alpaca, cuenta **Paper**, sección API Keys |
| `ALPACA_SECRET_KEY` | Ídem (solo se muestra una vez: cópiala al generarla) |

Después:

1. **Actions → Probar conexiones → Run workflow**: comprueba Telegram y Alpaca.
2. **Actions → Pipeline diario → Run workflow**: primera descarga completa de datos.
3. Revisa `reports/data_status.md`.

## Ejecutar en local (opcional)

```bash
pip install -r requirements.txt pytest
pytest -q                                  # pruebas
python scripts/update_data.py --sin-telegram
```
