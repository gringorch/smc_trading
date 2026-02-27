## Context
Se requiere incorporar una capa de estrategia para SMC sobre la infraestructura ya existente (OHLCV en DB, DataFrame y candlestick chart) para detectar y graficar eventos sin ejecutar trades todavía.

El objetivo inmediato es producir eventos con reglas explícitas, visualizarlos como overlays y dejar un contrato estable para consumo posterior del backtester.

## Requirements
1. Implementar detectores desacoplados por dominio:
   - `structure.py`: pivots (fractal no repaint), BOS, CHOCH y sweeps HTF.
   - `imbalance.py`: FVG e IFVG.
   - `context.py`: Fibonacci premium/discount + market state 1H.
   - `events.py`: `Event` + tipos de evento.
   - `plot_overlays.py`: render de overlays sin lógica de detección.
2. Definir pivots con fractal `L` (default `L=2`):
   - Swing high en `i` si `high[i]` es estrictamente mayor que `high[i-L:i+L]` excluyendo `i`.
   - Swing low en `i` si `low[i]` es estrictamente menor que `low[i-L:i+L]` excluyendo `i`.
   - Confirmación del pivot luego de `L` velas posteriores (no repaint).
3. Definir BOS por cierre (`close`) únicamente:
   - Bull BOS: `close` rompe por encima del último swing high confirmado.
   - Bear BOS: `close` rompe por debajo del último swing low confirmado.
   - Validación por desplazamiento: `abs(close - level) >= min_break_atr * ATR(tf)`.
   - Guardar: nivel roto, id de swing asociado, timestamp de ruptura y dirección.
4. Definir CHOCH con estado de tendencia basado en BOS:
   - `trend="bull"` tras bull BOS, `trend="bear"` tras bear BOS.
   - Si `trend="bull"` y hay cierre bajo último swing low confirmado => CHOCH bear.
   - Si `trend="bear"` y hay cierre sobre último swing high confirmado => CHOCH bull.
   - CHOCH usa el mismo filtro `min_break_atr`.
   - Guardar: trend previo, nivel roto, pivot asociado, timestamp y dirección.
5. Definir sweeps HTF (liquidity sweep / stop run) contra pivot confirmado más reciente (`sweep_lookback_pivots=1`):
   - Inputs: pivots confirmados + ATR(14) del HTF.
   - Parámetros default:
     - `min_sweep_wick = 0.10 * ATR_HTF`
     - `max_reclaim_distance = 0.05 * ATR_HTF`
     - `confirm_mode = "close_reclaim"`
     - `confirm_within_bars = 1`
     - `invalidate_if_breaks = True`
   - Sweep High (bear):
     - `high[i] > H_pivot + min_sweep_wick`
     - reclaim por close en `i` o `i+1`: `close <= H_pivot + max_reclaim_distance`
     - si `close[i]` y `close[i+1]` quedan arriba de `H_pivot + max_reclaim_distance` => no sweep (ruptura/continuación)
     - salida `Event(kind="SWEEP_HIGH", direction="bear")` con `ts_confirm`, `level`, `wick_excess` y metadata.
   - Sweep Low (bull):
     - `low[i] < L_pivot - min_sweep_wick`
     - reclaim por close en `i` o `i+1`: `close >= L_pivot - max_reclaim_distance`
     - cierres sostenidos por debajo => no sweep
     - salida `Event(kind="SWEEP_LOW", direction="bull")`.
6. Definir FVG de 3 velas:
   - Bull FVG en `i` si `high[i-2] < low[i]`, zona `[high[i-2], low[i]]`.
   - Bear FVG en `i` si `low[i-2] > high[i]`, zona `[high[i], low[i-2]]`.
   - Filtro mínimo: `zone_height >= min_fvg_atr * ATR(tf)`.
   - Guardar: `start_ts` (`i-2`), `ts_event` (`i`), `price_low/high`, dirección.
7. Definir IFVG por invalidación de cierre:
   - Bull FVG invalida si luego `close < price_low` => IFVG bear.
   - Bear FVG invalida si luego `close > price_high` => IFVG bull.
   - Guardar referencia al FVG original y timestamp de inversión.
8. Definir contexto Fibonacci + premium/discount:
   - Range por defecto: último swing high y swing low confirmados que encierren precio actual.
   - Si no existe, usar último par de swings opuestos confirmados.
   - Calcular fib 0..1 del range.
   - Bull range (`low->high`): discount `[0.5, 1.0]`, premium `[0.0, 0.5]`.
   - Bear range: invertir definición de zonas.
   - Guardar eventos de zona con límites de precio.
9. Definir `market_state` 1H con tabla determinística:
   - Estados: `NEUTRAL`, `TREND_BULL`, `TREND_BEAR`, `CORRECTION_BULL`, `CORRECTION_BEAR`.
   - Inicialización: `NEUTRAL` hasta primer BOS.
   - Transiciones base:
     - `NEUTRAL + BOS_BULL => TREND_BULL`
     - `NEUTRAL + BOS_BEAR => TREND_BEAR`
     - `TREND_BULL + CHOCH_BEAR => TREND_BEAR`
     - `TREND_BEAR + CHOCH_BULL => TREND_BULL`
     - `TREND_BULL + BOS_BULL => TREND_BULL`
     - `TREND_BEAR + BOS_BEAR => TREND_BEAR`
   - Corrección:
     - `TREND_BULL` entra en `CORRECTION_BULL` si `fib_retrace >= 0.5` sin `CHOCH_BEAR`.
     - `TREND_BEAR` entra en `CORRECTION_BEAR` si `fib_retrace <= 0.5` sin `CHOCH_BULL`.
     - `CORRECTION_BULL + BOS_BULL => TREND_BULL`.
     - `CORRECTION_BEAR + BOS_BEAR => TREND_BEAR`.
10. Contrato unificado de salida:
    - Cada detector retorna `list[Event]`.
    - `Event` incluye: `kind`, `direction`, `ts` (o `start_ts/end_ts`), `price_low/high` (o `price`) y `meta: dict`.
11. Overlays de plot desde eventos:
    - BOS/CHOCH: línea horizontal en nivel roto + etiqueta en timestamp de ruptura.
    - FVG: rectángulo entre `price_low/high` desde `ts_event` hasta mitigación o expiración.
    - IFVG: marcador visual sobre FVG original (borde/etiqueta) en timestamp de inversión.
    - Sweep: marcador/etiqueta en `ts_confirm` sobre nivel sweepeado.
    - Fib zones: bandas horizontales del range actual con labels premium/discount.
12. Expiración visual de zonas HTF proyectadas en LTF (default recomendado):
    - Política: mitigación + edad máxima (`zone_expiry_mode = "mitigation_or_max_age"`).
    - Mitigación default: `mitigation_mode = "touch"`.
      - Bull zone mitigada si `low <= zone_high`.
      - Bear zone mitigada si `high >= zone_low`.
    - `end_ts = min(mitigated_ts, created_ts + max_age_time)`.
    - Defaults de edad máxima:
      - 4H: `age_max_bars_htf = 20`
      - 1H: `age_max_bars_htf = 48`
      - 15m: `age_max_bars_htf = 96`
13. Exponer `analyze(symbol, timeframe, candles)` que retorne:
    - lista de eventos detectados,
    - chart con overlays.
14. Extender con análisis adaptativo multi-timeframe:
    - `StrategyConfig` con sub-configs:
      - `config_htf`: `pivots_L`, `min_break_atr`, `min_fvg_atr`, `discount_threshold`, `poi_merge_distance`, `poi_max_age`, `sweep_*`.
      - `config_ltf`: `pivots_L`, `min_break_atr`, `min_fvg_atr`, `ifvg_confirm_mode`, `ifvg_min_penetration`, `trigger_max_distance_to_poi_atr`.
    - `analyze_adaptive(symbol, htf_list=["15m","1h","4h"], ltf_default in {"3m","5m"}, ltf_trend="1m")`:
      1) construye eventos HTF (estructura, FVG, sweeps, fib discount) en 4H/1H/15m,
      2) determina `market_state` usando 1H,
      3) selecciona LTF (trend=>1m, correction/neutral=>3m o 5m configurable),
      4) busca IFVG LTF solo dentro de discount HTF y distancia `<= trigger_max_distance_to_poi_atr * ATR_LTF`,
      5) grafica panel LTF con IFVG + POIs HTF proyectados,
      6) devuelve reporte con `market_state`, timeframe elegido y enlaces HTF↔LTF.
    - `analyze_multi_tf(symbol, htf, ltf, candles_htf, candles_ltf)`:
      1) detecta POIs/contexto HTF (FVG zones, sweeps, discount zones),
      2) detecta IFVG LTF,
      3) linkea IFVG↔POI HTF por solape o distancia `<= threshold`,
      4) grafica panel LTF con overlays IFVG + bandas HTF proyectadas,
      5) devuelve reporte de conteos + lista de eventos linkeados.
15. Defaults iniciales ATR por timeframe:
    - `min_break_atr`: 4H=0.30, 1H=0.25, 15m=0.20, 5m=0.15, 3m/4m=0.12, 1m=0.20.
    - `min_fvg_atr`: 4H=0.25, 1H=0.20, 15m=0.15, 5m=0.12, 3m/4m=0.10, 1m=0.15.
    - `trigger_max_distance_to_poi_atr`: 3m/5m=0.60, 1m=0.40.
    - Filtro extra en 1m: `require_displacement_body=True` y `min_body_atr_1m=0.20`.
16. Agregar tests unitarios mínimos:
    - pivots no repaint,
    - BOS/CHOCH con breaks por close,
    - sweep high/low con reclaim,
    - FVG por regla de 3 velas,
    - IFVG por invalidación close,
    - transición de `market_state`.

## Non-goals
1. Ejecución de órdenes, gestión de riesgo o simulación de PnL.
2. Motor de backtesting completo (solo contrato de eventos listo para integración).
3. Cambios de esquema DB o API externa.
4. Mezclar lógica de detección dentro del plotting.

## Technical Design
### Módulos y responsabilidades
- `src/strategy/events.py`
  - `EventKind` (enum), `Direction` (enum), `MarketState` (enum), `Event` (dataclass), y helpers de serialización.
- `src/strategy/structure.py`
  - `detect_pivots(df, L=2) -> list[Event]`
  - `detect_bos_choch(df, pivots: list[Event], atr, min_break_atr) -> list[Event]`
  - `detect_sweeps(df, pivots: list[Event], atr, cfg) -> list[Event]`
- `src/strategy/imbalance.py`
  - `detect_fvg(df, atr, min_fvg_atr) -> list[Event]`
  - `detect_ifvg(df, fvg_events: list[Event], confirm_mode="close") -> list[Event]`
- `src/strategy/context.py`
  - `build_fib_context(df, pivots: list[Event], discount_threshold: float = 0.5) -> list[Event]`
  - `compute_market_state_1h(events_1h: list[Event], fib_retrace: float | None) -> MarketState`
- `src/charting/plot_overlays.py`
  - `apply_overlays(ax, events: list[Event], df, config) -> None`
- `src/strategy/service.py`
  - `analyze(symbol, timeframe, candles, config=None) -> AnalysisResult`
  - `analyze_multi_tf(symbol, htf, ltf, candles_htf, candles_ltf, config) -> MultiTFReport`
  - `analyze_adaptive(symbol, htf_list, ltf_default, ltf_trend, config) -> AdaptiveReport`

### Flujo de alto nivel
1. Cargar OHLCV a DataFrame por timeframe solicitado.
2. Calcular ATR(14) por timeframe para filtros y calibración.
3. Ejecutar detectores en orden: pivots -> BOS/CHOCH -> sweeps -> FVG -> IFVG -> fib context -> market_state.
4. Normalizar todo a `Event` y agregar metadata para linkeo posterior.
5. Pasar eventos al módulo de plotting para overlays.
6. Devolver `AnalysisResult`/`MultiTFReport`/`AdaptiveReport`.

## Data Impact
1. No hay cambios de schema, migraciones ni nuevos contratos de persistencia obligatorios en esta fase.
2. Los eventos se generan en memoria (listas tipadas) y quedan listos para futura persistencia/consumo por backtester.

## Edge Cases
1. Serie con menos de `2L+1` velas: no hay pivots confirmables.
2. Igualdades en extremos (`==`) no califican como fractal (regla estricta > / <).
3. Falta de swings opuestos para range fib: emitir contexto vacío.
4. Múltiples breaks en velas consecutivas sobre mismo nivel: deduplicar por swing roto.
5. Sweep sin reclaim en ventana permitida: descartar como sweep.
6. FVG nunca mitigado dentro de ventana visible: expirar por `max_age_time`.
7. HTF y LTF desalineados en timestamps: linkeo por solape de precio y tolerancia configurable.

## Acceptance Criteria
1. `analyze(symbol, timeframe, candles)` retorna eventos tipados y chart con overlays de BOS/CHOCH/SWEEP/FVG/IFVG/Fib según reglas definidas.
2. Detectores devuelven `list[Event]` y no contienen lógica de render.
3. Plotting consume solo eventos y no recalcula señales.
4. Tests unitarios cubren pivots no repaint, BOS/CHOCH close-based, sweep reclaim, FVG 3-velas, IFVG invalidación close y market_state.
5. `analyze_multi_tf(...)` retorna reporte con conteos y eventos linkeados HTF↔LTF.
6. `analyze_adaptive(...)` selecciona LTF en función de `market_state` y filtra IFVG por discount+distancia a POI HTF.
