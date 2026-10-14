# install-hooks: plantillas de usuario y exit 1 (para 4.17.1)

- Bug: `hefesto install-hooks` fuera de un clon de Agents-Hefesto decía "template not found" dos veces y salía con 0.
- Fix: plantillas de usuario en el paquete (`hefesto/cli/hook_templates.py`, módulo .py, así entran al wheel sin tocar MANIFEST); se usan cuando no existe `scripts/git-hooks/` con plantillas. Exit 1 si no quedó ningún hook instalado o al día.
- pre-commit: `hefesto analyze <staged> --fail-on HIGH --allow-no-files`; pre-push: `hefesto analyze . --fail-on CRITICAL --allow-no-files`.
- Prueba manual: repo nuevo, `install-hooks` (exit 0), commit de `app.py` con `eval(x)` → bloqueado (EVAL_USAGE CRITICAL, exit 1).
- Tests: `tests/test_install_hooks_user_templates.py` (6) + los 5 existentes.
- No incluye el fix de check-test-contradictions para llamadas sin argumentos (reservado para PYTHIA).
- Sin merge: mañana como pronto, con el OK de Arturo.
