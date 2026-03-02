# Implementation Plan: Trading Sessions + Risk-based Position Sizing

**Date**: 2026-02-27  
**Spec**: [`specs/strategy_sessions_risk_sizing.md`](./strategy_sessions_risk_sizing.md)

## PLAN Structure (mandatory)

### 1. files to modify

1. `specs/strategy_sessions_risk_sizing.md`
   - Mantener decisiones finales trazadas (UTC, lookup activo, skip, equity dinámica).
2. `specs/strategy_sessions_risk_sizing_plan.md` (nuevo)
   - Plan técnico ejecutable por fases.
3. `src/strategy/definitions.py`
   - Extender schema declarativo con `trading_sessions` y `risk_sizing`.
4. `src/strategy/engine.py`
   - Filtrar triggers por sesiones UTC y calcular `qty` por riesgo.
5. `src/backtesting/simulator.py`
   - Usar `intent.qty` y actualizar equity trade a trade para sizing dinámico.
6. `src/backtesting/metrics.py`
   - Incorporar métricas complementarias de sizing (opcional en summary/meta).
7. `src/ingestion/repositories/assets_repository.py` (o repositorio nuevo en `src/strategy/`)
   - Lookup de contrato por activo (`contract_point_value`).
8. `src/db/models/` + `alembic/versions/` (si se crea tabla nueva)
   - Modelo/migración para tabla de especificaciones de contrato por activo.
9. `strategies/examples/htf_ltf_ifvg.yaml`
   - Extender ejemplo con sesiones y bloque `risk_sizing`.
10. `docs/strategy_quickstart.md`
   - Documentar sesiones, sizing y ejemplo de cálculo de qty.
11. `tests/unit/test_strategy_definitions.py`
   - Validar parse de sesiones y risk config.
12. `tests/unit/test_strategy_engine.py`
   - Test de filtro horario y qty por riesgo.
13. `tests/unit/test_backtesting_simulator.py`
   - Test de equity dinámica y qty por intent.
14. `tests/unit/test_backtesting_metrics.py`
   - Ajustes por nuevas salidas de sizing.
15. `CHANGELOG.md`
   - Registrar feature de sesiones + risk sizing.

### 2. order of changes

#### Fase 1 — Contratos y validación
1. Extender dataclasses de estrategia (`TradingSession`, `RiskSizingConfig`).
2. Validar formato de sesiones UTC y weekdays.
3. Validar límites de riesgo (`risk_percent`, `qty_step`, `min/max_qty`, `min_qty_policy=skip`).
4. Tests unitarios de parsing/validación.

#### Fase 2 — Lookup de activo para `contract_point_value`
5. Definir acceso a `contract_point_value` por símbolo/asset_id.
6. Si no existe estructura actual, agregar tabla dedicada + migración.
7. Implementar fallback/error funcional cuando no hay lookup válido.
8. Tests unitarios de repositorio/lookup.

#### Fase 3 — Engine (sesiones + sizing)
9. Implementar filtro de triggers por sesión UTC.
10. Implementar cálculo de `qty_raw` por fórmula de riesgo.
11. Aplicar redondeo (`qty_step`) + límites (`min/max`) + política `skip`.
12. Incluir metadata de trazabilidad (`risk_amount`, `price_risk`, `qty_raw`, `qty_final`, sesión).
13. Tests unitarios de casos dentro/fuera de sesión y sizing.

#### Fase 4 — Simulator con equity dinámica
14. Consumir `intent.qty` para PnL por trade.
15. Actualizar equity tras cada trade y recalcular riesgo para el siguiente sizing.
16. Mantener fallback de cantidad solo para intents legacy sin `qty`.
17. Tests unitarios de secuencia multi-trade verificando actualización de equity.

#### Fase 5 — Docs + ejemplo
18. Actualizar YAML ejemplo con `trading_sessions` y `risk_sizing`.
19. Actualizar quickstart con flujo operativo y ejemplo numérico (6000 USD, 1% riesgo => 60 USD).
20. Actualizar `CHANGELOG.md`.

### 3. migration strategy

1. Migración de DB condicional:
   - si no hay fuente de `contract_point_value`, agregar tabla dedicada y poblarla por activo.
2. Compatibilidad hacia atrás:
   - estrategias sin `trading_sessions` => comportamiento actual (sin filtro horario).
   - estrategias sin `risk_sizing` => bloquear ejecución de backtest nuevo o fallback explícito documentado.
3. Rollout recomendado:
   - primero contratos + engine,
   - luego lookup + simulator dinámico,
   - por último docs/ejemplos.

### 4. test strategy

1. Unit tests de validación de strategy file:
   - sesiones válidas/inválidas,
   - políticas de qty y límites.
2. Unit tests de engine:
   - trigger dentro/fuera de sesión,
   - sizing correcto por fórmula,
   - skip por `min_qty` y por riesgo inválido.
3. Unit tests de simulator:
   - PnL usando `intent.qty`,
   - equity dinámica trade a trade.
4. Tests de regresión:
   - no romper parse/evaluación existente.

### 5. rollback strategy

1. Revert por commit sin impacto de datos históricos de trades.
2. Si falla lookup por activo:
   - desactivar temporalmente sizing dinámico y bloquear ejecución con error explícito.
3. Si falla filtro de sesiones:
   - fallback temporal a comportamiento sin filtro horario.
4. Si falla simulator dinámico:
   - fallback temporal a cantidad fija documentada para no bloquear pruebas internas.
