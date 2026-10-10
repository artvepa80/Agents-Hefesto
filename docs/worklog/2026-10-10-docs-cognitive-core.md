# 2026-10-10 — Documento cognitive-core (PR #54)

## Qué se hizo

1. **Rama al día con `main`.** El PR #54 salió de `dea23f7`, justo después del #53, que había quitado la línea `Version: X.Y.Z` de `skill/SKILL.md`. Por eso `scripts/verify_readme.py` fallaba con `skill/SKILL.md (skill metadata): pattern not found` en README Parity y en CI / lint-and-test (3.10–3.13). El #55 ya lo había corregido en `main`; bastó con mergear `main` en la rama. El contenido del documento no tenía nada que ver con el fallo.
2. **Sin Kronos.** Se quitaron todas las menciones a Kronos de `docs/cognitive-core.md`: la frase de la introducción, la sección "Kronos (brief)" (que describía públicamente el proyecto, su exchange y su hosting) y los dos no-objetivos que lo nombraban. El documento queda solo sobre HefestoAI. El título y la descripción del PR también se cambiaron.
3. **CHANGELOG.** Entrada en `[Unreleased] / Added`.

## Qué no cambia

- Código: ninguno. Es solo documentación.
- Los cinco casos de dogfood y el mapeo core/memoria quedan igual.

## Verificación

- `python scripts/verify_readme.py` → All checks passed (4.14.1, 22 formatos).
- `python scripts/verify_capabilities.py` → SUCCESS.
- `grep -i -E "kronos|railway|hyperliquid|trading" docs/cognitive-core.md` → sin resultados.
- Enlaces del documento comprobados: `skill/SKILL.md`, `docs/ai-discovery.md`, #53, arXiv 2609.00006.

## Nota

El commit original del PR (`4e4dc04`) todavía contiene el texto con Kronos. Como el PR se mergea con squash, ese texto no llega a `main`, pero sigue visible en el historial del PR en GitHub.
