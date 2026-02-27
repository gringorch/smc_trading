# Implementation Plan: SMC Strategy Events Layer

**Date**: 2026-02-27  
**Spec**: [`specs/smc_strategy_events_layer.md`](./smc_strategy_events_layer.md)

## PLAN Structure (mandatory)

### 1. files to modify

1. `specs/smc_strategy_events_layer.md`
   - Consolidar reglas finales aprobadas (sweeps, market state, expiración HTF, defaults ATR).
2. `specs/smc_strategy_events_layer_plan.md`
   - Plan técnico ejecutable por fases.
3. `src/strategy/__init__.py` (nuevo)
4. `src/strategy/events.py` (nuevo)
5. `src/strategy/structure.py` (nuevo)
6. `src/strategy/imbalance.py` (nuevo)
7. `src/strategy/context.py` (nuevo)
8. `src/strategy/service.py` (nuevo)
9. `src/charting/plot_overlays.py` (nuevo)
10. `src/charting/service.py` (existente, integración de overlays)
11. `tests/unit/test_strategy_structure.py` (nuevo)
12. `tests/unit/test_strategy_imbalance.py` (nuevo)
13. `tests/unit/test_strategy_context.py` (nuevo)
14. `tests/unit/test_strategy_service.py` (nuevo)
15. `CHANGELOG.md` (existente)

### 2. order of changes

#### Fase 1 — Contrato base y configuración
1. Crear `events.py` con:
   - enums `EventKind`, `Direction`, `MarketState`.
   - dataclass `Event`.
   - dataclasses de configuración (`StrategyConfig`, `HTFConfig`, `LTFConfig`) con defaults ATR cerrados por timeframe.
2. Agregar tests unitarios del contrato de `Event` y defaults de config.

#### Fase 2 — Estructura (ST + HTF sweeps)
3. Implementar `detect_pivots(df, L)` con confirmación no repaint.
4. Implementar `detect_bos_choch(...)` close-based + validación `min_break_atr * ATR`.
5. Implementar `detect_sweeps(...)` con fórmula exacta aprobada:
   - wick mínimo `0.10*ATR`,
   - reclaim por close con tolerancia `0.05*ATR`,
   - confirmación en misma vela o siguiente,
   - invalidación por cierres sostenidos de continuación.
6. Tests unitarios:
   - pivots no repaint,
   - BOS/CHOCH por close,
   - sweep high/sweep low con reclaim válido,
   - no-sweep cuando hay continuation break.

#### Fase 3 — Imbalance y contexto
7. Implementar `detect_fvg(...)` regla 3 velas + filtro `min_fvg_atr * ATR`.
8. Implementar `detect_ifvg(...)` por invalidación con close y referencia al FVG origen.
9. Implementar `build_fib_context(...)` para range + premium/discount.
10. Implementar `compute_market_state_1h(...)` con tabla determinística:
    - `NEUTRAL -> TREND_*` por BOS,
    - reversals por CHOCH,
    - entrada/salida de `CORRECTION_*` por fib retrace >=/<= 0.5 y BOS de reanudación.
11. Tests unitarios de FVG/IFVG y market state.

#### Fase 4 — Orquestación single-TF + overlays
12. Implementar `analyze(...)` en `service.py` (pipeline ST, retorno eventos + chart).
13. Implementar `plot_overlays.py` consumiendo solo `Event`:
    - BOS/CHOCH,
    - SWEEP,
    - FVG/IFVG,
    - Fib zones.
14. Integrar overlays en `src/charting/service.py` sin mover lógica al plot.
15. Tests de servicio (wiring + contrato de salida).

#### Fase 5 — Multi-TF y proyección HTF→LTF
16. Implementar `analyze_multi_tf(...)`:
    - detectar POIs HTF (FVG + sweeps + discount zones),
    - detectar IFVG LTF,
    - linkear IFVG↔POI por solape o distancia ATR,
    - devolver reporte de conteos + eventos linkeados.
17. Implementar expiración visual HTF en LTF con default:
    - `zone_expiry_mode="mitigation_or_max_age"`,
    - `mitigation_mode="touch"`,
    - `end_ts=min(mitigated_ts, created_ts+max_age_time)`.
18. Aplicar edades máximas por HTF:
    - 4H: 20 barras,
    - 1H: 48 barras,
    - 15m: 96 barras.
19. Tests de linkeo y expiración de zonas.

#### Fase 6 — Adaptive HTF→LTF
20. Implementar `analyze_adaptive(...)`:
    - construir HTF (4H/1H/15m),
    - derivar `market_state` en 1H,
    - seleccionar LTF:
      - `TREND_BULL/TREND_BEAR => 1m`,
      - `CORRECTION_* / NEUTRAL => 3m o 5m`.
    - filtrar IFVG por `discount zone` HTF + `trigger_max_distance_to_poi_atr`.
21. Aplicar filtros extra en 1m:
    - `require_displacement_body=True`,
    - `min_body_atr_1m=0.20`.
22. Tests unitarios del selector adaptativo y filtros.

#### Fase 7 — Cierre
23. Actualizar `CHANGELOG.md`.
24. Ejecutar tests nuevos + regresión de tests existentes.
25. Verificar no haya cambios fuera de alcance.

### 3. migration strategy

1. No hay cambios de schema ni migraciones.
2. Entrega incremental por capas:
   - contrato + config,
   - detectores,
   - orquestación ST,
   - MTF/adaptive.
3. Compatibilidad:
   - no afecta ingesta/DB,
   - la capa estrategia consume DataFrames existentes.
4. Rollout:
   - habilitar primero por servicio Python,
   - exponer CLI solo tras estabilizar tests.

### 4. test strategy

1. Unit tests deterministas con fixtures OHLCV sintéticos.
2. Cobertura mínima obligatoria:
   - pivots no repaint,
   - BOS/CHOCH close-based con umbral ATR,
   - sweeps HTF (caso válido y caso invalidado),
   - FVG/IFVG,
   - market_state transitions,
   - selección adaptativa de LTF.
3. Tests smoke de overlays (render sin excepción usando eventos precomputados).
4. Criterio de pase:
   - tests nuevos en verde,
   - sin regresiones.

### 5. rollback strategy

1. Revert por commit (sin impacto de datos).
2. Si falla MTF/adaptive:
   - mantener `analyze` ST activo,
   - feature flag interno para desactivar rutas MTF/adaptive.
3. Si falla plotting:
   - mantener detección,
   - devolver eventos sin render.
4. Si falla integración CLI:
   - mantener API de servicio Python como vía primaria.
