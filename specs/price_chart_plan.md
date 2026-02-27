- files to modify
  - specs/price_chart.md
  - specs/price_chart_plan.md
  - src/config/settings.py
  - src/charting/__init__.py
  - src/charting/timeframes.py
  - src/charting/resampler.py
  - src/charting/price_data_repository.py
  - src/charting/price_plotter.py
  - src/charting/service.py
  - src/cli/ingestion_commands.py
  - tests/unit/test_resampler.py
  - tests/unit/test_price_chart_service.py
  - tests/unit/test_cli_ingestion_commands.py
  - pyproject.toml
  - CHANGELOG.md

- order of changes
  1. Crear módulos de charting (timeframe, resample, repositorio, plotter, servicio).
  2. Agregar setting de timezone para chart (default UTC).
  2.1 Agregar fallback de end al último timestamp persistido por símbolo.
  3. Integrar comandos CLI `symbols` y `plot-price`.
  4. Agregar dependencia de plotting.
  5. Implementar tests unitarios y ajustar tests de CLI.
  6. Registrar cambio en changelog.

- migration strategy
  - No aplica (sin migraciones).

- test strategy
  - Unit tests para resample y vela parcial (incluyendo 2m/3m/4m).
- Unit tests de fallback de `end` y errores funcionales cuando no hay datos.
  - Unit tests de servicio con repositorio/plotter falsos.
  - Unit tests de CLI para nuevos comandos.

- rollback strategy
  - Revertir commit del feature; no hay cambios persistentes de datos.
