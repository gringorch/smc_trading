## Plan

### files to modify
- `.pre-commit-config.yaml` (nuevo): definicion de hooks de higiene, calidad y seguridad (`bandit` + `pip-audit`).
- `pyproject.toml`: agregar dependencias de desarrollo necesarias para ejecutar `pre-commit` y hooks localmente (si aplica).
- `README.md`: documentar instalacion y uso basico de `pre-commit`.
- `CHANGELOG.md`: registrar cambio de comportamiento del flujo de desarrollo (nuevo control pre-commit).

### order of changes
1. Crear `.pre-commit-config.yaml` con versiones fijadas y alcance de hooks para Python.
2. Ajustar `pyproject.toml` en `[project.optional-dependencies].dev` para incluir tooling requerido.
3. Ejecutar `pre-commit run --all-files` y resolver problemas de configuracion del propio setup (sin refactor funcional).
4. Documentar comandos de instalacion/uso en `README.md`.
5. Registrar la decision y alcance del cambio en `CHANGELOG.md`.

### migration strategy
- Migracion no disruptiva y opt-in por desarrollador:
1. Instalar dependencias de desarrollo.
2. Instalar hooks con `pre-commit install`.
3. Ejecutar corrida inicial con `pre-commit run --all-files`.
- No hay cambios de base de datos ni contratos externos.

### test strategy
1. Validar sintaxis/carga de `.pre-commit-config.yaml` con `pre-commit run --all-files`.
2. Confirmar ejecucion de hooks clave:
- `ruff` y `ruff-format` sobre archivos Python.
- `bandit` sobre `src/`.
- `pip-audit` para dependencias.
3. Verificar que los tests existentes del proyecto no se vean afectados por el cambio de tooling.

### rollback strategy
1. Revertir commit que introduce `.pre-commit-config.yaml` y cambios asociados en `pyproject.toml`/documentacion.
2. Ejecutar nuevamente flujo de commit sin hooks instalados.
3. Si el rollback es parcial, priorizar eliminar hook conflictivo (por ejemplo `pip-audit`) manteniendo higiene y lint base.
