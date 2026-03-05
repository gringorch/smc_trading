## Context
Hoy tenemos:
- **FVG** como herramienta principal para identificar *zonas de interés* (ZOI / POI).
- **IFVG** como herramienta principal para *gatillar* (evento accionable en LTF).

Falta una pieza base para poder decidir “antes de operar” si buscamos **long** o **short** según tendencia/sesgo, y para ubicar entradas en zonas de **corrección** (premium/discount) en timeframes mayores (M15 / H1 / H4).

Este feature incorpora un detector de **estructura de mercado** (swings + BOS) y un cálculo explícito de **dealing range + premium/discount** para usar como filtro de sesgo y ubicación. CHOCH queda fuera por ahora para mantenerlo incremental.

## Requirements
### Inputs
- Fuente de datos: velas 1m persistidas en DB (ya existente) + resample a timeframe objetivo.
- `timeframe`: uno de `15m`, `1h`, `4h` (pero la implementación debe aceptar cualquier timeframe soportado por el resampler).
- Parámetros configurables para swings (pivot/fractal):
  - `swing_left`: int >= 1 (default `2`)
  - `swing_right`: int >= 1 (default `2`)
  - Nota: un swing se confirma recién cuando existen `swing_right` velas “a la derecha”.
- Confirmación al final de la serie (tema “última parte del gráfico”):
  - `allow_unconfirmed_last_swing`: bool (default `true`)
  - Si `true`, el detector puede devolver un último swing “tentativo” con `confirmed=false` cuando todavía no hay suficientes velas a la derecha. Esto puede **repaint** si se agregan velas nuevas.
  - Si `false`, el detector solo devuelve swings confirmados.
- Parámetros para BOS:
  - `bos_rule`: fijo a **cierre** (por este requerimiento). Definición: `close > level` (bull) o `close < level` (bear), con desigualdad estricta.
  - `bos_buffer`: Decimal >= 0 (default `0`) para exigir un margen adicional: `close > swing_high + bos_buffer` o `close < swing_low - bos_buffer`.

### Outputs (modelo de datos)
El detector debe devolver:
- Lista ordenada de `SwingPoint`:
  - `kind`: `high` | `low`
  - `timestamp_utc`
  - `price`
  - `bar_index` (índice en la serie resampleada)
  - `left`, `right` (los parámetros efectivos)
  - `confirmed`: bool
- Lista ordenada de `BosEvent` (Break of Structure):
  - `side`: `bull` | `bear`
  - `triggered_at` (timestamp de la vela que rompe)
  - `bar_index`
  - `broken_swing`: referencia (por índice o id) al swing high/low roto
  - `close` (precio de cierre que disparó)
  - `buffer` usado
- Estado “actual” derivado:
  - `current_bias`: `bull` | `bear` | `neutral`
    - `neutral` si aún no hubo un BOS válido.
  - `current_bias_since`: timestamp del último BOS (nullable si `neutral`)
  - `current_dealing_range` (nullable si `neutral` o si no se puede construir):
    - `low`, `high`
    - `mid` (= (low+high)/2)
    - `discount_zone`: `[low, mid]`
    - `premium_zone`: `[mid, high]`
    - `derived_from_bos`: referencia al `BosEvent` que lo origina

### Definiciones (explícitas y testeables)
#### SwingPoint (pivot/fractal)
Para un índice `i` con velas resampleadas:
- Swing High si `high[i]` es estrictamente mayor que todos los `high` de:
  - `i - swing_left ... i - 1` y `i + 1 ... i + swing_right`
- Swing Low si `low[i]` es estrictamente menor que todos los `low` de esos rangos.

Para evitar ambigüedad con empates (equal highs/lows):
- Si hay empate (máximo/mínimo no estricto), **no** se marca swing en ese `i`.

#### BOS (Break of Structure) por cierre
- Bullish BOS: el cierre de una vela rompe por arriba el último **swing high confirmado** previo:
  - `close > swing_high + bos_buffer`
- Bearish BOS: el cierre rompe por abajo el último **swing low confirmado** previo:
  - `close < swing_low - bos_buffer`

#### Dealing Range + Premium/Discount
El dealing range se define usando el **último BOS** como contexto de sesgo y los **últimos swings confirmados** como extremos activos:
- Si el último BOS es **bull**:
  - `low` = último `swing low` confirmado disponible.
  - `high` = último `swing high` confirmado disponible.
- Si el último BOS es **bear**:
  - `low` = último `swing low` confirmado disponible.
  - `high` = último `swing high` confirmado disponible.

`mid = (low + high) / 2`.

Uso práctico esperado:
- Con `current_bias=bull`: preferir setups **long** en **discount** del dealing range.
- Con `current_bias=bear`: preferir setups **short** en **premium** del dealing range.

## Non-goals
- No detección de CHOCH (Change of Character) en esta iteración.
- No ejecución de órdenes ni “estrategia completa”.
- No overlays en `plot-price` (mantenerlo limpio según `specs/price_chart.md`).
- No cambios de esquema de DB ni migraciones.

## Technical Design
### Flujo
1) Obtener velas 1m de DB y resamplear a `timeframe`.
2) Detectar `SwingPoint` con parámetros configurables.
3) Usando solo swings **confirmados**, detectar `BosEvent` por cierre.
4) Derivar `current_bias` desde el último BOS.
5) Construir `current_dealing_range` desde últimos swings confirmados (low/high), condicionado al sesgo del último BOS.
6) (UX) Exponer un reporte HTML (patrón `fvg-report`) para inspección visual:
   - Chart candlestick (Plotly) del timeframe
   - Marcadores de swings (triángulos o puntos)
   - Líneas/etiquetas para BOS
   - Banda/rectángulo para dealing range y línea de `mid`
  - Indicar explícitamente el **origen** de `DR.high`/`DR.low` (ej. etiqueta “last confirmed swing high/low”).

### Componentes (tentativo)
- `indicators/structure.py`: lógica pura (sin I/O) para swings + BOS + bias + dealing range.
- `reporting/structure_report.py`: builder HTML con Plotly.
- `cli`: comando `structure-report` para generar el HTML, alineado con `fvg-report` / `ifvg-report`.

### Integración futura (fuera de alcance)
- Reusar `current_bias` como input de `detect_ifvgs(..., htf_bias=..., config.bias_required=true)`.

## Data Impact
- Sin cambios en DB.
- Nuevo output: archivo HTML bajo `reports/` (por default).

## Edge Cases
- Series con pocas velas para formar swings (menos de `swing_left+swing_right+1`):
  - devolver sin swings y sin BOS, `current_bias=neutral`.
- “Última parte del gráfico” sin suficientes velas a la derecha:
  - si `allow_unconfirmed_last_swing=true`, marcar `confirmed=false` y **no** usarlo para BOS.
- Swing sequence incompleta para construir dealing range (por ejemplo, falta `last confirmed swing low` o `last confirmed swing high`):
  - `current_dealing_range=null` con explicación en `reason` (si se incluye logging/reasoning).
- Empates (equal highs/lows) en pivots: no deben producir swings.
- Gaps y velas con rango 0: no deben romper el detector.

## Acceptance Criteria
- Unit tests con velas sintéticas validan:
  - detección de swings con `2-2` y con parámetros distintos,
  - que empates no generan swings,
  - que un swing sin suficientes velas a la derecha se devuelve como `confirmed=false` solo si está habilitado,
  - BOS bull/bear se dispara **solo** contra swings confirmados y usando **cierre** + `bos_buffer`,
  - dealing range se calcula correctamente con `last confirmed swing low/high` y `mid` consistente,
  - cuando no hay precondiciones (pocos datos o falta swing adyacente), `current_bias`/`current_dealing_range` se devuelven en estado consistente (`neutral` / `null`).
