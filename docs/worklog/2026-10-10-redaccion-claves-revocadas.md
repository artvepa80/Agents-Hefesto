# 2026-10-10 — Claves de licencia revocadas fuera de la documentación

## Contexto

En la auditoría de ramas apareció que `main` todavía mostraba dos claves internas de licencia OMEGA, revocadas el 2026-10-06:
- `CHANGELOG.md:1959`, en la entrada del fix de OMEGA ("Verified with real OMEGA license (…)"), con el prefijo `HFST-6F06-`.
- `scripts/README.md:183` y `:192`, en el ejemplo de salida de `fulfill_order.py`, con el prefijo `HFST-A2F4-`.

`CHANGELOG.md` va dentro del sdist (`MANIFEST.in`). Por eso las 27 versiones publicadas entre la 4.2.1 y la 4.14.1 llevan la clave dentro del sdist. Las claves ya no sirven, pero cada release nuevo la seguía publicando.

## Qué se hizo

1. Las tres apariciones pasan a `HFST-XXXX-XXXX-XXXX-XXXX-XXXX`, el mismo placeholder que ya usa el resto de la documentación.
2. Test nuevo, `tests/test_no_license_keys_in_repo.py`: recorre los archivos de texto del repo y falla si aparece una clave `HFST-…` distinta del placeholder o del ejemplo inventado `HFST-1234-5678-9ABC-DEF0-1234`. El mensaje de error muestra solo el prefijo.
3. CHANGELOG: entrada en `[Unreleased] / Security`.

## Qué no se hizo

- **No se reescribió la historia.** Los commits viejos siguen teniendo las claves. Purgar el repo público no se recomienda: 2 forks y PyPI ya tienen copias, y reescribir cambiaría los SHAs de 36 tags. Ver `runbook-purga-historial.md`, fuera del repo.
- Los sdists ya publicados en PyPI no se tocan.

## Verificación

- `git grep -E 'HFST-(6F06|A2F4|07C1)-'` sin resultados.
- `python -m build --sdist` en local: el sdist nuevo no contiene esas claves.
- `pytest tests/test_no_license_keys_in_repo.py`, en verde.
