# 2026-10-16 — pre-push local: ruff alineado con flake8 y mypy no-redef

Handoff. Sin merge. No se tocan tags, releases ni el PR #111.

## Qué fallaba

`ruff check` sin configuración reportaba 1957 hallazgos: el default de Ruff no es el de Flake8 (line-length 88, otro conjunto de reglas, y el árbol entero). CI ejecuta `python -m flake8 hefesto tests` con `.flake8` (`max-line-length = 100`, `extend-ignore = E203, W503`). No hay `setup.cfg` ni `tox.ini`.

`python -m mypy hefesto --ignore-missing-imports` tenía un solo error: `hefesto/analyzers/format_drift.py:82` `[no-redef]`, porque `import black as black_module` redefinía el parámetro `black_module` de la línea 80.

## Qué se hizo

- Black opcional se carga con `importlib.import_module("black")` dentro de `try/except ImportError`. El retorno anotado es `types.ModuleType`. El parámetro del constructor no se vuelve a definir con un `import`. No hay `# type: ignore`: la documentación de `no-redef` dice que, si se silencia, gana la primera definición.
- Tests nuevos en `tests/test_format_check.py`: import real, módulo inyectado, e `ImportError` cuando Black no está.
- `[tool.ruff]` / `[tool.ruff.lint]` en `pyproject.toml`: `line-length = 100`, `target-version = "py310"`, `select = ["E", "W", "F"]`. Ignore: `E203` (el `extend-ignore` del repo) y los default de Flake8 que Ruff sí implementa (`E226`, `E24`). Ruff rechaza selectores que no implementa (`E121`, `E123`, `E126`, `E704`, `W503`, `W504`); esos códigos no pueden dispararse. McCabe no se selecciona: `.flake8` no define `max-complexity`. `ruff` entra en el extra `lint`.
- `extend-exclude = ["scripts", "examples"]`. CI no pasa esas rutas a Flake8. Bajo las mismas reglas, `ruff check scripts examples` da **41** hallazgos y no se tocaron (no es un arreglo mínimo):

  | Código | Cuenta |
  | --- | ---: |
  | F541 | 26 |
  | E501 | 9 |
  | W605 | 3 |
  | F841 | 2 |
  | F401 | 1 |

  Archivos: `examples/basic_usage.py`, `examples/pre_commit_hook.py`, `examples/pro_semantic_analysis.py`, `scripts/verify_capabilities.py`, `scripts/verify_readme.py`, `scripts/verify_release_tag.py`, `scripts/verify_server_json.py`.
- `hefesto/` y `tests/` quedan en 0 hallazgos con esas reglas. No se corrió `ruff --fix`. No hay `per-file-ignores`: no hizo falta dentro del alcance de CI.
- `.github/` y `build_grammars.py` no están excluidos: bajo E/W/F también dan 0.
- CONTRIBUTING documenta los comandos locales de pre-push, incluido el dogfood con el CLI del repo.

## Fuentes abiertas

- https://docs.astral.sh/ruff/configuration/
- https://docs.astral.sh/ruff/linter/
- https://docs.astral.sh/ruff/settings/ (`line-length`, `extend-exclude`, `lint.per-file-ignores`, `lint.select`, `lint.ignore`)
- https://docs.astral.sh/ruff/faq/ (How does Ruff's linter compare to Flake8: todos los `F` y un subconjunto de `E` y `W`)
- https://flake8.pycqa.org/en/latest/user/options.html (`--ignore` por defecto `E121,E123,E126,E226,E24,E704,W503,W504`; `--extend-ignore`; `--max-line-length`)
- https://mypy.readthedocs.io/en/stable/error_code_list.html#check-that-each-name-is-defined-once-no-redef
- https://mypy.readthedocs.io/en/stable/common_issues.html (redefiniciones; `# type: ignore` es para silenciar, no para este caso)
- https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports
- https://mypy.readthedocs.io/en/stable/error_code_list2.html (`try` / `except ImportError` alrededor de un import opcional)
- https://mypy.readthedocs.io/en/stable/stubtest.html (el mismo `try` / `except ImportError` para una dependencia opcional)
- https://peps.python.org/pep-0008/#imports
- https://peps.python.org/pep-0484/ (`Optional` como `Union[..., None]`; `Any` acepta el módulo inyectado en tests)

## Dogfood

CLI del propio repo, distribución `hefesto-ai` 4.19.0 (editable). Los únicos `.py` del PR son `hefesto/analyzers/format_drift.py` y `tests/test_format_check.py`.

```bash
HEFESTO_TELEMETRY=0 python3 -m hefesto analyze hefesto/analyzers/format_drift.py tests/test_format_check.py --severity LOW
```

Exit 0. Salida: 2 archivos analizados, 0 hallazgos, `No issues found! Analysis complete in 0.08s`. Nada que corregir.

## Comandos

Los resultados de guard, ruff, mypy, flake8 y pytest están en el cuerpo del PR. Cada uno salió 0.
