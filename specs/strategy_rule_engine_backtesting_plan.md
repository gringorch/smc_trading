# Implementation Plan: Strategy Rule Engine + Historical Backtesting

**Date**: 2026-02-27  
**Spec**: [`specs/strategy_rule_engine_backtesting.md`](./strategy_rule_engine_backtesting.md)

## PLAN Structure (mandatory)

### 1. files to modify

1. `specs/strategy_rule_engine_backtesting_plan.md` (nuevo)
   - Plan técnico incremental y ejecutable.
2. `src/strategy/definitions.py` (nuevo)
   - Contratos de estrategia declarativa + loader/validator YAML/JSON.
3. `src/strategy/engine.py` (nuevo)
   - Evaluación de reglas HTF->LTF y emisión de `TradeIntent`.
4. `src/backtesting/__init__.py` (nuevo)
   - Exposición de API de simulación/reporte.
5. `src/backtesting/simulator.py` (nuevo)
   - Simulación de entradas/salidas y generación de `TradeResult`.
6. `src/backtesting/metrics.py` (nuevo)
   - Métricas agregadas (`win_rate`, `profit_factor`, `max_drawdown`, etc.).
7. `src/cli/strategy_commands.py` (nuevo o integración en `src/cli/ingestion_commands.py`)
   - Comandos para validar estrategia y ejecutar backtest.
8. `src/main.py` / bootstrap CLI (si aplica)
   - Registro de comandos de estrategia.
9. `docs/strategy_quickstart.md` (nuevo)
   - Guía operativa end-to-end para backend developer.
10. `strategies/examples/htf_ltf_ifvg.yaml` (nuevo)
   - Estrategia ejemplo mínima y funcional.
11. `tests/unit/test_strategy_definitions.py` (nuevo)
   - Validación de schema y parsing.
12. `tests/unit/test_strategy_engine.py` (nuevo)
   - Evaluación de reglas declarativas -> intents.
13. `tests/unit/test_backtesting_simulator.py` (nuevo)
   - Simulación de fill/salida y casos de gap/slippage/fees.
14. `tests/unit/test_backtesting_metrics.py` (nuevo)
   - Métricas agregadas.
15. `tests/unit/test_cli_strategy_commands.py` (nuevo)
   - Wiring de CLI (validate/run).
16. `CHANGELOG.md` (existente)
   - Registro de nuevas capacidades de strategy/backtesting.

### 2. order of changes

#### Fase 1 — Contratos y definición declarativa
1. Crear modelos `StrategyDefinition`, `TradeIntent`, `TradeResult`, `BacktestReport`.
2. Definir schema validable para YAML/JSON y mensajes de error accionables.
3. Implementar `load_strategy_definition(path)` con validación estricta.
4. Tests unitarios de parse/validación (casos válidos e inválidos).

#### Fase 2 — Engine de estrategia (sin PnL)
5. Implementar `evaluate_strategy(events_htf, events_ltf, strategy_def)`.
6. Implementar filtros de contexto HTF (state, zona, distancia a POI).
7. Implementar triggers LTF (event kinds + constraints mínimas).
8. Emitir `TradeIntent` con trazabilidad en `meta` (event ids, regla aplicada, timestamps).
9. Tests unitarios del engine con fixtures sintéticos HTF/LTF.

#### Fase 3 — Simulador de backtesting
10. Implementar política base de ejecución (entry/exit) sobre velas históricas.
11. Soportar long/short, sl/tp, fees y slippage configurables.
12. Implementar `exit_reason` normalizado (`tp`, `sl`, `rule_exit`, `eod`, `invalidated`).
13. Tests unitarios de simulación incluyendo edge cases de gaps.

#### Fase 4 — Métricas y reporte
14. Implementar métricas agregadas en módulo dedicado.
15. Construir `BacktestReport` completo (summary + trades + period + strategy_id).
16. Tests unitarios de métricas y consistencia del reporte.

#### Fase 5 — Integración CLI + DX
17. Agregar comando `strategy-validate --file <path>`.
18. Agregar comando `backtest-run --strategy <file> --symbol --from --to --htf --ltf`.
19. Formato de salida legible por consola + opción export JSON/CSV.
20. Tests de CLI con dobles/mocks.

#### Fase 6 — Documentación de uso simple
21. Crear `docs/strategy_quickstart.md` con:
   - arquitectura conceptual (eventos -> intents -> trades),
   - ejemplo de estrategia,
   - comandos reales para validar y correr,
   - guía para interpretar resultados.
22. Agregar estrategia ejemplo en `strategies/examples/`.
23. Actualizar `CHANGELOG.md`.

### 3. migration strategy

1. No hay migraciones de DB.
2. Rollout incremental:
   - primero definición + engine (sin simulator),
   - luego simulator + métricas,
   - finalmente CLI + docs.
3. Compatibilidad:
   - mantener `analyze`, `analyze_multi_tf`, `analyze_adaptive` como proveedores de eventos.
4. Backward compatibility:
   - no romper comandos CLI existentes de ingesta/charting.

### 4. test strategy

1. Unit tests por capa:
   - schema/definitions,
   - engine declarativo,
   - simulator,
   - metrics,
   - CLI.
2. Fixtures sintéticos deterministas para evitar dependencia de DB/red.
3. Pruebas de regresión mínimas sobre capa de eventos existente.
4. Criterio de pase:
   - 100% tests nuevos en verde,
   - sin regresiones en tests existentes.

### 5. rollback strategy

1. Revert por commit (sin impacto de datos persistidos).
2. Si falla simulator:
   - dejar habilitado solo `strategy-validate` y engine de intents.
3. Si falla CLI:
   - mantener API Python (`load_strategy_definition`, `evaluate_strategy`, `run_backtest`).
4. Si falla métricas:
   - mantener ejecución de trades con reporte mínimo y desactivar métricas avanzadas.
