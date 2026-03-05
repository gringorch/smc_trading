# Changelog

## 2026-03-05

- Added market structure detector (`src/indicators/structure.py`) with configurable swing pivots (`swing_left/swing_right`), optional tentative last swing, BOS-by-close detection with `bos_buffer`, and derived state (`current_bias`, `current_bias_since`, dealing range with premium/discount zones).
- Added market structure HTML report builder (`src/reporting/structure_report.py`) with Plotly candlestick chart, swing markers, BOS markers, dealing range overlays, and explicit source labels for dealing-range extremes.
- Added `structure-report` CLI command (`src/cli/ingestion_commands.py`) to generate `reports/structure_report.html` (default) from persisted candles.
- Added unit tests for structure detector logic, report rendering, and CLI wiring (`tests/unit/test_structure_detector.py`, `tests/unit/test_structure_report.py`, `tests/unit/test_cli_structure_report.py`).
- Updated dealing range derivation to use the latest confirmed swing low/high as active premium/discount bounds, improving correction-zone alignment in live charts.

## 2026-03-04

- Added IFVG detector module (`src/indicators/ifvg.py`) with inversion-by-close logic (`inversion_fill_pct`), displacement filters (`body_pct_range` / `body_atr`), optional sweep/bias/POI gating, and configurable order levels (`entry/stop/tp`).
- Added IFVG HTML report builder (`src/reporting/ifvg_report.py`) and `ifvg-report` CLI command to generate chart + signals table output (`reports/ifvg_report.html` by default).
- Exposed IFVG trigger controls in CLI/config: `min_gap_size` (default `0.00005`), `max_bars_from_fvg_formation_to_inversion`, and `body_pct_range` (default `0.7`).
- Added unit tests for IFVG detection behavior (`tests/unit/test_ifvg_detector.py`), IFVG report rendering (`tests/unit/test_ifvg_report.py`), and CLI wiring/output (`tests/unit/test_cli_ifvg_report.py`).

## 2026-03-03

- Added FVG (Fair Value Gap) detector with optional mitigation (`wick` / `close`) as a reusable pure-logic module (`src/indicators/fvg.py`).
- Added `fvg-report` CLI command to generate a lightweight HTML report with Plotly candlestick chart, FVG zone overlays, and a signals table.
- Added `plotly` dependency for interactive HTML charting and unit tests for FVG detection/mitigation plus CLI wiring.

## 2026-02-27

- Added price chart feature modules (`charting`) with layered data access, UTC timeframe resampling, and candlestick rendering via `mplfinance`.
- Added CLI commands `symbols` (list active symbols) and `plot-price` (render/save candlestick chart from persisted 1m candles).
- Added chart timezone runtime setting (`CHART_TIMEZONE`, default `UTC`) and strict UTC validation for chart bucketing.
- Added unit tests for resampling correctness (`1m -> 5m/15m/1h/1d`), partial last candle inclusion, chart service behavior, and CLI chart command wiring.
- Added plotting dependencies (`pandas`, `matplotlib`, `mplfinance`).
- Fixed chart default range behavior: when `--end` is omitted, charting now anchors to the latest persisted 1m candle for the symbol, avoiding empty plots on stale datasets.
- Added clearer domain errors when no persisted candles exist for a symbol/range.
- Added additional minute timeframes for charting: `2m`, `3m`, and `4m`.

## 2026-02-25

- Added `.pre-commit-config.yaml` with repository hygiene hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-merge-conflict`, `detect-private-key`).
- Added Python code quality hooks (`ruff`, `ruff-format`) to run automatically before commits.
- Added security hooks: `bandit` (scans `src/`) and `pip-audit` (dependency vulnerability audit).
- Updated `pyproject.toml` dev dependencies to include `pre-commit`, `ruff`, `bandit`, and `pip-audit`.
- Restricted project Python support metadata to `>=3.11,<4.0` to make Poetry dependency resolution compatible with `pip-audit` transitive constraints in CI.
- Updated PR CI workflow to install dependencies with `pip install -e .[dev]` instead of Poetry, aligning CI with setuptools/PEP 621 project metadata.
- Added focused unit tests for CLI wiring, DB engine/session scope, main entrypoint, Binance provider, candles repository branches, ingestion state repository, and ingestion service edge branches.
- Increased total test coverage to 96% (`pytest --cov=. --cov-report=term-missing`).
- Documented pre-commit install and execution flow in `README.md`.

## 2026-02-24

- Fixed Alembic/MySQL migration import namespace mismatch in `alembic/env.py` to prevent duplicate SQLAlchemy table registration.
- Updated initial migration to tolerate MySQL error `1506` when partitioning `market_candles` with foreign keys, allowing schema creation to complete without partitions.
- Added a repository guard to skip partition maintenance when `market_candles` is not partitioned (`pmax` missing), plus unit test coverage.
- Fixed `DukascopyProvider` integration with `dukascopy-python` by parsing DataFrame responses correctly, normalizing forex symbols (`EURUSD` -> `EUR/USD`), and enforcing UTC-safe request/response timestamps.
- Added unit tests for Dukascopy provider parsing, request argument normalization, and error wrapping.

## 2026-02-23

- Added Docker local runtime (`Dockerfile`, `docker-compose.yml`) with MySQL 8 service and persistent named volume.
- Added `.env.docker.example` and Docker runbook in `README.md` for migrate/seed/CLI flow.
- Changed `dukascopy` dependency from optional extra to base dependency in `pyproject.toml`.

## 2026-02-21

- Added first ingestion feature for historical 1m candles (forex/crypto).
- Added MySQL schema and migration for `assets`, `ingestion_state`, `market_candles` with monthly partitioning.
- Added CLI commands: `backfill`, `sync`, `reprocess`.
- Added repositories/providers/service orchestration and retention cleanup.
- Added unit and integration tests for deduplication, retention, reprocess, and ingestion state behavior.
- Updated `pyproject.toml` packaging so `main` module is included and `smc-trading` CLI entrypoint is available.
