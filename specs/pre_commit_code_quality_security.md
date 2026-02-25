## Context
Necesitamos estandarizar controles automaticos de calidad y seguridad antes de cada commit para reducir defectos evitables y hallazgos de seguridad basicos en el codigo Python.

Actualmente no existe configuracion de `pre-commit` en el repositorio, por lo que la ejecucion depende de disciplina manual y puede generar inconsistencias entre desarrolladores.

## Requirements
1. Debe existir un archivo de configuracion de `pre-commit` en la raiz del repositorio.
2. La configuracion debe incluir validaciones de calidad de codigo para Python.
3. La configuracion debe incluir al menos una validacion de seguridad sobre codigo Python.
4. La configuracion debe incluir una validacion de seguridad de dependencias Python con `pip-audit`.
5. Las validaciones deben ejecutarse automaticamente en `git commit` una vez instalado `pre-commit`.
6. La configuracion debe ser reproducible en entorno local sin requerir servicios externos.
7. El alcance inicial debe priorizar cambios minimos e incrementales (sin refactor del codigo existente).

## Non-goals
1. Reescribir o refactorizar codigo existente para cumplir nuevas reglas en esta iteracion.
2. Configurar pipelines de CI/CD en esta tarea.
3. Incorporar escaneo de dependencias remoto o SaaS.
4. Cubrir politicas de seguridad avanzadas (SAST empresarial, secretos historicos del repositorio completo, etc.) en esta iteracion.

## Technical Design
1. Agregar `.pre-commit-config.yaml` en la raiz del proyecto.
2. Definir hooks base de higiene de repositorio (por ejemplo: trailing whitespace, end-of-file-fixer, check-yaml).
3. Definir hook de calidad Python con `ruff` para linting y ordenamiento de imports.
4. Definir hook de formato Python con `ruff-format`.
5. Definir hook de seguridad Python con `bandit` apuntando a `src/`.
6. Definir hook de seguridad de dependencias con `pip-audit` sobre el entorno/dependencias del proyecto.
7. Ajustar dependencias de desarrollo para incluir herramientas requeridas por hooks solo si es necesario para ejecucion local consistente.
8. Documentar el uso minimo (instalacion y ejecucion manual inicial) en `README.md` o `CHANGELOG.md` segun impacto de comportamiento.

## Data Impact
1. No hay cambios en base de datos, migraciones, contratos API ni esquema.
2. Se agregan solo archivos/configuracion de tooling de desarrollo.

## Edge Cases
1. Archivos no Python en el repositorio no deben bloquearse por reglas Python.
2. Hallazgos de seguridad en codigo legado pueden bloquear commits; debe poder usarse exclusion localizada y explicita cuando este justificado.
3. Diferencias de version de herramientas entre equipos deben mitigarse con versiones fijas o acotadas en hooks.
4. Hooks lentos pueden afectar experiencia de commit; se prioriza set inicial liviano.

## Acceptance Criteria
1. Existe `.pre-commit-config.yaml` en la raiz con hooks de higiene, calidad Python y seguridad Python.
2. Al ejecutar `pre-commit run --all-files`, los hooks se ejecutan sin errores de configuracion.
3. `ruff` y `ruff-format` analizan/formattean archivos Python del proyecto.
4. `bandit` analiza codigo Python del directorio `src/`.
5. `pip-audit` valida vulnerabilidades conocidas en dependencias del proyecto.
6. El repositorio documenta como instalar y ejecutar `pre-commit`.
7. No se introducen cambios funcionales en la logica de negocio.
