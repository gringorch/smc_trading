# smc_trading

Ingesta historica de velas OHLCV 1m para activos forex y cripto usando MySQL.

## Requisitos

- Python 3.11+
- MySQL 8+

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

## Pre-commit (calidad y seguridad)

Instalar hooks en el repositorio:

```bash
pre-commit install
```

Ejecutar validacion completa manual:

```bash
pre-commit run --all-files
```

Hooks incluidos:

- Higiene de repositorio (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-merge-conflict`, `detect-private-key`).
- Calidad Python (`ruff`, `ruff-format`).
- Seguridad de codigo (`bandit` sobre `src/`).
- Seguridad de dependencias (`pip-audit`).

## Migraciones

```bash
alembic upgrade head
```

## CLI

```bash
python -m main backfill --asset-id 1
python -m main sync
python -m main reprocess --asset-id 1
```

## Docker local

1. Crear env para Docker:

```bash
cp .env.docker.example .env.docker
```

2. Levantar MySQL con volumen persistente:

```bash
docker compose up -d db
```

3. Ejecutar migraciones:

```bash
docker compose run --rm --env-file .env.docker app alembic upgrade head
```

4. Insertar un activo de prueba:

```bash
docker compose exec db mysql -usmc_user -pchange_me smc_trading -e "INSERT INTO assets (symbol, asset_class, provider_symbol, is_active) VALUES ('BTCUSDT', 'CRYPTO', 'BTCUSDT', 1);"
```

5. Ejecutar CLI:

```bash
docker compose run --rm --env-file .env.docker app smc-trading backfill --asset-id 1
docker compose run --rm --env-file .env.docker app smc-trading sync
docker compose run --rm --env-file .env.docker app smc-trading reprocess --asset-id 1
```

Persistencia:

- `docker compose down`: mantiene datos/schema en el volumen.
- `docker compose down -v`: elimina volumen y borra datos/schema.

## Seguridad y consistencia

- Configuracion por variables de entorno (sin secretos hardcodeados).
- Escrituras de DB con SQLAlchemy parametrizado.
- Deduplicacion por clave compuesta (`asset_id`, `timeframe`, `timestamp_utc`).
- Trazabilidad por activo en `ingestion_state`.
- Retencion automatica de 365 dias durante `sync`.
