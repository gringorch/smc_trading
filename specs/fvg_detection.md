## Context
Queremos incorporar una primera herramienta “standalone” para detectar **Fair Value Gaps (FVG)** sobre una serie OHLCV, con una UX simple (consumible sin integrar todavía un backtester completo) y que luego se pueda reutilizar como componente para estrategias/backtesting.

El proyecto ya tiene:
- Persistencia de velas 1m en DB.
- Resample a timeframes mayores y plot básico de precio via CLI (`plot-price`).

La primera iteración debe enfocarse en:
1) detección consistente de FVG (bull/bear),
2) visualización clara,
3) salida “web” simple vía **reporte HTML**.

## Requirements
### Detección
- Detectar FVG en un set de velas resampleadas (timeframe objetivo) usando una definición explícita y testeable **basada en el gap** (no en el color de una sola vela).
  - Nota: “bull/bear” en FVG normalmente refiere a la **dirección del desplazamiento/imbalance** (cómo queda orientado el gap en el patrón de 3 velas), y el color de la vela (verde/roja) puede usarse como *filtro opcional* pero no define por sí solo la existencia del gap.
  - **Bullish FVG (3-candle gap up)**: gap entre `high` de vela i y `low` de vela i+2 cuando `high[i] < low[i+2]`.
  - **Bearish FVG (3-candle gap down)**: gap entre `high` de vela i+2 y `low` de vela i cuando `low[i] > high[i+2]`.
- Permitir filtrar por dirección:
  - `bull`, `bear`, o `both`.
- Calcular y devolver para cada FVG:
  - `direction` (bull/bear)
  - `formed_at` (timestamp de la vela i+2, cuando el patrón queda confirmado)
  - `gap_low`, `gap_high`
  - `gap_size` (gap_high - gap_low, en precio)
  - `index_start`/`index_end` (índices de velas relevantes o timestamps equivalentes)

### Configuración (mínima, pero extensible)
- Soportar opciones de configuración (con defaults claros):
  - `direction`: `both` (default)
  - `min_gap_size`: float (default `0.0`) para ignorar gaps chicos
  - `mitigation`:
    - `enabled`: bool (default `true`)
    - `rule`: `wick` o `close` (default `wick`)
    - si está habilitado, marcar si el FVG fue mitigado y cuándo:
      - `mitigated`: bool
      - `mitigated_at`: timestamp (nullable)
- No requerir otras señales/estructura SMC (solo FVG).

### UX / Salida HTML (reporte “web”)
- Generar un **HTML report** que se pueda abrir en el navegador (sin servidor).
- El reporte debe incluir:
  1) encabezado con los parámetros usados (`symbol`, `timeframe`, `candles`, `end`, y config FVG),
  2) un chart candlestick **interactivo (Plotly)** con overlays de FVG (zonas/rectángulos),
  3) una tabla debajo listando cada señal/FVG (ordenable por fecha o al menos listada por fecha).
- El HTML debe ser **auto-contenido** o tener una estrategia clara de assets:
  - preferencia: **liviano usando CDN** para Plotly JS (requiere internet al abrir el HTML).

### Interfaces de uso
- Exponer un comando de CLI (Typer) para generar el reporte:
  - ejemplo tentativo: `fvg-report --symbol EURUSD --timeframe 4h --candles 500 --end ... --direction bull --output report.html`
- Reutilizar la obtención de datos existente:
  - origen: candles persistidas 1m → resample a `timeframe` objetivo.

### Tests
- Tests unitarios para:
  - detección bull/bear con datasets sintéticos mínimos,
  - respeto de `direction`,
  - filtrado por `min_gap_size`,
  - mitigación con regla `wick` y `close`.

## Non-goals
- No backtesting ni simulación de trades.
- No API HTTP ni UI con estado (no “web app” interactiva en esta fase).
- No integración con otros conceptos SMC (POI, BOS/CHOCH, etc.).
- No cambios de esquema de DB ni migraciones.

## Technical Design
### Flujo
1) CLI recibe parámetros (symbol/timeframe/candles/end + config FVG).
2) Servicio de chart/datos obtiene velas resampleadas.
3) Módulo de detección FVG produce lista de gaps + metadatos + mitigación opcional.
4) Módulo de plotting genera imagen de chart con overlays.
5) Módulo de reporting arma HTML (encabezado + imagen + tabla) y lo guarda.

### Componentes y responsabilidades
- `PriceDataRepository` / `PriceChartService` (existente): lectura y resample.
- `FvgDetector` (nuevo): lógica pura de detección/mitigación (sin I/O).
- `FvgPlotter` (nuevo o extensión del plotter existente): dibuja rectángulos FVG sobre candlestick.
- `HtmlReportBuilder` (nuevo): genera HTML a partir de (metadata + imagen + tabla).
- `CLI` (extensión): expone comando `fvg-report`.

### Decisiones de implementación a fijar en el PLAN
- Librería de chart:
  - Plotly (HTML interactivo).
- Estrategia de assets:
  - usar CDN (más liviano) vs JS inline (offline, más pesado).

## Data Impact
- Sin cambios en DB.
- Solo lecturas de `assets` y `market_candles` (vía repos existentes).

## Edge Cases
- Símbolo inexistente o sin datos.
- `candles <= 0`.
- Timeframe inválido.
- No se detectan FVG → reporte igual se genera (chart sin overlays + tabla vacía).
- Velas con NaN/orden temporal incorrecto (debe fallar con error claro).
- Mitigación:
  - FVG formado en la última vela: puede quedar sin “futuro” para mitigar.
  - Regla `close`: requiere definir “close dentro del gap” vs “close cruzando el borde” (dejar explícito en PLAN).

## Acceptance Criteria
- `fvg-report` genera un archivo HTML y lo abre manualmente en navegador mostrando:
  - chart con FVG bull/bear (según config),
  - tabla con todas las detecciones y sus campos.
- Con un set sintético de velas, los tests validan detección bull/bear y mitigación.
- No hay cambios de esquema y el cambio es modular (detector reutilizable por futuros componentes).
