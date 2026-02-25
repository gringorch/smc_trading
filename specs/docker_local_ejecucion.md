## Context
Se necesita ejecutar la app de ingesta en un entorno Docker local, incluyendo MySQL, para validar el funcionamiento end-to-end sin depender de una instalacion manual de base de datos en el host.

Ademas, se requiere persistencia de datos entre reinicios/recreaciones de contenedores para no perder schema ni historico de pruebas.

## Requirements
1. Debe existir una definicion Docker para la aplicacion Python.
2. Debe existir una definicion Docker Compose para levantar aplicacion y MySQL.
3. MySQL debe usar un volumen persistente para conservar datos entre ejecuciones.
4. Debe existir un archivo de entorno de ejemplo para ejecucion en Docker con `DB_HOST` apuntando al servicio de MySQL en Compose.
5. Debe documentarse el flujo minimo de uso:
   - levantar contenedores
   - ejecutar migraciones
   - insertar activo de prueba
   - ejecutar comandos CLI (`backfill`, `sync`, `reprocess`)
6. El setup no debe requerir cambios de codigo de dominio (ingestion, repositorios, providers).
7. La dependencia `dukascopy` debe quedar incluida como dependencia base del proyecto en `pyproject.toml` para soportar forex sin extras de instalacion.

## Non-goals
1. Despliegue productivo/orquestacion (Kubernetes, ECS, etc.).
2. Hardening de seguridad para produccion.
3. Observabilidad avanzada (APM, metrics, tracing).
4. Automatizar scheduler de jobs dentro del contenedor.

## Technical Design
1. `Dockerfile` para imagen de app:
   - base `python:3.11-slim`
   - copia de codigo fuente y metadata del proyecto
   - instalacion editable con dependencias necesarias para providers.
2. `docker-compose.yml` con dos servicios:
   - `db` (MySQL 8) con variables de inicializacion y healthcheck.
   - `app` construida desde `Dockerfile`, dependiente de `db` healthy.
3. Persistencia:
   - volumen nombrado montado en `/var/lib/mysql` del servicio `db`.
4. Configuracion:
   - archivo `.env.docker.example` para variables de entorno de runtime en Docker.
5. Optimizacion de build:
   - `.dockerignore` para excluir `.venv`, `.git`, caches y artefactos.
6. Dependencias Python:
   - mover `dukascopy` de dependencia opcional a dependencia base en `pyproject.toml`.

## Data Impact
1. No se agregan nuevas tablas ni se altera el schema existente.
2. El schema actual se crea mediante migraciones Alembic en runtime.
3. Los datos de MySQL persisten en volumen Docker nombrado.
4. Se altera el contrato de instalacion del paquete: `dukascopy` pasa a instalarse por defecto.

## Edge Cases
1. Primera ejecucion sin schema: la app debe requerir `alembic upgrade head`.
2. Reejecuciones posteriores: el schema y datos deben mantenerse mientras no se elimine el volumen.
3. Eliminacion explicita de volumen (`down -v`): se pierde la data y requiere migraciones nuevamente.
4. Arranque de app antes de DB disponible: mitigado con `depends_on` + `healthcheck`.

## Acceptance Criteria
1. Con `docker compose up -d`, se levanta MySQL correctamente.
2. Con `docker compose run --rm --env-file .env.docker app alembic upgrade head`, se crean tablas del proyecto.
3. Tras reiniciar contenedores (`docker compose down` y `docker compose up -d`), las tablas y datos continúan disponibles.
4. Solo al eliminar volumen (`docker compose down -v`) se pierde la persistencia.
5. Los comandos CLI de ingesta corren desde el servicio `app` usando la DB del servicio `db`.
6. `pip install -e .` instala `dukascopy` sin requerir extras.
