## Context
La capa de estrategia/backtesting declarativa ya permite convertir eventos HTF/LTF en intents y simular resultados, pero faltan dos capacidades operativas críticas para uso real:

1. Filtrado por ventanas horarias de operación (sesiones/horas de mayor liquidez o volatilidad esperada).
2. Sizing por riesgo monetario (cantidad de contratos/lotes derivada del capital, riesgo %, distancia entry->SL y valor por punto).

Sin estas dos capacidades, la evaluación puede generar señales fuera de horario deseado y tamaños de posición inconsistentes con el riesgo objetivo de cuenta.

## Requirements
1. Permitir definir múltiples bandas horarias por estrategia (por ejemplo: London open, NY open, overlap).
2. Cada banda horaria debe incluir:
   - timezone,
   - hora inicio/fin,
   - días habilitados,
   - comportamiento para ventanas que cruzan medianoche.
3. La evaluación de estrategia debe ignorar triggers fuera de ventanas activas.
4. Debe existir un modo configurable para jornadas sin ventana activa:
   - `skip_signals` (default),
   - `collect_but_no_execute` (opcional, para análisis).
5. Incorporar position sizing por riesgo:
   - Inputs mínimos: `account_equity`, `risk_percent`, `entry_price`, `stop_price`, `contract_point_value`.
   - Fórmula objetivo:
     - `risk_amount = account_equity * risk_percent`
     - `price_risk = abs(entry_price - stop_price)`
     - `qty_raw = risk_amount / (price_risk * contract_point_value)`
6. Soportar reglas de redondeo de cantidad:
   - `qty_step`,
   - `min_qty`,
   - `max_qty`.
7. Incluir validaciones de seguridad:
   - si `price_risk == 0`, no emitir trade,
   - si `qty_raw < min_qty`, política configurable (`skip` o `clamp_min`),
   - si `qty_raw > max_qty`, clamping a `max_qty`.
8. Persistir trazabilidad en `TradeIntent.meta` y `TradeResult.meta`:
   - ventana horaria aplicada,
   - riesgo monetario objetivo,
   - cantidad calculada antes/después de redondeo.
9. El simulador debe usar `qty` calculada por riesgo (no hardcoded global fijo) para PnL.
10. La documentación de uso debe mostrar ejemplo completo:
   - estrategia con sesiones,
   - parámetros de cuenta/riesgo,
   - salida esperada de qty por trade.

## Non-goals
1. Gestión avanzada de cartera multi-asset con correlaciones.
2. Margin/leverage dinámico dependiente de broker.
3. Optimizador de ventanas horarias automático.
4. Riesgo por volatilidad dinámica (ATR-based sizing) en esta fase inicial.

## Technical Design
### 1) Extensiones de contratos declarativos
- `StrategyDefinition`
  - `trading_sessions: list[TradingSession]`
  - `risk_sizing: RiskSizingConfig`
- `TradingSession`
  - `name`, `timezone`, `start_time`, `end_time`, `weekdays`
  - `cross_midnight_mode` (implícito por start/end o explícito)
- `RiskSizingConfig`
  - `account_equity`
  - `risk_percent`
  - `contract_point_value`
  - `qty_step`
  - `min_qty`
  - `max_qty`
  - `min_qty_policy` (`skip` | `clamp_min`)

### 2) Evaluación (strategy engine)
1. Antes de aplicar trigger, validar si `trigger.ts` cae en alguna sesión activa.
2. Si no cae:
   - omitir señal (default).
3. Si cae, calcular `qty` por riesgo usando `entry_ref` y `sl`.
4. Adjuntar resultado de sizing en metadata del intent.

### 3) Simulación (backtester)
1. Consumir `intent.qty` (calculada por estrategia) en lugar de `quantity` fija.
2. Mantener `SimulationConfig.quantity` solo como fallback opcional para intents sin qty.
3. Reportar impacto de sizing en PnL agregado y por trade.

### 4) Configuración ejemplo
Agregar ejemplo en `strategies/examples/` con:
- 2 o más sesiones,
- riesgo 1% sobre equity,
- límites de qty realistas.

## Data Impact
1. Sin cambios de schema obligatorios.
2. Se agregan campos en contratos in-memory (`StrategyDefinition`, `TradeIntent.meta`).
3. Reportes pueden incluir nuevos campos de sizing/sesión en export JSON/CSV.

## Edge Cases
1. Sesión inválida (formato hora o timezone): error de validación.
2. Sesión cruzando medianoche: evaluar correctamente pertenencia temporal.
3. Días no habilitados: no emitir intents.
4. Stop igual a entry: descartar señal por riesgo cero.
5. `contract_point_value <= 0`: invalidar configuración.
6. `risk_percent <= 0` o `> 1`: invalidar configuración.
7. Rounding de qty a 0 por `qty_step`: aplicar `min_qty_policy`.

## Acceptance Criteria
1. Estrategia puede definir una o varias ventanas horarias y el engine respeta esas ventanas.
2. Intents fuera de sesión no se ejecutan por default.
3. Cada intent incluye `qty` calculada según riesgo monetario y distancia a SL.
4. Simulador calcula PnL con `qty` por intent.
5. Documentación muestra claramente cómo configurar sesiones + riesgo por cuenta.
6. Tests unitarios cubren:
   - filtro horario dentro/fuera de sesión,
   - cálculo de qty por riesgo,
   - redondeo y límites de qty,
   - integración intent->simulator con qty variable.

## Open Questions (requieren confirmación)
1. Timezone base preferida para sesiones: ¿UTC fijo o timezone por sesión (IANA)?
2. Instrumentos: ¿valor por punto fijo por símbolo en config, o lookup por metadata del activo?
3. Política cuando `qty_raw < min_qty`: ¿preferís `skip` o `clamp_min` por defecto?
4. ¿El riesgo % se calcula sobre equity fija (input) o equity dinámica tras cada trade?
