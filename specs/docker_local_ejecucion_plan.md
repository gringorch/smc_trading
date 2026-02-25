# Implementation Plan: Entorno Docker local con MySQL persistente

**Date**: 2026-02-23  
**Spec**: [`specs/docker_local_ejecucion.md`](./docker_local_ejecucion.md)

## PLAN Structure (mandatory)

### 1. files to modify

1. `Dockerfile` (nuevo)  
   - Imagen base Python 3.11 slim.
   - Copia de codigo y metadata de proyecto.
   - Instalacion de dependencias de runtime desde dependencias base del proyecto.
2. `docker-compose.yml` (nuevo)  
   - Servicio `db` (MySQL 8) con healthcheck.
   - Servicio `app` para ejecutar CLI/migraciones.
   - Volumen nombrado para persistencia en `/var/lib/mysql`.
3. `.dockerignore` (nuevo)  
   - Excluir artefactos locales para optimizar build context.
4. `.env.docker.example` (nuevo)  
   - Variables de entorno para runtime Docker (`DB_HOST=db`).
5. `README.md`  
   - Seccion breve con runbook Docker (up, migrate, seed, comandos CLI).
6. `CHANGELOG.md`  
   - Registrar cambio de comportamiento/operacion (nuevo flujo Docker local).
7. `pyproject.toml`
   - Mover `dukascopy` a dependencias base (no opcional).

### 2. order of changes

1. Actualizar `pyproject.toml` para que `dukascopy` sea dependencia base.
2. Crear `Dockerfile` con instalacion de app y dependencias requeridas.
3. Crear `docker-compose.yml` con servicios `db` y `app`, healthcheck y volumen persistente.
4. Crear `.dockerignore` para reducir build context y evitar copiar entorno local.
5. Crear `.env.docker.example` con valores por defecto para compose runtime.
6. Actualizar `README.md` con instrucciones operativas en Docker.
7. Actualizar `CHANGELOG.md` dejando traza del feature de entorno Docker local y el cambio de dependencias.

### 3. migration strategy

1. No hay migraciones de schema nuevas en codigo.
2. El schema existente se inicializa ejecutando:
   - `docker compose run --rm --env-file .env.docker app alembic upgrade head`
3. Persistencia:
   - Los datos y schema quedan en volumen Docker nombrado mientras no se ejecute `docker compose down -v`.
4. Re-inicializacion completa:
   - `docker compose down -v` + `up` + `alembic upgrade head`.

### 4. test strategy

1. Verificacion de sintaxis/config:
   - `docker compose config` debe resolver correctamente servicios/volumen.
2. Smoke operativos documentados:
   - levantar DB: `docker compose up -d db`
   - ejecutar migraciones: `docker compose run --rm --env-file .env.docker app alembic upgrade head`
   - insertar asset de prueba en `assets`
   - ejecutar `smc-trading backfill` para confirmar conexion app↔db.
3. Verificacion de persistencia:
   - crear dato de prueba, ejecutar `docker compose down` y `docker compose up -d`, validar que sigue presente.
4. Nota:
   - No se agregan tests automatizados de Python porque el cambio es de infraestructura/operacion.

### 5. rollback strategy

1. Rollback de archivos:
   - revertir `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.docker.example`, cambios en `README.md` y `CHANGELOG.md`.
2. Rollback operativo:
   - dejar de usar compose y volver al flujo local actual (venv + MySQL host).
3. Limpieza opcional:
   - eliminar contenedores y volumen creados con `docker compose down -v` si se decide descartar entorno Docker.
