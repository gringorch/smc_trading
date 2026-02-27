## Context
La capa de eventos SMC ya detecta estructura/imbalances/contexto, pero todavía no existe una capa formal que convierta esos eventos en decisiones de estrategia y resultados de backtesting sobre un periodo histórico.

Además, se necesita una forma simple de entender cómo funciona el programa y cómo usarlo de punta a punta (configurar estrategia, ejecutar backtest, leer resultados).

## Requirements
1. Introducir una capa de definición de estrategia **declarativa** (sin hardcode por estrategia) para evaluar señales sobre eventos SMC.
2. El formato de estrategia debe ser estructurado y validable (YAML o JSON con schema), no texto libre.
3. La estrategia debe permitir, como mínimo:
   - filtros de contexto HTF (market_state, zonas premium/discount, POIs),
   - condiciones de trigger en LTF (ej. IFVG/BOS/CHOCH/sweep),
   - reglas de invalidación,
   - reglas de salida (SL/TP o exit por condición).
4. Definir un flujo HTF -> LTF explícito:
   - detectar POIs en HTF,
   - limitar búsqueda en LTF al contexto de POI,
   - evaluar trigger de entrada long/short.
5. Incorporar un motor de backtesting sobre rango histórico que consuma `TradeIntent` y produzca `TradeResult`.
6. El backtester debe soportar al menos:
   - lado long/short,
   - precio/timestamp de entrada,
   - stop y take profit,
   - motivo de salida,
   - costos básicos configurables (fee y slippage).
7. Exponer un reporte mínimo de resultados:
   - cantidad de trades,
   - win rate,
   - PnL bruto/neto,
   - profit factor,
   - max drawdown,
   - lista de trades.
8. Mantener separación estricta de capas:
   - detectores generan eventos,
   - strategy engine decide señales/intents,
   - backtester simula fills/salidas,
   - plotting/reporting solo visualiza.
9. Agregar una guía simple de uso para desarrollador/backend con pasos concretos:
   - cómo definir una estrategia,
   - cómo correr un backtest,
   - cómo interpretar output.
10. Mantener compatibilidad con funciones existentes (`analyze`, `analyze_multi_tf`, `analyze_adaptive`) como proveedoras de eventos.

## Non-goals
1. Ejecución en broker real o paper trading en tiempo real.
2. Optimización automática de parámetros (grid search/genéticos) en esta fase.
3. UI web completa de estrategia/backtesting.
4. Persistencia obligatoria de resultados en DB (puede ser in-memory + export opcional).

## Technical Design
### 1) Contratos nuevos
- `StrategyDefinition`
  - metadata (`name`, `version`, `description`)
  - `timeframes` (`htf`, `ltf_default`, `ltf_trend`)
  - `context_filters` (market_state, discount/premium, distancia a POI)
  - `trigger_rules` (event kinds + constraints)
  - `risk_rules` (sl, tp, sizing base)
  - `execution_rules` (entry mode, slippage, fees)
- `TradeIntent`
  - `ts`, `direction`, `entry_ref`, `sl`, `tp`, `meta`
- `TradeResult`
  - `entry_ts/price`, `exit_ts/price`, `direction`, `qty`, `pnl_gross`, `pnl_net`, `exit_reason`, `meta`
- `BacktestReport`
  - `summary metrics` + `trades` + `strategy_id` + `period`

### 2) Módulos propuestos
- `src/strategy/definitions.py`
  - parse + validate de YAML/JSON a `StrategyDefinition`
- `src/strategy/engine.py`
  - `evaluate_strategy(events_htf, events_ltf, strategy_def) -> list[TradeIntent]`
- `src/backtesting/simulator.py`
  - `run_backtest(intents, candles_ltf, config) -> BacktestReport`
- `src/backtesting/metrics.py`
  - cálculo de métricas agregadas
- `src/cli/strategy_commands.py` (o extensión en CLI existente)
  - comando para validar estrategia
  - comando para correr backtest
- `docs/strategy_quickstart.md`
  - guía corta y operativa de uso

### 3) Flujo funcional
1. Cargar `StrategyDefinition` desde archivo validado.
2. Generar eventos HTF/LTF usando capa existente de `analyze*`.
3. Evaluar reglas declarativas para producir `TradeIntent`.
4. Simular intents sobre velas históricas y producir `TradeResult`.
5. Agregar métricas y devolver `BacktestReport`.
6. Mostrar reporte por CLI y/o exportar a JSON/CSV.

### 4) Usabilidad/entendimiento
- Entregar quickstart con ejemplo mínimo end-to-end.
- Proveer un archivo de estrategia ejemplo (`strategies/examples/*.yaml`).
- Errores de validación de estrategia deben ser explícitos y accionables.

## Data Impact
1. Sin cambios de schema obligatorios en esta fase.
2. Resultados de backtest pueden mantenerse in-memory y opcionalmente exportarse a archivos.
3. Se introducen contratos de datos nuevos (`StrategyDefinition`, `TradeIntent`, `TradeResult`, `BacktestReport`).

## Edge Cases
1. Estrategia inválida (schema): abortar con errores detallados por campo.
2. No hay eventos HTF/LTF para el periodo: reporte válido con `0 trades`.
3. Señal sin fill por reglas de ejecución: registrar `intent` descartado en metadata.
4. Solapamiento de señales opuestas: regla explícita de prioridad o descarte.
5. Gap de precio que salta SL/TP: definir política de fill conservadora y documentarla.
6. Datos insuficientes para ATR/condiciones: no emitir señal en esos segmentos.

## Acceptance Criteria
1. Existe un formato de estrategia declarativa validable y un parser/validador asociado.
2. Se puede ejecutar un backtest histórico end-to-end desde CLI con una estrategia definida por archivo.
3. El flujo HTF->LTF queda implementado y trazable en `TradeIntent.meta`.
4. Se genera `BacktestReport` con métricas mínimas y listado de trades.
5. Se provee documentación rápida (`quickstart`) para entender y usar el sistema sin leer toda la base de código.
6. Se mantienen separados detección, decisión, simulación y visualización.
