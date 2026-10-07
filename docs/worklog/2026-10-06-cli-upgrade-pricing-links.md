# 2026-10-06: Enlaces de upgrade del CLI y docs → oferta actual (#pricing)

- **Contexto:** LIC plan PR 3, parte pública. Los enlaces de pago antiguos
  (`…eAg04` prueba $99/mes, `…eAg05` fundador $59, `…eAg03` anual $990) están
  **inactivos** en Stripe. La oferta vigente es PRO $8/mes y OMEGA $19/mes, ambos
  con 14 días de prueba, en `https://hefestoai.narapallc.com/#pricing`.
- **Rama:** `fix/cli-upgrade-pricing-links`, desde `main` @ `04b5e8d` (v4.14.1).
  Sin cambio de versión ni tag.
- **PRs relacionados (privado):** #104 (webhook de Stripe) y #105 (redirige
  `/trial`, `/founding` y `/annual` a `/#pricing` y corrige los mensajes del CLI PRO).

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `hefesto/cli/main.py` | Nuevas constantes `PRICING_URL` y `PRO_REQUIRED_MESSAGE`. Los 5 avisos "requires Hefesto PRO/OMEGA" (`serve` sin PRO, `info`, `activate`, `deactivate`, `status`) muestran precios, prueba de 14 días, la URL de `#pricing` y "Already licensed? Install Hefesto PRO from the private distribution." |
| `README.md` | La sección de precios enlazaba a `/trial` y `/founding` y decía "no credit card" para PRO, aunque su checkout exige tarjeta (`payment_method_collection: always`). Ahora enlaza a `#pricing`. Se quita la línea de "Founding Members" (no hay cupón extra) |
| `docs/GETTING_STARTED.md`, `INTEGRATION.md`, `INSTALLATION.md`, `QUICK_START.md`, `LICENSE_GATES.md` | Los enlaces de ejemplo inventados (`buy.stripe.com/hefesto-pro`, `pro-link`, `omega-link`, un enlace antiguo `…4gMfZg…`, `hefesto.ai/pricing`, `support@narapa.com`) se cambian por `#pricing` y `support@narapallc.com` |
| `examples/basic_usage.py`, `examples/pro_semantic_analysis.py` | Igual (enlace inventado → `#pricing`) |
| `CLAUDE.md` | Los enlaces de Stripe estaban truncados (no abrían). Ahora apuntan a `#pricing` y a los enlaces completos vigentes `…eAg0b` (PRO) y `…eAg0c` (OMEGA) |
| `scripts/README.md` | Los precios $25/$35/$49 pasan a ser PRO $8 y OMEGA $19 (precio fundador, sin cupón) |
| `tests/test_cli_pro_required_message.py` (nuevo, 5 casos) y `tests/test_pro_wiring.py` | Comprueban que el mensaje lleva la URL y los precios, y que `info`, `status` y `deactivate` salen con código 1 y lo muestran |

## Cómo verificar

```bash
CI=true PYTHONPATH=. HEFESTO_TELEMETRY=0 python -m pytest -q -m "not integration and not slow"
python -m black --check hefesto tests && python -m isort --check-only hefesto tests && python -m flake8 hefesto tests
hefesto info    # → exit 1 con el mensaje nuevo y la URL de #pricing
```

En local: 713 passed, 7 skipped y 1 fallo **ajeno** (`test_version_drift`: el venv local
tiene instalada la distribución 4.13.1; en CI se instala el repo). black 26.1.0, isort,
flake8 y mypy (`hefesto/cli/main.py`) sin errores. `hefesto analyze` solo reporta hallazgos
MEDIUM previos en funciones que no se tocaron.

## Pendiente

- Decisión de Arturo (2026-10-06): los precios son solo PRO $8 y OMEGA $19, sin cupón
  fundador extra. Por eso el README ya no menciona `Founding40` y `scripts/README.md` no cita
  $4.80. Él desactivará los cupones en Stripe.
- El README ya no promete "no credit card" para PRO (el checkout de PRO exige tarjeta). Arturo
  revisará el resto de textos "no credit card" (landing) por su cuenta.
- `README.md:516` y `skill/commands.md:150` siguen hablando de la "private distribution".
  Es correcto: describen cómo instalar PRO, no cómo comprarlo.
