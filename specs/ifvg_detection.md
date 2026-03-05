## Context
Queremos incorporar una segunda herramienta “standalone” para detectar **Inverse Fair Value Gaps (iFVG / IFVG)** en timeframes bajos (1m–5m) y emitir **señales accionables** (con parámetros de orden) que luego puedan usarse como **gatillo de ejecución**.

La idea operativa (SMC) que queremos modelar es:
1) existe un FVG LTF reciente,
2) aparece un **evento singular/fuerte** que “cierra” ese FVG (en el sentido de llenarlo) y produce una **inversión**,
3) se emite una señal para ejecutar una orden con SL/TP calculables.

Nota: conceptos como **POI (ej. FVG HTF mitigado)**, **sweep/toma de liquidez** y **bias HTF** se van a integrar como *gates/filtros* en iteraciones posteriores. En esta iteración deben quedar como **opcionales** para no bloquear señales por ausencia de esos componentes.

## Requirements
### Inputs
- Fuente de datos: velas 1m persistidas en DB (ya existente).
- Timeframes:
  - `ltf_timeframe`: uno de `5m`, `4m`, `3m`, `2m`, `1m`.
  - `htf_timeframe` (opcional, futuro gate): mínimo `15m` (M15) o superior.
- `bias` HTF (opcional, futuro gate):
  - `htf_bias`: `bull` o `bear` (si se provee).
  - Nota: la forma de calcular `htf_bias` queda fuera de este feature; inicialmente puede pasarse como parámetro manual o omitirse.
- Filtro de tamaño mínimo del gap origen:
  - `min_gap_size` (default `0.00005`, unidades de precio).

### Definiciones (explícitas y testeables)
#### FVG (reuso)
- Usamos el detector existente de FVG (3 velas):
  - Bullish FVG: `high[i] < low[i+2]` => gap `(high[i], low[i+2])`
  - Bearish FVG: `low[i] > high[i+2]` => gap `(high[i+2], low[i])`

#### Mitigación HTF (para POI)
- Un FVG HTF se considera **mitigado** si, después de formarse, una vela HTF “entra” al gap según `mitigation_rule`:
  - `wick`: bull si `low <= gap_high`, bear si `high >= gap_low`
  - `close`: bull si `close <= gap_high`, bear si `close >= gap_low`

#### POI (zona de interés) basada en FVG HTF mitigado
- Un FVG HTF mitigado produce una POI activa con límites:
  - `poi_low = gap_low`, `poi_high = gap_high`
- Una POI se considera “en juego” para LTF si se cumple **alguna** de estas condiciones (configurable):
  - `poi_activation = price_inside`: la vela LTF actual tiene `low <= poi_high` y `high >= poi_low` (intersección).
  - `poi_activation = since_mitigation`: estamos dentro de una ventana `poi_active_bars_after_mitigation` (en HTF) desde `mitigated_at`.

Nota: en esta iteración `poi_required` debe default a `false` y el detector IFVG debe funcionar sin POI.

#### Liquidity sweep (toma de liquidez) en LTF
- Configurable por `sweep_lookback_bars` y `sweep_required`.
- Buy-side sweep (para reversión bajista):
  - `bar.high > max(high[lookback])` y `bar.close <= max(high[lookback])`
- Sell-side sweep (para reversión alcista):
  - `bar.low < min(low[lookback])` y `bar.close >= min(low[lookback])`

Nota: en esta iteración `sweep_required` debe default a `false` (no bloquear señales si no hay sweep).

#### IFVG “singular” (evento de inversión + desplazamiento)
El IFVG que buscamos es un evento que ocurre **casi inmediatamente** después de un FVG LTF reciente y representa su **inversión** (fallo del movimiento y reversión).

- Identificamos un **FVG LTF candidato** formado recientemente (configurable):
  - `max_bars_from_fvg_formation_to_inversion` (p. ej. 1–5).
- Definimos el **cierre del FVG** (fill por cierre) con un umbral configurable:
  - `inversion_fill_pct` en `[0.1, 1.0]` (default `1.0`).
  - Intuición: `1.0` significa que el cierre “llenó” el 100% del gap (lo cruzó completo); valores como `0.5` o `0.7` permiten cierres parciales profundos.
  - Para un FVG bull (gap debajo): el fill por cierre en una vela se define como:
    - `fill = clamp((gap_high - close) / (gap_high - gap_low), 0..1)` si `close` está entre `gap_low` y `gap_high`,
    - si `close < gap_low` entonces `fill = 1`.
    - Hay inversión bajista si `fill >= inversion_fill_pct` **y además** `close <= (gap_high - inversion_fill_pct * (gap_high-gap_low)) - inversion_buffer`.
  - Para un FVG bear (gap arriba): el fill por cierre se define como:
    - `fill = clamp((close - gap_low) / (gap_high - gap_low), 0..1)` si `close` está entre `gap_low` y `gap_high`,
    - si `close > gap_high` entonces `fill = 1`.
    - Hay inversión alcista si `fill >= inversion_fill_pct` **y además** `close >= (gap_low + inversion_fill_pct * (gap_high-gap_low)) + inversion_buffer`.
- Exigimos que la vela de inversión sea “notoria/fuerte” (displacement), configurable:
  - `displacement_rule = body_atr`: `abs(close-open) >= displacement_body_atr_mult * ATR(n)`
  - o `displacement_rule = body_pct_range`: `abs(close-open) / (high-low) >= displacement_min_body_pct` (default `0.7`)
- Opcionalmente, exigimos `sweep_required = true` y que el sweep ocurra:
  - en la vela inmediatamente anterior, o
  - dentro de `max_bars_between_sweep_and_inversion`.

### Señal de trading (output)
Cuando se cumple un IFVG event y los filtros, se emite una señal:
- `side`: `buy` (inversión alcista) o `sell` (inversión bajista)
- `triggered_at`: timestamp de la vela LTF de inversión (cierre confirmado)
- `ltf_timeframe`, `htf_timeframe`, `symbol`
- `poi`: límites de la POI HTF que habilitó la señal (si aplica)
- `origin_fvg`: límites y metadata del FVG LTF invertido
- `reason`: lista de flags (ej. `inversion_close`, `displacement_ok`, `sweep_ok`, `poi_ok`, `bias_ok`)

#### Parámetros de orden (para ejecución)
La señal debe incluir niveles calculables, con modelos configurables:
- `entry_model`:
  - `market_on_close` (default): entrada a mercado al cierre del IFVG event
  - `limit_retest`: limit en un nivel del gap del FVG invertido (`gap_mid`, `gap_near_edge`, `gap_far_edge`)
- `stop_model`:
  - `beyond_sweep_extreme`: SL más allá del extremo del sweep + `sl_buffer`
  - `beyond_gap_edge`: SL más allá del borde relevante del gap + `sl_buffer`
- `tp_model`:
  - `rr`: TP = `entry + side * rr * (entry - stop)` (RR configurable)
  - (otros modelos quedan fuera por ahora)

Además:
- `one_signal_per_origin_fvg`: evitar duplicados por FVG invertido
- `cooldown_bars`: enfriamiento global de señales

### Filtros obligatorios
- No hay filtros obligatorios más allá de la definición de IFVG.
- Si se provee `htf_bias`, puede activarse un filtro opcional `bias_required=true`:
  - `htf_bias=bull` => solo `buy`
  - `htf_bias=bear` => solo `sell`
- POI es opcional en esta iteración:
  - `poi_required=false` (default). Si se activa, debe existir una POI activa según `poi_activation`.

## Non-goals
- No ejecución real de órdenes (broker/exchange).
- No “bias engine” automático (se recibe como input).
- No detección completa de estructura (BOS/CHOCH) en esta iteración.
- No cambios de esquema de DB ni migraciones.

## Technical Design
### Flujo
1) Obtener velas 1m de DB y resamplear a `ltf_timeframe`.
2) Detectar FVGs en LTF.
3) En LTF, para cada FVG candidato reciente:
   - validar inversión por cierre con `inversion_fill_pct` + `inversion_buffer`,
   - validar displacement,
   - (opcional) validar sweep,
   - (opcional) validar POI/bias si están habilitados,
   - generar señal + niveles de orden (por defecto `market_on_close`).
4) Exponer una interfaz consumible (CLI) con output principal en **HTML** (gráfico + listado de señales debajo), igual al patrón de `fvg-report`.
   - El reporte debe incluir metadata/config usada para detección.
   - El listado/tablas debe incluir `side`, `triggered_at`, `entry`, `stop`, `tp`, `origin_fvg`, `reason`.

### Componentes y responsabilidades (tentativo)
- `indicators/ifvg.py`: lógica pura (sin I/O) para detectar IFVG events + señales.
- `charting/service.py`: reuso para obtener barras resampleadas.
- `reporting/ifvg_report.py`: builder HTML para reporte IFVG.
- `cli`: comando `ifvg-report` para generar reporte HTML.

## Data Impact
- Sin cambios en DB.
- Output principal: archivo HTML (`reports/ifvg_report.html` por default).
- (Opcional futuro) JSON/stdout para integración con ejecución automática.

## Edge Cases
- POIs HTF múltiples / solapadas: regla de selección (primera que intersecta vs la más cercana) debe ser explícita.
- Barras con rango 0 (high==low): cuidado con `body_pct_range`.
- ATR no disponible en las primeras N velas: definir warmup (no señal hasta tener ATR).
- Sweep con lookback demasiado chico/grande: posibles falsos positivos.
- Señales duplicadas cuando el precio oscila alrededor del borde: `one_signal_per_origin_fvg` y `cooldown_bars`.

## Acceptance Criteria
- Dado un set sintético de velas:
  - se detecta al menos 1 caso alcista y 1 bajista de IFVG por cierre + displacement,
  - el umbral `inversion_fill_pct` cambia el comportamiento (ej. un caso que entra con 0.7 pero no con 1.0),
  - si `entry_model=market_on_close`, la señal calcula `entry` al cierre de la vela IFVG,
  - el cálculo de `stop/tp` respeta los modelos configurados.
- Unit tests cubren:
  - inversión por cierre con `inversion_fill_pct` (1.0 vs <1.0),
  - displacement filter,
  - (opcional) gating por bias si `bias_required=true`,
  - dedupe/cooldown,
  - generación de reporte HTML (tabla/listado IFVG).
