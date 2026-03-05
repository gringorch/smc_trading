- files to modify
  - specs/ifvg_detection_plan.md
  - specs/ifvg_detection.md
  - src/indicators/ifvg.py
  - src/indicators/__init__.py
  - src/reporting/ifvg_report.py
  - src/cli/ingestion_commands.py
  - tests/unit/test_ifvg_detector.py
  - tests/unit/test_ifvg_report.py
  - tests/unit/test_cli_ifvg_report.py
  - CHANGELOG.md

- order of changes
  1. Implementar `indicators/ifvg.py` (lógica pura, sin I/O):
     - reuso de `detect_fvgs` para encontrar FVGs LTF candidatos,
     - filtro `min_gap_size` configurable (default `0.00005`),
     - detección de “cierre del FVG” por `inversion_fill_pct` (0.1–1.0) + `inversion_buffer`,
     - filtro de displacement (`body_pct_range` y `body_atr` con ATR simple y warmup),
     - dedupe por `one_signal_per_origin_fvg` y `cooldown_bars`,
     - cálculo de niveles de orden:
       - `entry_model=market_on_close` (default),
       - `stop_model=beyond_gap_edge` (default) + `sl_buffer`,
       - `tp_model=rr` (default) + `rr`.
  2. Exportar API en `src/indicators/__init__.py` (si corresponde al patrón existente).
  3. Agregar builder de reporte `src/reporting/ifvg_report.py`:
     - reutiliza patrón de `fvg_report.py` (Plotly + tabla).
     - incluye metadata de parámetros IFVG y señales.
  4. Agregar comando CLI Typer `ifvg-report` en `src/cli/ingestion_commands.py`:
     - obtiene velas resampleadas a `ltf_timeframe`,
     - ejecuta detector IFVG,
     - expone `min_gap_size`, `max_bars_from_fvg_formation_to_inversion` y `body_pct_range`,
     - genera HTML y escribe reporte a `--output` (default `reports/ifvg_report.html`),
     - imprime un summary (cantidad de señales, output path, symbol/timeframe).
     - Nota: POI/sweep/bias quedan como flags/config opcionales, pero con defaults que NO bloquean señales:
       - `poi_required=false`, `sweep_required=false`, `bias_required=false`.
  5. Tests unitarios del detector IFVG con velas sintéticas:
     - casos bull->sell y bear->buy,
     - efecto de `inversion_fill_pct` (ej. 0.7 pasa, 1.0 no),
     - displacement filter,
     - cálculo de `entry/stop/tp` con RR.
  6. Tests unitarios de reporte/CLI:
     - `test_ifvg_report.py` valida HTML con chart + tabla/listado.
     - mock de `PriceChartService.get_price_bars` + `detect_ifvgs`,
     - valida escritura del HTML y mensaje de salida.
  7. Registrar el feature en `CHANGELOG.md` (entrada “IFVG report CLI + detector”).

- migration strategy
  - No aplica (sin migraciones / sin cambios de esquema).

- test strategy
  - `pytest tests/unit/test_ifvg_detector.py`
  - `pytest tests/unit/test_ifvg_report.py`
  - `pytest tests/unit/test_cli_ifvg_report.py`
  - (opcional) `pytest` completo si el repo lo permite en tu entorno.

- rollback strategy
  - Revertir los cambios del feature (archivos `ifvg.py`, `ifvg_report.py`, comando CLI, tests y changelog).
