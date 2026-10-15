# 2026-10-15 — check-test-contradictions: llamadas sin argumentos y entorno

Handoff del fix de la limitación conocida de 4.17.0. Sin merge: espera el OK de Arturo.
No se tocan tags, releases ni el PR #111.

## Causa raíz

`_is_comparable_call` compara una llamada a función plana solo cuando cada
argumento es un literal. Una llamada sin argumentos cumple esa condición de
forma vacía (`all([])` es verdadero): no hay ningún argumento que no sea
literal. El detector agrupaba entonces por `(función, "")` y, si dos tests
esperaban valores distintos, reportaba contradicción. Eso es falso cuando el
resultado depende del entorno que cada test prepara (variable de entorno,
monkeypatch, plataforma, reloj) y no de un argumento. El caso real en este
repo: dos tests de `remote_ping_enabled()` con `HEFESTO_TELEMETRY` distinto;
se unieron en un solo test para no fallar
`test_own_test_suite_has_no_contradictions` (#107). El validador no se tocó
en 4.17.0.

## Qué se hizo

- Una llamada sin argumentos sigue siendo candidata, pero solo se agrupa con
  otra si los hechos de entorno que preceden a la aserción coinciden
  (decoradores incluidos). Hechos: `monkeypatch.setenv` / `delenv` / `setattr`
  y el resto de mutadores de monkeypatch, asignaciones a `os.environ`,
  `patch` / `patch.dict`, `skipif` (solo la condición, no el `reason`),
  un `if` sobre `sys.platform` / `os.name`, y `freeze_time`.
- Una lectura del reloj (`datetime.now()`, `time.time()`, …) sin `freeze_time`
  deja la llamada fuera de la comparación: el reloj no es el mismo input en
  dos tests aunque el fuente sea igual.
- Las llamadas con argumentos literales no cambian: el literal es el input
  aunque el test también toque el entorno.
- Los dos estados de `remote_ping_enabled()` vuelven a ser dos tests
  (`tests/test_readme_telemetry_claim.py`).
- CHANGELOG: sección `[4.17.1] - 2026-10-15`. La versión del paquete sigue en
  4.17.0; esto no es una release.

## Tests

`tests/validators/test_test_contradictions_env.py`. En 4.17.0 (sin el fix)
fallan los que exigen cero contradicciones; los de contradicción real ya
pasaban y siguen pasando.

No es contradicción:

- `monkeypatch.delenv` frente a `setenv` (la reproducción)
- `os.environ["FLAG"] = ...` con valores distintos
- `patch.dict` / `mock.patch.dict` con mapas distintos
- `@pytest.mark.skipif` con condiciones de plataforma distintas
- `if sys.platform` distinto antes del assert
- `@freeze_time` con instantes distintos
- `monkeypatch.setattr` del reloj con lambdas distintas
- `datetime.now()` / `time.time()` sin congelar
- dos asserts seguidos en el mismo test, con un `setenv` entre medias
- el CLI sale 0 en el caso monkeypatch

Sigue siendo contradicción:

- `add(1, 2) == 3` frente a `== 4`
- lo mismo aunque los tests hagan `setenv` distinto, o lean el reloj
- `func() == 1` frente a `== 2` sin entorno
- el mismo `setenv("FLAG", "1")` con expectativas distintas
- el mismo `freeze_time` (aunque el test llame a `datetime.now()`)
- el mismo `skipif` con `reason` distinto
- `assertEqual(func(), 1)` frente a `2`; el par con `setenv` distinto no entra
- `add(a=1, b=2)` con literales por keyword

`test_own_test_suite_has_no_contradictions` cubre el caso real de
`remote_ping_enabled()` dentro de `tests/`.

## Riesgos

- El entorno que solo está en un fixture o en `conftest.py`, sin rastro en el
  test ni en un decorador, no se ve. Esos dos tests siguen comparándose.
- Si la función lee el entorno pero los tests no muestran un setup distinto,
  `func() == 1` frente a `== 2` se sigue reportando. Es el caso que los tests
  viejos tratan como contradicción real; no se puede distinguir de un bug sin
  mirar el cuerpo de la función, y este cambio no sigue imports.
- Cualquier `.setattr` / `.setenv` / `.patch` / `.skip` entra en la huella. Un
  test que hace un `setattr` no relacionado y otro que no lo hace no se
  comparan. Se puede perder una contradicción real; es la misma dirección
  conservadora que 4.17.0 (ante la duda, no comparar).
- El mismo entorno con expectativas distintas sí se reporta. No es un suprimido
  total de las llamadas sin argumentos.
- `skipif` ignora el texto de `reason`. Dos condiciones iguales con razones
  distintas se comparan (y se reportan si el valor esperado cambia).

## Cómo verificar

```bash
python scripts/guard_public_repo.py
python -m ruff check hefesto/validators/test_contradictions.py \
  tests/validators/test_test_contradictions_env.py \
  tests/test_readme_telemetry_claim.py
python -m mypy hefesto --ignore-missing-imports
python -m black --check hefesto tests
python -m isort --check-only hefesto tests
python -m flake8 hefesto tests
HEFESTO_TELEMETRY=0 python -m pytest -q -m "not integration and not slow" \
  tests/validators/test_test_contradictions_env.py \
  tests/validators/test_test_contradictions.py \
  tests/validators/test_test_contradictions_py314.py \
  tests/test_readme_telemetry_claim.py
hefesto check-test-contradictions tests
```

El test de reproducción falla en el código de 4.17.0 y pasa con este cambio.
`ruff check` sin rutas, con el ruff 0.17 por defecto, sigue marcando el resto
del repo (no hay config de ruff; CI usa flake8). No se añadió config.
