# install-hooks: plantillas de usuario y exit 1 (para 4.17.1)

- Bug: `hefesto install-hooks` fuera de un clon de Agents-Hefesto decía "template not found" dos veces y salía con 0.
- Fix: plantillas de usuario en el paquete (`hefesto/cli/hook_templates.py`, módulo .py, así entran al wheel sin tocar MANIFEST); se usan cuando no existe `scripts/git-hooks/` con plantillas. Exit 1 si no quedó ningún hook instalado o al día.
- pre-commit: `hefesto analyze <staged> --fail-on HIGH --allow-no-files`; pre-push: `hefesto analyze . --fail-on CRITICAL --allow-no-files`.
- Prueba manual: repo nuevo, `install-hooks` (exit 0), commit de `app.py` con `eval(x)` → bloqueado (EVAL_USAGE CRITICAL, exit 1).
- Tests: `tests/test_install_hooks_user_templates.py` (6) + los 5 existentes.
- No incluye el fix de check-test-contradictions para llamadas sin argumentos (queda para un PR aparte).
- Sin merge: mañana como pronto, con el OK de Arturo.

## Revisión de Arturo (2026-10-14 tarde)
- (a) Los hooks llevan la ruta absoluta del intérprete que corrió `install-hooks` (`<python> -m hefesto`); si no existe, `hefesto` en PATH; si tampoco, exit 1 con "reinstall the hooks or set SKIP_HEFESTO_HOOKS=1". Antes salía 0 en silencio.
- (b) Directorio de hooks por `git rev-parse --git-path hooks` (worktrees/submódulos). Con `core.hooksPath` no se escribe nada: exit 1 y explicación (llamar `hefesto analyze` desde el gestor o usar el hook `hefesto-analyze` de pre-commit).
- (c) Hooks de contribuidor solo si el `pyproject.toml` raíz tiene `name = "hefesto-ai"`; se imprime qué set se usó.
- (d) Escritura en bytes con LF (sin CRLF en Windows).
- Tests: uno por caso (a: con y sin intérprete; b: hooksPath y worktree; c: proyecto ajeno y clon de Agents-Hefesto; d: sin `\r`). Los 5 tests anteriores se adaptaron (su repo de prueba declara `name = "hefesto-ai"`).
- Limitación documentada: el pre-commit analiza la copia del working tree de los archivos staged, no el índice.

## Backlog (sin implementar)
- Marcar los pings de telemetría que vienen de un hook (p. ej. una variable de entorno con valor `hook` que el hook exporta y el ping incluye) para separarlos de las corridas manuales.
