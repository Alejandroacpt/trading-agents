# Guía del agente investigador

Sesión semanal (sábados) de Claude que busca, implementa y prueba estrategias nuevas.
Esta guía es la fuente de verdad de cómo trabaja; la tarea programada solo apunta aquí.

## Objetivo

Encontrar cada semana entre 1 y 3 ideas nuevas con evidencia pública que puedan mejorar lo que ya opera
en algún mercado (renta variable, bonos, materias primas, cripto, forex) o en el motor táctico (velas de 1 h,
4 h o media sesión). Prioridad actual:

1. **Motor táctico de baja rotación**: el diagnóstico de costes (`reports/laboratorio/tactico.md`) muestra
   que con velas de 1 hora los costes se comen la ventaja. Buscar ideas con pocas operaciones, mucho recorrido
   por operación y entradas a favor de la tendencia diaria.
2. **Forex y bonos**: hoy no tienen ninguna estrategia válida.
3. **Datos institucionales** ya descargados: posicionamiento COT (`data/institucional/cot.csv`), tipos de
   interés (`data/macro/tipos_3m.csv`) y, si existe, compras de directivos.

## Procedimiento

1. **Leer el estado** (sin gastar de más):
   - `reports/laboratorio/ultimo.md` y `reports/laboratorio/tactico.md`
   - `reports/auditor/ultimo.md`
   - `research/registro_pruebas.csv` (qué se ha probado ya; no repetir ideas)
   - `research/fichas/` (fichas de semanas anteriores)
2. **Investigar** con búsqueda web: SSRN, arXiv (q-fin), revistas (JFE, RFS, JF, JPM, FAJ), Quantpedia,
   Alpha Architect, blogs de investigación cuantitativa. Preferir ideas con estudios académicos, datos fuera
   de muestra y explicación económica (por qué funciona y por qué no ha desaparecido).
3. **Elegir 1–3 ideas** que se puedan probar con los datos disponibles.
4. **Escribir una ficha** por idea en `research/fichas/AAAA-MM-DD-<id>.md`: reglas exactas, mercados,
   referencia, fecha de publicación, evidencia y riesgos.
5. **Fijar la rejilla de parámetros ANTES de ejecutar nada** (3 variantes como máximo, con el parámetro
   del paper en el centro) y escribirla en la ficha.
6. **Programar la idea** como familia nueva:
   - Diaria: en `src/research/familias.py` (función + entrada en `FAMILIAS`). Campo `"mercados"` si solo
     tiene sentido en algunos.
   - Táctica: en `src/tactico/familias.py` (función + entrada en `FAMILIAS_TACTICAS`, con `"velas": "4h"`
     si usa velas de 4 h / media sesión). Puede usar `limite` (orden limitada), `dinamico` (stop dinámico)
     y `max_velas`.
   - Código comentado en español y sencillo, como el resto del repositorio.
7. **Añadir un test** mínimo en `tests/` y ejecutar `python3 -m pytest -q`: todo debe pasar.
8. **Probar** con `python3 scripts/run_lab.py --sin-telegram` y/o `python3 scripts/run_lab_tactico.py --sin-telegram`
   (los datos están en el repositorio; no hace falta descargar nada). Cada variante queda en el registro de
   pruebas y endurece el listón del Sharpe deflactado: es lo correcto.
9. **Anotar el resultado en la ficha** (veredicto, Sharpe completo y de test, peor caída, qué falla) sin
   reajustar parámetros a la vista de los resultados.
10. **Subir** los cambios a `main` con un commit descriptivo.
11. **Avisar a Alejandro** lanzando el workflow de notificación:
    `gh api -X POST repos/Alejandroacpt/trading-agents/actions/workflows/notificar.yml/dispatches -f ref=main -f "inputs[mensaje]=<resumen>"`
    Resumen breve: ideas probadas, veredicto de cada una y si hay algo que proponer.

## Reglas que no se rompen

- **Nunca** modificar `config/sistema.yaml` ni `config/tactico.yaml` (lo que opera): solo proponer.
- **Nunca** cambiar los umbrales del validador ni borrar filas del registro de pruebas.
- **Nunca** ajustar parámetros después de ver resultados para que una estrategia apruebe. Si una idea falla,
  se anota y se pasa a otra.
- Si algo del sistema está roto (tests que fallan, datos sin actualizar), arreglarlo tiene prioridad sobre
  investigar, y se menciona en el aviso.
- Sesión acotada: como máximo 3 ideas por semana (el presupuesto de IA es limitado).
