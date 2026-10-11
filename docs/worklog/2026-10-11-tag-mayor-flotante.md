# 2026-10-11 — Tag mayor flotante `v4` para la GitHub Action

## Decisión

Arturo decidió (dom 11 oct, 3:11 PM Lima) publicar un tag flotante `v4` y moverlo en cada
release v4.x.y, para que `uses: artvepa80/Agents-Hefesto@v4` reciba los arreglos sin editar
el workflow. Motivo: la Action instala HefestoAI desde su propio ref, así que quien quedó en
`@v4.15.0` conserva el bug de exclusiones aunque 4.15.1 esté en PyPI.

## Tipo de tag: liviano

`v4` es un tag liviano (apunta directo al commit). Es lo que usan las Actions oficiales
(`actions/checkout` y `actions/setup-python`: el ref `v4` es de tipo `commit`) y la guía de
versionado de Actions solo pide que el ref resuelva a un commit. Un tag anotado guardaría
un mensaje y un autor que quedan viejos en cada movimiento, y lo confundiría con un release.
Los tags exactos (`v4.15.1`, ...) siguen anotados y no se mueven nunca.

## Cambios en este PR

- `release.yml`:
  - Último paso nuevo, "Move floating major tag". Si el tag es `vX.Y.Z` y es el `v4.x.y`
    más alto en `origin`, hace `git tag -f v4 $GITHUB_SHA` y `git push -f` con el
    `GITHUB_TOKEN` del job (`contents: write`).
  - Solo actúa sobre tags `v4.x.y`: `v4` es la única excepción a "nunca mover tags"; un
    futuro `v5` necesitaría su propia decisión. Un patch viejo no mueve `v4` hacia atrás.
    Tampoco lo mueven los RC ni el propio `v4`.
  - El filtro `!v4` evita que el push de `v4` dispare otro release.
  - Probado en local con un repo bare: v4.15.1 mueve el tag; v4.14.1, `v4` y
    v4.16.0-rc.1 no lo mueven.
- `scripts/verify_readme.py`: el ref de la Action puede ser el mayor (`@v4`, debe coincidir
  con el mayor de `pyproject.toml`) o la versión exacta. Tests nuevos para `@v4`, para un
  mayor equivocado y para que el mayor no valga fuera de los refs de la Action.
- Ejemplos a `@v4`: README, `docs/github-action.md` (nueva sección "Versions"),
  `skill/integration.md`, `llms.txt` y las instrucciones de Copilot. Se menciona que
  `@v4.15.1` sigue disponible.
- `CLAUDE.md`: el tag `v4` (alias flotante de la línea 4.x) se nombra como la única
  excepción a "nunca mover tags", con un fallback manual. No hay regla genérica para tags
  mayores.
- README, `docs/github-action.md` y CHANGELOG dicen explícitamente que `@v4` sigue toda la
  línea 4.x, minors incluidas, y por eso recibe cambios de comportamiento (por ejemplo el
  cambio de exit code con cero archivos). Para estabilidad exacta: `@v4.15.1`.
- `CHANGELOG.md` (`[Unreleased]`): nota para quien está en `@v4.15.0`.
- El push del workflow se hizo con el token con scope `workflow`.

## Protección de tags (revisada antes de crear `v4`)

- Rulesets del repo: "HefestoAI" (branch, desactivado) y "main branch protection" (branch,
  solo `refs/heads/main`). `rulesets?targets=tag` devuelve `[]`: no hay rulesets de tags.
- Protección legacy de tags: `GET /repos/.../tags/protection` responde 404 (la API ya no
  existe en GitHub y no hay reglas `v*`, `v4*` ni `v4.*`).
- Conclusión: nada bloquea mover `v4` a mano ni desde el workflow. No se cambió ninguna
  protección.
- Opcional, para más adelante y solo con aprobación: un ruleset de tags que proteja
  `refs/tags/v4.*.*` contra update y deletion. No tocaría `v4`.

## Pasos fuera del PR

- Tag `v4` creado sobre `579544f` (el commit de v4.15.1) y empujado después del merge, para
  que el filtro nuevo ya esté en `main`.
- `/workspace/hefesto-cobol-ci-example` pasa a `@v4` (commit local, sin remoto).

## Para mañana (no hecho)

- #91 (head `b97107c`): confirmar verde. Luego agregar a la salida la línea
  "N files skipped as vendored (use --include-vendored)".
- #91 y #85 salen juntos en 4.16.0, no en 4.15.2.
- Las notas de 4.16.0 (CHANGELOG, highlights del README y GitHub Release) deben ABRIR con el
  cambio de exit code de #85 (una corrida con cero archivos ya no pasa con `--fail-on`).
  Los usuarios de `@v4` lo reciben automáticamente.

## Resultado (2026-10-11)

- #92 squash-merge `34549fad7dd1c5156742fbca357e4e35dc63a7c5` (15 checks verdes). CI de
  `main` verde en ese SHA: CI, CodeQL, Action Smoke Test, Multilang Extra Smoke, README Parity
  y Capabilities Parity.
- Tag liviano `v4` → `579544fe945974443a6323780b043244d6e920bb` (v4.15.1).
  `git/ref/tags/v4` es de tipo `commit`. `v4.15.1` sigue anotado (objeto `639e675`) y no se
  tocó.
- Resolución verificada:
  - `commits/v4` devuelve `579544f`.
  - El tarball que baja el runner (`codeload .../tar.gz/v4`) trae `action.yml` composite y
    `version = "4.15.1"`.
  - Emulé los pasos de la Action desde ese tarball sobre el ejemplo COBOL: instala
    hefesto 4.15.1, analiza 5 archivos y encuentra 7 hallazgos.
  - Con `fail_on: CRITICAL` el gate falla a propósito (`exit_code=1`) y escribe SARIF 2.1.0
    con 7 resultados.
- Efecto conocido del primer push de `v4`:
  - GitHub corrió los workflows de `579544f`, cuyo `release.yml` todavía no tenía el filtro
    `!v4`.
  - "Release (PyPI)" falló en "Verify release tag" (`4` != `4.15.1`), antes de build, PyPI y
    GitHub Release: no se publicó nada y no existe una release `v4`.
  - "CI" sobre `v4` pasó.
  - Los movimientos futuros salen del workflow con `GITHUB_TOKEN`, que no dispara
    workflows, y `!v4` los filtra igual.
- Repo de ejemplo COBOL: `@v4`, con un comentario que remite a `@v4.15.1` para estabilidad
  exacta (commit local `c5f7b7b`, sin remoto).
- #91: head `b97107c`, 16 checks verdes (confirmado el 11 oct). Pendiente para mañana: la
  línea "N files skipped as vendored (use --include-vendored)".
