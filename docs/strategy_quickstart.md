# Strategy Quickstart (HTF -> LTF + Backtesting)

## 1) Definir estrategia
Crear archivo YAML basado en `strategies/examples/htf_ltf_ifvg.yaml`.

## 2) Generar eventos
Usar la capa actual:
- `analyze(symbol, timeframe, candles)`
- `analyze_multi_tf(...)`
- `analyze_adaptive(...)`

## 3) Evaluar estrategia
- Cargar definición con `load_strategy_definition(path)`.
- Evaluar reglas declarativas con `evaluate_strategy(events_htf, events_ltf, strategy_def)`.
- Resultado: lista de `TradeIntent`.

## 4) Correr backtest
- Ejecutar `run_backtest(intents, candles_ltf, strategy_def)`.
- Resultado: `BacktestReport` con resumen y lista de trades.

## 5) Interpretar output
`BacktestReport.summary` incluye:
- total_trades
- win_rate
- pnl_gross / pnl_net
- profit_factor
- max_drawdown

Cada trade incluye:
- `entry_ts`, `entry_price`
- `exit_ts`, `exit_price`
- `direction`, `qty`
- `pnl_gross`, `pnl_net`
- `exit_reason`
