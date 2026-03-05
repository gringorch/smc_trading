## Files to modify
- `src/indicators/structure.py` (nuevo): detector puro de swings + BOS + bias + dealing range.
- `src/reporting/structure_report.py` (nuevo): HTML report con Plotly (candles + swings + BOS + dealing range).
- `src/cli/ingestion_commands.py` (extender): comando `structure-report`.
- `tests/test_structure.py` (nuevo): unit tests con velas sintéticas.
- `CHANGELOG.md` (extender): entrada del feature.

## Order of changes
1) Crear `src/indicators/structure.py`:
   - Modelos `SwingPoint`, `BosEvent`, `DealingRange`, `StructureState`, `StructureConfig`.
   - Funciones:
     - `detect_swings(bars, config) -> list[SwingPoint]` (con `confirmed` + opción `allow_unconfirmed_last_swing`).
     - `detect_bos(bars, swings, config) -> list[BosEvent]` (solo contra swings confirmados; por cierre + `bos_buffer`).
     - `derive_structure_state(bars, swings, bos_events) -> StructureState` (bias + DR).
2) Crear tests `tests/test_structure.py`:
   - Swings 2-2 configurable.
   - Empates (equal highs/lows) no generan swing.
   - Último swing sin suficientes velas a la derecha:
     - se devuelve `confirmed=false` si `allow_unconfirmed_last_swing=true`,
     - no se devuelve si `false`.
   - BOS por cierre con `bos_buffer` y solo swings confirmados.
   - Dealing range:
     - `low` desde `last confirmed swing low`,
     - `high` desde `last confirmed swing high`,
     - `mid` correcto.
3) Crear `src/reporting/structure_report.py`:
   - Plotly chart con:
     - candlesticks,
     - markers para swings (colores distintos high/low),
     - anotaciones/líneas para BOS (timestamp + nivel roto + close),
     - rectángulo del dealing range + línea mid,
     - etiquetas que muestren el **origen** de `DR.high`/`DR.low` (ej. “last confirmed swing high/low”).
4) Extender CLI en `src/cli/ingestion_commands.py`:
   - `structure-report --symbol --timeframe --candles --end ... --swing-left --swing-right --bos-buffer --allow-unconfirmed-last-swing --output`.
   - Reuso de `PriceChartService.get_price_bars(...)`.
5) Actualizar `CHANGELOG.md` con una entrada corta del nuevo comando/reporte.

## Migration strategy
- No hay migraciones ni cambios de esquema.
- Feature es aditivo (nuevos módulos + nuevo comando).

## Test strategy
- Ejecutar unit tests del detector con datasets sintéticos (sin DB).
- Mantener el estilo de tests existente (pytest).
- No agregar tests de integración con DB en esta iteración.

## Rollback strategy
- Eliminar el comando `structure-report` de `src/cli/ingestion_commands.py`.
- Borrar `src/indicators/structure.py`, `src/reporting/structure_report.py` y `tests/test_structure.py`.
- Revertir la entrada agregada en `CHANGELOG.md`.
