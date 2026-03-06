- files to modify
  - `specs/htf_poi_detection_plan.md`
  - `specs/htf_poi_detection.md`
  - `src/indicators/htf_poi.py` (nuevo)
  - `src/indicators/__init__.py`
  - `src/reporting/htf_poi_report.py` (nuevo)
  - `src/cli/ingestion_commands.py`
  - `tests/unit/test_htf_poi_detector.py` (nuevo)
  - `tests/unit/test_htf_poi_report.py` (nuevo)
  - `tests/unit/test_cli_htf_poi_report.py` (nuevo)
  - `CHANGELOG.md`

- order of changes
  1. Ajustar la SPEC si hace falta cerrar detalles menores detectados durante implementación, sin cambiar el alcance aprobado.
  2. Crear `src/indicators/htf_poi.py` como módulo puro, sin I/O, reutilizando `analyze_structure(...)` y `detect_fvgs(...)`.
     - Modelos tentativos:
       - `HtfPoiConfig`
       - `HtfPoiCandidate`
       - `HtfPoiContext`
     - Responsabilidades:
       - derivar `current_bias` y `dealing_range` desde estructura,
       - detectar FVGs HTF elegibles,
       - filtrar por alineación con `discount/premium`,
       - soportar evaluación de contexto histórico por formación (`replay_context=true`),
       - resolver `pending` / `active` / `invalidated`,
       - calcular ancho dinámico post-activación (`dynamic_poi_low/high`) con límite opcional de velas,
       - calcular `expires_at`,
       - exponer `activation_reason` y `expiration_reason`,
       - devolver una sola `active_poi` prioritaria.
  3. Exponer el nuevo API en `src/indicators/__init__.py` si el patrón del proyecto lo requiere.
  4. Crear `src/reporting/htf_poi_report.py` siguiendo el patrón de reportes actuales.
     - Plotly candlestick HTF.
     - Overlays para:
       - dealing range,
       - discount / premium,
       - FVGs elegibles,
       - POIs detectadas.
     - Etiquetas visibles por POI:
       - `buy` o `sell`,
       - estado,
       - expiración.
     - Tabla/listado con:
       - lado buscado,
       - `fvg_formed_at`,
       - `activated_at`,
       - `expires_at`,
       - `invalidated_at`,
       - razones de activación,
       - razones de expiración/invalidez.
  5. Extender `src/cli/ingestion_commands.py` con un comando tentativo `htf-poi-report`.
     - Parámetros base:
       - `symbol`
       - `htf_timeframe`
       - `candles`
       - `end`
       - parámetros de estructura (`swing_left`, `swing_right`, `bos_buffer`)
       - parámetros FVG (`min_gap_size`, `mitigation_rule`, `only_unmitigated_fvg`)
       - parámetros POI (`poi_activation_rule`, `poi_validity_bars`, `poi_expiration_rule`, `max_active_pois`)
       - parámetros de ancho dinámico (`poi_dynamic_width_enabled`, `max_dynamic_extension_bars`, `dynamic_width_source`)
       - modo de contexto (`replay_context`)
       - `output`
     - Flujo:
       - obtener barras HTF con `PriceChartService.get_price_bars(...)`,
       - correr detector HTF POI,
       - generar HTML,
       - escribir archivo y emitir summary CLI.
     - Agregar variante YAML (`htf-poi-report-yaml`) para cargar todos los parámetros desde archivo de estrategia.
  6. Agregar tests unitarios del detector en `tests/unit/test_htf_poi_detector.py`.
     - Caso `bull`:
       - bias alcista + bullish FVG en discount => POI `buy` candidata válida.
       - retorno del precio a la zona => POI `active`.
     - Caso `bear`:
       - bias bajista + bearish FVG en premium => POI `sell` candidata válida.
     - Validar:
       - `poi_activation_rule` (`touch` vs `close_inside`),
       - `require_discount_premium_alignment`,
       - ancho dinámico y límite por `max_dynamic_extension_bars`,
       - expiración con `bars_since_activation`,
       - expiración con `bars_since_creation`,
       - invalidación por cambio de bias,
       - priorización determinística cuando hay múltiples FVGs.
  7. Agregar tests de reporte en `tests/unit/test_htf_poi_report.py`.
     - Validar que el HTML incluya:
       - chart Plotly,
       - metadata/config,
       - referencias a `buy` / `sell`,
       - `expires_at`,
       - razones de activación y expiración.
  8. Agregar tests de CLI en `tests/unit/test_cli_htf_poi_report.py`.
     - Mock de `PriceChartService.get_price_bars(...)`,
     - mock del detector y del builder HTML,
     - validación de escritura de archivo y summary.
  9. Actualizar `CHANGELOG.md` con una entrada breve del nuevo detector/reporte HTF POI.
  10. Dejar la integración con `ifvg-report` fuera de esta implementación inicial.
      - Si se quiere consumir `active_poi` desde IFVG, eso va en un siguiente incremento para no mezclar detector HTF con gatillo LTF en el mismo cambio.

- migration strategy
  - No aplica: no hay migraciones ni cambios de esquema.
  - El cambio es aditivo:
    - nuevo detector,
    - nuevo reporte,
    - nuevo comando CLI.
  - No se modifica el comportamiento actual de `fvg-report`, `structure-report` ni `ifvg-report` en esta fase.

- test strategy
  - Ejecutar:
    - `pytest tests/unit/test_htf_poi_detector.py`
    - `pytest tests/unit/test_htf_poi_report.py`
    - `pytest tests/unit/test_cli_htf_poi_report.py`
  - Si el entorno lo permite, correr además la suite de regresión de componentes relacionados:
    - `pytest tests/unit/test_fvg_detector.py`
    - `pytest tests/unit/test_structure_detector.py`
    - `pytest tests/unit/test_cli_structure_report.py`
  - Usar datasets sintéticos, sin dependencia de DB, para mantener determinismo en activación/expiración.

- rollback strategy
  - Revertir los cambios del feature:
    - eliminar `src/indicators/htf_poi.py`,
    - eliminar `src/reporting/htf_poi_report.py`,
    - quitar `htf-poi-report` de `src/cli/ingestion_commands.py`,
    - eliminar los tests nuevos,
    - revertir la entrada de `CHANGELOG.md`.
  - No hay rollback de datos porque el feature no persiste estado ni altera esquema.
