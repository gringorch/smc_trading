## Context
Necesitamos visualizar series OHLCV persistidas para inspección visual en formato candlestick. La base persiste candles en 1m, por lo que cualquier timeframe superior debe derivarse por resample consistente.

## Requirements
- Exponer función de aplicación `plot_price(symbol, timeframe, candles, end=None, show=True, save_path=None, include_volume=False)`.
- Timeframes soportados: `1m`, `2m`, `3m`, `4m`, `5m`, `15m`, `1h`, `4h`, `1d`.
- El origen de datos debe ser exclusivamente candles persistidas en `timeframe=1m`.
- Bucketing UTC consistente por inicio de vela (`floor` al timeframe en UTC).
- Incluir vela parcial final cuando el bucket actual no está cerrado.
- Si `end` no se provee, usar el último timestamp 1m persistido del símbolo como referencia por defecto.
- Si no hay datos persistidos para el símbolo/rango, devolver error funcional claro.
- Logging debug con cantidad de filas crudas leídas y velas resultantes.
- CLI:
  - comando `symbols` para listar símbolos disponibles
  - comando `plot-price` para renderizar/guardar gráfico con help de parámetros
- Tests unitarios para resample 1m->5m/15m/1h/1d, inclusión de vela parcial, y cantidad exacta de velas.

## Non-goals
- No overlays técnicos (SMA/FVG/CHOCH/BOS/FOS).
- No cambios de esquema ni migraciones.
- No API HTTP.

## Technical Design
- Capa de acceso a datos (`PriceDataRepository`):
  - resolver símbolo a `asset_id`
  - leer candles 1m por rango temporal (UTC)
  - listar símbolos activos
- Capa de resample (`resampler` + `timeframes`):
  - validar timeframe
  - calcular inicio de bucket UTC
  - agregar OHLCV (open first, high max, low min, close last, volume sum)
  - mantener bucket parcial final
- Capa de chart (`price_plotter`):
  - usar `mplfinance` con DataFrame OHLC(V)
  - `show` y/o `save_path`
- Capa de orquestación (`PriceChartService`):
  - validar timezone configurada (default UTC)
  - obtener datos, resamplear, limitar a N velas y graficar

## Data Impact
- Sin cambios en DB ni contratos de tablas.
- Lectura de `assets` y `market_candles`.

## Edge Cases
- Símbolo inexistente.
- Timeframe inválido.
- `candles <= 0`.
- `end` naive (se interpreta/normaliza a UTC).
- Sin datos para símbolo/rango.
- Menos velas disponibles que N solicitado.

## Acceptance Criteria
- Ejecutar `plot-price` renderiza o guarda candlestick del símbolo solicitado.
- Timeframe y límite de velas se respetan.
- La última vela puede ser parcial.
- El diseño queda modular para overlays futuros.
