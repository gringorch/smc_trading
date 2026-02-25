# Implementation Plan: Ingesta historica basica (1m, retencion 365 dias, reprocesado)

**Date**: 2026-02-17  
**Spec**: [`specs/ingesta_historica_basica.md`](./ingesta_historica_basica.md)

## Summary

Implementar una app Python orientada a jobs de ingesta historica de mercado con MySQL como persistencia principal, enfocada en:

1. Persistir velas OHLCV de 1 minuto por activo en tabla unica particionada.
2. Evitar descargas repetidas mediante sync incremental por ultimo `timestamp_utc`.
3. Aplicar retencion automatica de 365 dias.
4. Soportar reprocesado por activo (borrado por activo/timeframe + recarga limpia hasta 1 ano).
5. Registrar trazabilidad por activo en `ingestion_state`.
6. Conectar a proveedores reales: Dukascopy (forex) y Binance (cripto).

El plan se ejecuta en pasos incrementales para tener validaciones tempranas sin incorporar API web ni backtesting en esta etapa.

## PLAN Structure (mandatory)

### 1. files to modify

1. `pyproject.toml`  
   - Dependencias base (`typer`, `sqlalchemy`, `alembic`, `pydantic-settings`, `pymysql`, libs Dukascopy/Binance).
2. `.env.example`  
   - Variables de configuracion (DB, proveedores, modo ejecucion).
3. `src/main.py`  
   - Punto de entrada CLI.
4. `src/config/settings.py`  
   - Carga tipada de configuracion.
5. `src/db/base.py`  
   - Declarative base y metadata compartida.
6. `src/db/engine.py`  
   - Creacion de engine y session factory.
7. `src/db/models/assets.py`  
   - Tabla `assets`.
8. `src/db/models/ingestion_state.py`  
   - Tabla `ingestion_state`.
9. `src/db/models/market_candles.py`  
   - Modelo de tabla unica de velas (`market_candles`).
10. `src/ingestion/providers/base.py`  
    - Contrato de proveedor de velas 1m.
11. `src/ingestion/providers/dukascopy_provider.py`  
    - Provider de forex (Dukascopy).
12. `src/ingestion/providers/binance_provider.py`  
    - Provider de cripto (Binance).
13. `src/ingestion/repositories/assets_repository.py`  
    - Lectura de activos habilitados.
14. `src/ingestion/repositories/candles_repository.py`  
    - Upsert, max timestamp, limpieza > 365 dias, borrado por activo/timeframe.
15. `src/ingestion/repositories/ingestion_state_repository.py`  
    - Estado de ejecucion por activo.
16. `src/ingestion/services/ingestion_service.py`  
    - Flujos `backfill`, `sync`, `reprocess`.
17. `src/cli/ingestion_commands.py`  
    - Comandos: `backfill`, `sync`, `reprocess`.
18. `alembic.ini`
19. `alembic/env.py`
20. `alembic/versions/<timestamp>_create_assets_ingestion_state_market_candles.py`
21. `tests/unit/test_market_candles_keys.py`
22. `tests/unit/test_retention_policy.py`
23. `tests/unit/test_reprocess_flow.py`
24. `tests/integration/test_ingestion_state_updates.py`
25. `tests/integration/test_duka_provider_ingestion.py`
26. `tests/integration/test_binance_provider_ingestion.py`
27. `README.md`  
    - Runbook minimo de ejecucion local.

### 2. order of changes

1. Inicializar base Python del proyecto y dependencias (incluyendo librerias de proveedores).
2. Implementar configuracion y capa DB (`engine`, `base`, modelos metadata).
3. Agregar migracion inicial (`assets`, `ingestion_state`, `market_candles`).
4. Implementar esquema e indices de `market_candles` con clave compuesta e indice para lecturas incrementales.
5. Definir estrategia de particionado mensual por `timestamp_utc` y mantenimiento de particiones.
6. Implementar repositorios (activos, velas, estado ingesta).
7. Implementar providers Dukascopy y Binance con paginacion y manejo de rate limits.
8. Implementar servicio de ingesta con tres flujos:
   - `backfill`: carga inicial hasta 365 dias.
   - `sync`: incremental desde ultimo timestamp + limpieza > 365 dias.
   - `reprocess`: borrado por activo/timeframe + backfill limpio.
9. Exponer comandos CLI para ejecutar cada flujo por activo y en batch.
10. Agregar tests unitarios e integracion minima (incluye providers).
11. Documentar uso local y verificaciones operativas en `README.md`.

### 3. migration strategy

1. Migracion inicial crea tablas:
   - `assets`
   - `ingestion_state`
   - `market_candles`
2. `market_candles` define clave unica compuesta:
   - (`asset_id`, `timeframe`, `timestamp_utc`)
3. `market_candles` incluye columnas:
   - `open`, `high`, `low`, `close`, `volume`, `ingested_at`
4. Particionado:
   - por rango de `timestamp_utc` con particiones mensuales.
   - crear particiones futuras (horizonte configurable, por ejemplo 2-3 meses).
   - eliminar particiones fuera de retencion (365 dias).
5. Cambios futuros de schema:
   - se versionan con Alembic.
   - mantenimiento de particiones via comando operativo dedicado.
6. No se migra data legacy porque el proyecto inicia sin datos previos.

### 4. test strategy

1. Unit tests:
   - Clave compuesta y deduplicacion en `market_candles`.
   - Retencion de 365 dias (se conserva limite, se elimina historico excedido).
   - Reprocesado por activo/timeframe (borra y recarga sin duplicados).
2. Integration tests (DB local):
   - Actualizacion correcta de `ingestion_state` en exito y error.
   - Sync incremental no duplica velas y actualiza velas corregidas.
   - Limpieza por retencion elimina registros/particiones fuera de ventana.
   - Ingesta real con Dukascopy y Binance en modo controlado (limitar rango temporal).
3. Smoke tests por CLI:
   - `ingestion backfill --asset <id>`
   - `ingestion sync --asset <id>`
   - `ingestion reprocess --asset <id>`
4. Criterio de salida de pruebas:
   - Todos los acceptance criteria del SPEC cubiertos al menos por un test.

### 5. rollback strategy

1. Rollback de codigo:
   - revertir cambios al commit/tag previo estable.
2. Rollback de DB:
   - ejecutar downgrade de Alembic para `assets`, `ingestion_state`, `market_candles` si aplica.
3. Rollback de particionado:
   - restaurar estrategia previa de mantenimiento de particiones.
   - no borrar datos adicionales fuera del downgrade definido.
4. Contencion ante incidentes:
   - deshabilitar scheduler de sync.
   - operar temporalmente solo con `backfill` manual sobre activos seleccionados.
5. Recuperacion:
   - ejecutar `reprocess` por activo afectado para reconstruir historico correcto (max 365 dias).

## Execution Notes

1. Se mantiene alcance minimo del feature: sin API HTTP, sin backtesting, sin ejecucion de ordenes.
2. Se prioriza trazabilidad y consistencia de datos por encima de optimizaciones tempranas.
3. Cualquier cambio de arquitectura mayor se tratara en un SPEC nuevo.
