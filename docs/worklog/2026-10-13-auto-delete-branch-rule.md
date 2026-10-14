# 2026-10-13 — CLAUDE.md: auto-delete de ramas de PR

- `delete_branch_on_merge` del repo = `true` (API). Al squash-mergear #105 y #101 hoy, sus
  ramas desaparecieron solas (API 404), sin borrado a mano.
- CLAUDE.md línea 59 decía que borrar "a PR branch after merge" requería OK explícito, lo que
  contradice el auto-delete. Se quita ese paréntesis y se añade la regla de Arturo:
  "PR head branches are deleted by the repository's auto-delete setting when a PR is merged;
  Arturo's merge OK covers that. Never delete a branch by hand without explicit OK."
- Ruleset 15985908 aplicado hoy con OK de Arturo: 13 checks requeridos (4 multilang-smoke,
  4 lint-and-test, wheel-leak-check, smoke-test, readme-parity, capabilities-check,
  corpus-baseline). Rollback: `/workspace/ruleset-15985908-actual.json` (fuera del repo).
- Solo docs; no se mergea sin OK.
