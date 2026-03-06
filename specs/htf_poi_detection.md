## Context
Hoy el proyecto ya tiene piezas separadas para:
- detectar `FVG`,
- derivar `bias` HTF con `BOS`,
- calcular `dealing range` con zonas de `discount` y `premium`,
- detectar `IFVG` en LTF como posible gatillo.

Falta una pieza intermedia para combinar ese contexto HTF y responder una pregunta operativa simple:

“¿Tiene sentido empezar a buscar gatillo en LTF ahora?”

La intención no es ejecutar una entrada desde HTF, sino activar un “radar” cuando el precio vuelve a una zona de interés coherente con el sesgo.

Primer caso objetivo:
- tendencia / bias alcista en HTF,
- existe un `bullish FVG` relevante dejado por una pata impulsiva,
- el precio retrocede hacia ese FVG,
- y la interacción ocurre dentro de `discount` del dealing range HTF.

En ese momento la app debe marcar una `POI HTF activa` para habilitar luego la búsqueda de gatillo LTF.

Aunque el primer caso objetivo es alcista, el feature debe diseñarse desde el inicio de forma simétrica para contexto `bull` y `bear`, sin quedar acoplado a longs solamente.

## Requirements
### Inputs
- Fuente de datos: velas 1m persistidas en DB + resample a `htf_timeframe`.
- `htf_timeframe`: timeframe donde se define el contexto y la POI.
- Reuso explícito de componentes existentes:
  - detector de `FVG`,
  - detector de estructura para `bias`, `BOS` y `dealing range`.
- Configuración mínima:
  - `fvg_direction_filter`: `with_bias` | `both`
    - default `with_bias`
  - `require_discount_premium_alignment`: bool
    - default `true`
  - `poi_activation_rule`: `touch` | `wick_inside` | `close_inside`
    - default `touch`
  - `max_active_pois`: int >= 1
    - default `50`
  - `only_unmitigated_fvg`: bool
    - default `true`
  - `poi_validity_bars`: int >= 1 | null
    - default `null` (sin expiración fija)
  - `poi_expiration_rule`: `none` | `bars_since_activation` | `bars_since_creation`
    - default `bars_since_activation`
  - `poi_dynamic_width_enabled`: bool
    - default `true`
  - `max_dynamic_extension_bars`: int >= 1 | null
    - default `null` (sin límite)
  - `dynamic_width_source`: `wick` | `body`
    - default `wick`
  - `replay_context`: bool
    - default `true`
- El feature debe contemplar parámetros explícitos por herramienta reutilizada:
  - estructura:
    - `swing_left`
    - `swing_right`
    - `bos_buffer`
  - FVG:
    - `min_gap_size`
    - `mitigation_rule`
    - `only_unmitigated_fvg`
  - POI:
    - `poi_activation_rule`
    - `poi_validity_bars`
    - `poi_expiration_rule`
    - `max_active_pois`
- La meta es que la definición de POI HTF pueda afinarse sin tocar código de estrategia cada vez que se quiera recalibrar sensibilidad.

### Output
El detector debe devolver un estado HTF consumible por otras piezas:
- `current_bias`: `bull` | `bear` | `neutral`
- `dealing_range`: snapshot actual o `null`
- lista de `poi_candidates` ordenada por prioridad/recencia, donde cada POI incluye:
  - `side`: `buy` | `sell`
  - `status`: `pending` | `active` | `invalidated`
  - `source_fvg_direction`: `bull` | `bear`
  - `fvg_formed_at`
  - `poi_low`
  - `poi_high`
  - `dynamic_poi_low`
  - `dynamic_poi_high`
  - `discount_premium_context`: `discount` | `premium` | `mid` | `outside_range`
  - `activated_at`: timestamp nullable
  - `invalidated_at`: timestamp nullable
  - `expires_at`: timestamp nullable
  - `activation_reason`: lista de flags explícitos
  - `expiration_reason`: lista de flags explícitos
  - `reason`: lista de flags explícitos
- `active_poi`: la única POI operativa actual o `null`

### Definiciones operativas
#### Rol de la POI
- La `POI HTF` es una zona habilitadora para bajar a LTF.
- La `POI HTF` no es por sí sola una orden ni una señal de entrada.
- Mientras exista `active_poi`, el sistema puede buscar gatillos LTF en la dirección de la POI.
- La POI debe declarar explícitamente qué se busca dentro de la zona:
  - `buy` si la zona habilita búsqueda de compras
  - `sell` si la zona habilita búsqueda de ventas

#### Selección base por sesgo
- Si `current_bias = bull`, la POI candidata principal debe habilitar únicamente contexto de compra.
- Si `current_bias = bear`, la POI candidata principal debe habilitar únicamente contexto de venta.
- Si `current_bias = neutral`, no debe haber `active_poi`.

#### FVG elegible como POI
- En bias alcista, el sistema debe priorizar `bullish FVG`.
- En bias bajista, el sistema debe priorizar `bearish FVG`.
- Si `fvg_direction_filter = with_bias`, se descartan FVG opuestos al sesgo.
- Si `only_unmitigated_fvg = true`, solo pueden proponerse FVG que aún no hayan sido mitigados al momento de ser seleccionados como POI candidata.
- Si `replay_context = true`, la elegibilidad se evalúa con el contexto histórico disponible al momento de formación del FVG (sin sesgo del final de la serie).

#### Alineación con premium/discount
- En bias alcista, una POI solo es válida si su zona útil intersecta `discount` del dealing range HTF cuando `require_discount_premium_alignment = true`.
- En bias bajista, una POI solo es válida si su zona útil intersecta `premium` del dealing range HTF cuando `require_discount_premium_alignment = true`.
- Si la intersección ocurre exactamente sobre `mid`, debe clasificarse como `mid` y no activar POI salvo que el PLAN defina lo contrario.

#### Activación de POI
Una POI candidata pasa a `active` cuando el precio HTF vuelve a interactuar con su rango según `poi_activation_rule`:
- `touch`:
  - existe intersección entre el rango de la vela y `[poi_low, poi_high]`
- `wick_inside`:
  - al menos una mecha entra al rango
- `close_inside`:
  - el cierre queda dentro del rango

La activación representa:
- “empezar a buscar gatillo”, no “ejecutar”.

#### Ancho dinámico de POI (post-activación)
- Si `poi_dynamic_width_enabled = true`, una POI activa puede expandir su ancho con velas posteriores hasta cierre (`invalidated` o `expired`):
  - con `dynamic_width_source=wick`:
    - `dynamic_poi_low = min(dynamic_poi_low, low[i])`
    - `dynamic_poi_high = max(dynamic_poi_high, high[i])`
  - con `dynamic_width_source=body`:
    - `dynamic_poi_low = min(dynamic_poi_low, min(open[i], close[i]))`
    - `dynamic_poi_high = max(dynamic_poi_high, max(open[i], close[i]))`
- Si `max_dynamic_extension_bars` está definido, solo se consideran como máximo esas velas posteriores a la activación para expandir el ancho.
- Antes de la activación, la POI conserva el ancho original del FVG.

#### Invalidación de POI
Una `active_poi` debe pasar a `invalidated` si ocurre alguna de estas condiciones:
- cambia el `current_bias` a la dirección opuesta,
- expira según `poi_expiration_rule` y `poi_validity_bars`,
- el dealing range deja de existir de forma consistente,
- el precio cierra más allá del borde opuesto del FVG en una forma que invalide la idea operativa.

La regla exacta de invalidación por precio debe fijarse en el PLAN.

Expiración configurable:
- `none`:
  - la zona no expira por tiempo, solo por invalidación estructural/precio
- `bars_since_activation`:
  - la zona expira luego de `poi_validity_bars` velas HTF desde `activated_at`
- `bars_since_creation`:
  - la zona expira luego de `poi_validity_bars` velas HTF desde la creación de la candidata

### Priorización de múltiples POIs
Si existen varios FVG elegibles:
- default: priorizar el más reciente alineado con bias y premium/discount.
- `max_active_pois` limita cuántas POIs pueden devolverse como relevantes.
- `active_poi` debe ser una sola para evitar ambigüedad en la capa LTF.

### Interfaces de uso
- Exponer una interfaz reutilizable en código para:
  - obtener contexto HTF,
  - listar POIs candidatas,
  - resolver `active_poi`.
- Exponer configuración por archivo YAML para evitar dependencias de muchos flags CLI en corridas repetibles.
- Exponer un reporte HTML para inspección visual, siguiendo el patrón del resto del proyecto.
  - Debe mostrar:
    - chart candlestick HTF,
    - dealing range y `mid`,
    - zonas `discount/premium`,
    - FVGs elegibles,
    - POIs detectadas como overlays diferenciados,
    - etiqueta visible por POI con:
      - `buy` o `sell`
      - estado actual
      - expiración o ausencia de expiración
    - render temporal por tramos:
      - tramo pending con ancho FVG original
      - tramo active con ancho dinámico (si habilitado)
    - tabla con candidatas/activas/invalidadas y:
      - lado buscado
      - `dynamic_poi_low`
      - `dynamic_poi_high`
      - `activated_at`
      - `expires_at`
      - `invalidated_at`
      - razones de activación
      - razones de expiración/invalidez

### Tests
- Tests unitarios con datasets sintéticos para validar:
  - bias alcista + bull FVG en discount => genera POI candidata válida,
  - bias alcista + bull FVG fuera de discount => no activa si alignment es requerido,
  - bias bajista + bear FVG en premium => genera POI candidata válida,
  - `poi_activation_rule` cambia el comportamiento,
  - cambio de bias invalida la POI activa,
  - múltiples FVG elegibles respetan la priorización.

## Non-goals
- No detectar ni ejecutar el gatillo LTF en esta iteración.
- No integrar todavía `liquidity sweep` como requisito obligatorio de la POI HTF.
- No modelar OB, breaker blocks o refinamientos ICT adicionales.
- No cambiar esquema de DB ni agregar migraciones.
- No reemplazar el detector IFVG actual en esta iteración.
- No fijar parámetros hardcodeados sin exponerlos en configuración donde ya exista la herramienta base.

## Technical Design
### Flujo
1) Obtener velas resampleadas en `htf_timeframe`.
2) Analizar estructura HTF para derivar `current_bias` y `dealing_range`.
3) Detectar FVGs HTF.
4) Filtrar FVGs elegibles según:
   - dirección compatible con bias,
   - estado de mitigación,
   - intersección con `discount` o `premium` según bias.
5) Para cada FVG elegible, construir una `POI candidate`.
6) Evaluar si alguna candidata está `active` por interacción actual del precio.
7) Resolver una única `active_poi` prioritaria para consumo por la capa LTF.
8) Exponer salida visual en HTML y salida estructurada reutilizable.

### Componentes y responsabilidades
- `indicators/htf_poi.py`:
  - lógica pura para combinar `structure` + `fvg` y producir `poi_candidates` / `active_poi`
- `reporting/htf_poi_report.py`:
  - reporte HTML con overlays HTF
- `cli`:
  - comando tentativo `htf-poi-report`

### Decisiones a fijar en el PLAN
- Qué significa exactamente “pata impulsiva” en términos operativos:
  - por ahora el proxy es FVG alineado con bias
- Regla exacta de invalidación por precio
- Cómo resolver FVG solapados
- Si la POI usa todo el rango del FVG o una sub-zona refinada
- Cómo integrar esta salida con `ifvg-report` sin acoplar en exceso
- Cómo renderizar visualmente expiración futura vs expiración ya ocurrida

## Data Impact
- Sin cambios en DB.
- Nuevo output principal:
  - modelo de datos de `HTF POI context`
  - reporte HTML bajo `reports/`

## Edge Cases
- `current_bias = neutral`:
  - no debe activarse ninguna POI
- Existe FVG alineado, pero no hay dealing range válido:
  - no activar POI si se requiere alineación con discount/premium
- El FVG intersecta tanto `discount` como `mid` por superposición parcial:
  - el criterio de clasificación debe ser explícito en el PLAN
- Múltiples FVG muy cercanos o solapados:
  - debe haber regla determinística de priorización
- Última vela del gráfico toca y atraviesa completamente la zona:
  - evitar marcar activación e invalidación ambiguas en el mismo paso sin regla explícita
- FVG ya mitigado antes de que exista bias utilizable:
  - no debe reactivarse retroactivamente si `only_unmitigated_fvg = true`
- `poi_expiration_rule=bars_since_creation` con activación tardía:
  - puede ocurrir que una candidata expire antes de activarse
- Cambio de parámetros de swings/FVG:
  - debe producir resultados determinísticos y testeables para evitar ambigüedad entre corridas

## Acceptance Criteria
- Dado un set sintético con `bias = bull`, dealing range válido y un `bullish FVG` que intersecta `discount`, el detector devuelve una `POI candidate` de compra.
- Dado un set sintético con `bias = bear`, dealing range válido y un `bearish FVG` que intersecta `premium`, el detector devuelve una `POI candidate` de venta.
- Cuando el precio HTF vuelve a tocar esa zona según la regla configurada, la POI pasa a `active`.
- Si el mismo escenario ocurre fuera de `discount` y `require_discount_premium_alignment = true`, no se activa POI.
- Dado un cambio posterior de bias opuesto, la `active_poi` queda invalidada.
- Cambiar `poi_expiration_rule` o `poi_validity_bars` modifica de forma verificable la expiración de la zona.
- Cambiar `max_dynamic_extension_bars` modifica de forma verificable el ancho dinámico final de la zona.
- El reporte HTML permite inspeccionar visualmente:
  - bias actual,
  - dealing range,
  - FVGs elegibles,
  - POIs detectadas,
  - qué se busca en cada zona (`buy`/`sell`),
  - cuándo expira cada zona,
  - razones de activación y expiración.
