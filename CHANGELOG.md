# Changelog

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
