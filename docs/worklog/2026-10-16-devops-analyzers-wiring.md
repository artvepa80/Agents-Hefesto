# 2026-10-16 — nueve analizadores conectados a `hefesto analyze`

Handoff. Sin merge. No se tocan tags, releases, PyPI ni el PR #111. La versión del paquete sigue en 4.19.0. El cambio es el trabajo no publicado de 4.20.0.

## Qué faltaba

`JsonAnalyzer`, `TomlAnalyzer`, `PowerShellAnalyzer`, `MakefileAnalyzer`, `GroovyJenkinsAnalyzer`, `CloudFormationAnalyzer`, `ArmAnalyzer`, `HelmAnalyzer` y `ServerlessAnalyzer` ya existían y tenían tests de módulo. No había `LanguageSpec` para ellos (salvo que Terraform ya cubría `*.tf.json`), así que `hefesto analyze config.json` decía cero archivos. El README lo decía en la nota al pie ².

## Qué se hizo

- Diseño en `docs/design/devops-analyzers-wiring.md`, escrito antes del dispatch. Cita solo páginas abiertas. Tabla de precedencia, alternativas rechazadas y conteos de ruido antes y después.
- `hefesto/core/languages/content_classify.py` elige un idioma cuando el sufijo es compartido. `registry.py` no deja que el glob `*.json` de ARM pise el de JSON.
- `analyzer_engine.py` despacha esos nueve idiomas y siempre devuelve un resultado, aunque no haya hallazgos. Los lockfiles generados entran en `DEFAULT_EXCLUDES`. Un path nombrado en la línea de comandos se sigue analizando.
- JSON y TOML comparan claves por tokens (`hefesto/analyzers/devops/key_match.py`). Los hijos inmediatos de `dependencies` y mapas parecidos no son secretos. MF002 ignora `curl | sh` entre comillas.
- `hefesto/analyzers/cloud/adapt.py` convierte `CloudFinding` en `AnalysisIssue`. Los analizadores cloud reciben `(content, path)`.
- Tests de CLI en `tests/test_devops_dispatch.py`. Antes del dispatch: 14 fallos (`files_analyzed` 0). Después: pasan.
- README (también zh-CN y ja), `llms.txt`, `.well-known/agent-card.json`, `skill/SKILL.md`, `capabilities.yml` y `CHANGELOG.md` dicen que `hefesto analyze` corre los 22 formatos. JSON queda en cuatro reglas: J001, J002, J004, J005. No hay J003 en el código.

## Ruido medido

Mismos commits. Antes: dispatch ingenuo, substring, sin excluir lockfiles. Después: el motor.

| Repo | SHA | Antes | Después |
| --- | --- | --- | --- |
| Este repo | `0e2c140` | JSON 6, TOML 1, 0 hallazgos | igual |
| helm/helm | `9b88efd62a6908fb11215f8e8b50c3c62a246df0` | MF002 ×2, HELM_S001 ×1 | HELM_S001 ×1 |
| python-poetry/poetry | `38a86661d2ae58694c76d0bb4e628e1400d6dc6f` | J001 ×98, J002 ×1 | J002 ×1 |
| serverless/serverless | `a61c2187afb6d9f01517065d115c38d3eb107e43` | JSON 104, J001 ×79, CFN_I001 ×4 | JSON 98, J001 ×2, CFN_I001 ×4 |

Los 6 JSON que ya no se abren en serverless son `package-lock.json`. Quedan HELM_S001 (`tlsSecret` en testdata), J002 (`download_url` HTTP en un fixture de PyPI), J001 (`resultToken`, `Postman-Token`) y CFN_I001 (buckets S3 sin `PublicAccessBlockConfiguration`). No se reescribieron esas reglas.

## Qué queda fuera

- La tarjeta del landing privado (`landing-page/api/agent-card.js`) compara este `.well-known/agent-card.json`. Hay que actualizarla o el test de paridad del repo privado falla. Este PR no puede tocar ese repo.
- `ArmAnalyzer` sigue sin analizar YAML y sin recorrer `resources` como objeto (`languageVersion` 2.0).
- No se inventó J003 ni el catálogo de PSScriptAnalyzer.
