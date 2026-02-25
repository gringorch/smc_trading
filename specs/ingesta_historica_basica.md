## Context
Necesitamos un feature inicial de ingesta historica para persistir datos de mercado y evitar descargas constantes. Estos datos seran la base para backtesting y futura ejecucion de ordenes en activos de forex y cripto.

El rango operativo minimo es de 1 minuto, por lo que el almacenamiento debe priorizar velas de 1m y una politica de retencion acotada para mantener costos y volumen controlados.

## Requirements
1. El sistema debe permitir registrar activos de forex y cripto.
2. El sistema debe ingerir y persistir velas OHLCV en timeframe de 1 minuto.
3. Los datos de velas deben persistirse en una tabla unica (`market_candles`) con clave por activo, timeframe y timestamp.
4. La tabla de velas debe estar particionada por fecha para facilitar mantenimiento y retencion.
5. La ingesta debe soportar dos modos:
   - backfill inicial (carga historica hasta un maximo de 1 ano)
   - sync incremental (agrega nuevas velas desde la ultima vela persistida)
6. Debe evitarse la duplicacion de velas por (`asset_id`, `timeframe`, `timestamp_utc`).
7. Debe existir un mecanismo de limpieza que elimine velas con antiguedad mayor a 1 ano.
8. La limpieza debe ejecutarse de forma automatica dentro del flujo de sync incremental.
9. Debe registrarse estado de ingesta por activo (ultimo timestamp exitoso, ultimo intento, estado y mensaje de error si aplica).
10. El sistema debe poder reintentar en la proxima ejecucion cuando falle la ingesta de un activo sin bloquear la ingesta de otros activos.
11. Debe existir un modo de reprocesado por activo que elimine completamente los datos historicos persistidos del activo (timeframe 1m) y ejecute una recarga limpia (backfill) dentro del limite de 1 ano.
12. Debe implementarse conexion a proveedores de datos reales:
   - Forex: Dukascopy (via libreria Python).
   - Cripto: Binance (via libreria o API oficial).

## Non-goals
1. Ejecutar ordenes reales o paper trading.
2. Implementar motor de backtesting.
3. Exponer API HTTP (FastAPI/Flask/Django) en esta etapa.
4. Soportar timeframes distintos de 1 minuto.
5. Implementar estrategia de trading.
6. Implementar almacenamiento alternativo fuera de MySQL (por ejemplo, data lake o Parquet) en esta etapa.
7. Incluir indices y acciones en esta etapa (se planifica a futuro).
8. Ingesta en tiempo real (streaming) o datos tick-by-tick.

## Technical Design
1. Ingesta por lotes ejecutada desde CLI en Python.
2. Componentes:
   - provider client: obtiene velas 1m del proveedor de mercado.
   - ingestion service: coordina backfill, sync incremental, deduplicacion y limpieza.
   - repository layer: persiste velas y estado de ingesta en MySQL.
   - scheduler externo (cron o equivalente): dispara ejecuciones periodicas.
3. Proveedores:
   - `DukascopyProvider` para forex.
   - `BinanceProvider` para cripto.
4. Flujo de backfill:
   - leer activo y ventana objetivo (maximo 1 ano)
   - descargar velas en bloques paginados
   - insertar/upsert por (`asset_id`, `timeframe`, `timestamp_utc`)
   - actualizar estado de ingesta
5. Flujo de reprocesado:
   - seleccionar activo a reprocesar
   - borrar historico completo del activo para timeframe 1m en `market_candles`
   - ejecutar backfill limpio (maximo 1 ano)
   - actualizar estado de ingesta marcando ejecucion de reprocesado
6. Flujo incremental:
   - leer ultimo timestamp persistido del activo para timeframe 1m
   - solicitar nuevas velas desde ese punto
   - insertar/upsert evitando duplicados
   - ejecutar limpieza de datos > 1 ano
   - actualizar estado de ingesta
7. Diseno de tabla de velas:
   - tabla unica `market_candles`
   - particionada por rango de fecha de `timestamp_utc` (estrategia mensual)

## Data Impact
1. Se agregan tablas de metadata:
   - `assets` (catalogo de activos y clase de activo)
   - `ingestion_state` (estado por activo)
2. Se agrega tabla de velas unica `market_candles` con columnas minimas:
   - `asset_id`, `timeframe`, `timestamp_utc` (clave unica compuesta)
   - `open`, `high`, `low`, `close`, `volume`
   - `ingested_at`
3. Retencion de datos:
   - mantener solo velas de los ultimos 365 dias
   - eliminacion automatica de registros mas antiguos durante sync incremental
4. No hay cambios de contratos externos en esta fase.

## Edge Cases
1. Activo nuevo sin historico previo: debe iniciar backfill hasta el limite de 1 ano.
2. Huecos de datos por caidas del proveedor: registrar error y permitir reintento posterior.
3. Velas tardias o corregidas por proveedor: el upsert por clave compuesta debe actualizar valores existentes.
4. Diferencias de timezone: persistir todo en UTC.
5. Fallo parcial multi-activo: continuar con los demas activos y registrar resultado por activo.
6. Reprocesado interrumpido: si falla tras el borrado, debe quedar error trazable y el activo debe poder relanzarse sin intervencion manual sobre esquema.
7. Mantenimiento de particiones: creacion anticipada de particiones futuras y limpieza de particiones fuera de la ventana de retencion.
8. Limites de API de proveedores: aplicar paginacion y manejo de rate limits.

## Acceptance Criteria
1. Dado un activo configurado, al ejecutar backfill se persisten velas 1m de hasta 365 dias sin duplicados por (`asset_id`, `timeframe`, `timestamp_utc`).
2. Dado un activo con datos previos, al ejecutar sync incremental solo se insertan/actualizan velas nuevas o corregidas.
3. Tras ejecutar sync incremental, no existen velas con `timestamp_utc` anterior a 365 dias respecto a la fecha de ejecucion.
4. Si falla la ingesta de un activo, el proceso continua con otros activos y deja trazabilidad del error en `ingestion_state`.
5. Se puede consultar para cada activo el ultimo timestamp de ingesta exitosa y el estado de la ultima ejecucion.
6. Dado un activo, al ejecutar reprocesado se elimina su historico previo (1m) y se recarga nuevamente (hasta 365 dias) sin duplicados por clave compuesta.
7. Para forex, la ingesta se realiza via Dukascopy y persiste velas 1m en `market_candles`.
8. Para cripto, la ingesta se realiza via Binance y persiste velas 1m en `market_candles`.
