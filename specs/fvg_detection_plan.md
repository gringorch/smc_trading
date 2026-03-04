- files to modify
  - specs/fvg_detection_plan.md
  - src/charting/service.py
  - src/cli/ingestion_commands.py
  - src/indicators/__init__.py
  - src/indicators/fvg.py
  - src/reporting/__init__.py
  - src/reporting/fvg_report.py
  - pyproject.toml
  - tests/unit/test_fvg_detector.py
  - tests/unit/test_fvg_mitigation.py
  - tests/unit/test_cli_fvg_report.py
  - CHANGELOG.md

- order of changes
  1. Agregar paquete `indicators` con detector FVG (lógica pura, sin I/O).
  2. Implementar mitigación opcional (`wick` / `close`) en el detector y cubrir con tests.
  3. Refactor mínimo en `PriceChartService` para exponer método que **construya y devuelva** barras resampleadas sin render (reutilizable por reportes).
  4. Agregar `reporting/fvg_report.py` para construir figura Plotly (candles + rectángulos FVG) y render HTML:
     - `include_plotlyjs="cdn"` para HTML liviano.
     - tabla HTML simple debajo (listada por fecha).
  5. Exponer comando CLI `fvg-report` (Typer) para generar el HTML a partir de `symbol/timeframe/candles/end` + config FVG.
  6. Agregar dependencia `plotly` al proyecto.
  7. Actualizar tests de CLI (si aplica) y registrar el feature en `CHANGELOG.md`.

- migration strategy
  - No aplica (sin migraciones / sin cambios de esquema).

- test strategy
  - Unit tests (sin DB) para:
    - detección bull/bear con datasets sintéticos,
    - filtros `direction` y `min_gap_size`,
    - mitigación `wick` y `close`.
  - Unit test de CLI para `fvg-report` validando que genera archivo HTML en un path temporal (mock de servicio/figura si es necesario).

- rollback strategy
  - Revertir commit del feature; no hay cambios persistentes de datos ni migraciones.
