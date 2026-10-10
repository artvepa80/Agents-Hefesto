# 2026-10-10: `hefesto activate`/`deactivate`/`status` para quien tiene licencia

## Problema

`activate`, `deactivate` y `status` imprimían el mensaje de compra y salían con 1 incluso con `hefesto_pro` instalado. Se comprobó de punta a punta con hefesto-ai 4.14.1 más el wheel 3.9.1. Además, el email de licencia (repo privado) le pedía al cliente correr `hefesto activate <clave>`: el comando que paga el cliente siempre fallaba.

La activación real es la variable de entorno `HEFESTO_LICENSE_KEY`, que lee `hefesto_pro` (`FeatureGate.get_current_license`).

## Cambio (`hefesto/cli/main.py`)

- `activate KEY`: normaliza la clave a mayúsculas y valida el formato `HFST-XXXX-XXXX-XXXX-XXXX-XXXX` (si no lo cumple, sale con 1). Imprime `export HEFESTO_LICENSE_KEY=KEY` y avisa si el paquete Pro no está instalado. No guarda nada.
- `deactivate`: imprime `unset HEFESTO_LICENSE_KEY`.
- `status`: muestra si Pro está instalado y si hay clave, solo con el prefijo `HFST-AB12-...`. Muestra la oferta solo cuando falta alguna de las dos. Sale con 0.
- `PRO_REQUIRED_MESSAGE`: "Already licensed? Install the Pro package from your HefestoAI download email and set HEFESTO_LICENSE_KEY".
- `info` no cambia: sigue requiriendo PRO.
- `skill/commands.md`: describe el comportamiento nuevo.

## Verificación

- Tests nuevos en `tests/test_cli_pro_required_message.py` (activate con y sin Pro, formato inválido, deactivate, status con y sin licencia, la clave nunca se imprime entera).
- Prueba manual con el wheel 3.9.1 instalado: `status` muestra "Pro package: installed".
- Va junto con el PR privado de entrega manual (#115), que ya no menciona `hefesto activate`.

## Agregado: `GIT_DIR` en el hook pre-push

Al actualizar este PR con `main`, el hook pre-push corrió los tests y 2 de `tests/test_pr_review_cli.py` fallaron. Corridos directamente, pasaban.

- **Causa:** git exporta `GIT_DIR` a los hooks. Los `git rev-parse` del test y los `git` de `hefesto/pr_review/orchestrator.py` lo heredaban y miraban el repo del hook en vez del repo temporal. No era solo un problema del test: `hefesto pr-review` lanzado desde un hook leía el repo equivocado.
- **Arreglo:**
  - `_run_git` ahora corre git sin las variables que fijan el repo (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_PREFIX`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`).
  - `tests/conftest.py` tiene un fixture autouse que borra esas variables para todos los tests (también fallaban, dentro del hook, los de `test_pr_review_orchestrator.py`, `test_patch_f_install_hooks.py` y `tests/scripts/test_cobol_corpus_baseline.py`).
  - Test de regresión nuevo: con `GIT_DIR` apuntando a otro repo, `pr-review` sigue leyendo `--project-root`. Sin el arreglo falla; con el arreglo pasa.
- No se usó `--no-verify`.
