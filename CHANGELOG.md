# Changelog

## 2026-02-27

- Added price chart feature modules (`charting`) with layered data access, UTC timeframe resampling, and candlestick rendering via `mplfinance`.
- Added CLI commands `symbols` (list active symbols) and `plot-price` (render/save candlestick chart from persisted 1m candles).
- Added chart timezone runtime setting (`CHART_TIMEZONE`, default `UTC`) and strict UTC validation for chart bucketing.
- Added unit tests for resampling correctness (`1m -> 5m/15m/1h/1d`), partial last candle inclusion, chart service behavior, and CLI chart command wiring.
- Added plotting dependencies (`pandas`, `matplotlib`, `mplfinance`).

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
