# Plan de Implementación: Características Competitivas
## Hefesto v4.9.0

**Fecha:** 2026-02-13  
**Enfoque:** Socrático-Adaptivo según CLAUDE.md

---

## Objetivo

Implementar 4 características competitivas:

1. **Autofix** (ALTA) - Competir con Semgrep/Snyk
2. **Métricas Performance** (ALTA) - Transparencia
3. **Detección Código IA** (MEDIA) - Tendencias 2025
4. **Reglas Personalizadas** (MEDIA) - Flexibilidad

---

## Suposiciones Seguras

1. Autofix primero (mayor impacto)
2. Aprovechar `propose_patch()` existente
3. Features opt-in (no breaking changes)
4. Autofix en PRO, Métricas en FREE
5. Testing 4 niveles según CLAUDE.md

---

## Preguntas Críticas

**Q1:** ¿Autofix completo o solo generación?

**A:** Ambos: `--suggest-fixes` (FREE) y `--auto-fix` (PRO)

**Q2:** ¿Métricas públicas o internas?

**A:** Ambas: CLI `hefesto benchmark` + README público

---

## Fases

### FASE 1: Autofix (Semanas 1-3)

**Semana 1:** Infraestructura base

- TDD scaffold y modelos (PatchProposal, PatchResult, PatchContext)
- Tests unitarios (3 tests fallando → implementar → pasar)
- PatchGenerator (integrar con LLMProvider.propose_patch)

**Semana 2:** Validación y aplicación

- PatchValidator (reutilizar SuggestionValidator)
- PatchApplier con backup/rollback
- CLI integration (`--suggest-fixes`, `--auto-fix`, `--dry-run`)

**Semana 3:** Testing y docs

- Tests Canary (dogfooding)
- Tests Empíricos (benchmarks)
- Documentación (README, docs/AUTOFIX.md)

**Criterios:**

- 80%+ patches válidos
- <500ms por archivo
- Tests 100% passing

---

### FASE 2: Métricas (Semanas 4-5)

**Semana 4:** Sistema de métricas

- PerformanceMetrics module
- Benchmark CLI (`hefesto benchmark`)
- Métricas por lenguaje

**Semana 5:** Reportes

- Benchmark reporter
- README actualizado
- CI integration

**Criterios:**

- Métricas automáticas
- README con benchmarks
- CI actualiza métricas

---

### FASE 3: Detección IA (Semanas 6-7)

**Semana 6:** Detección

- AICodeDetector module
- Pattern analysis
- Integración SecurityAnalyzer

**Semana 7:** Reportes

- AI detection report
- Documentación

**Criterios:**

- >90% precisión Copilot
- Reporta % código IA

---

### FASE 4: Reglas (Semanas 8-10)

**Semana 8:** Parser

- CustomRuleLoader (YAML)
- Rule schema
- Rule validator

**Semana 9:** Motor

- RuleEngine
- CLI integration

**Semana 10:** Docs

- Documentación completa
- Ejemplos

**Criterios:**

- Reglas YAML funcionales
- Ejecución durante análisis
- Docs con ejemplos

---

## Estructura propuesta

```
hefesto/
├── autofix/
│   ├── __init__.py
│   ├── patch_generator.py
│   ├── patch_applier.py
│   ├── patch_validator.py
│   └── models.py
├── metrics/
│   ├── __init__.py
│   ├── performance.py
│   ├── benchmark.py
│   └── reporter.py
├── rules/
│   ├── __init__.py
│   ├── custom_rule_loader.py
│   ├── rule_engine.py
│   └── rule_validator.py
└── ai_detection/
    ├── __init__.py
    ├── copilot_detector.py
    └── ai_pattern_analyzer.py
```

---

## Testing (4-Level Pyramid)

1. **Unit:** >90% cobertura
2. **Smoke:** Inicialización
3. **Canary:** Dogfooding
4. **Empirical:** Benchmarks

---

## Métricas de Éxito

**Técnicas:**

- Autofix: >80% éxito, <500ms/archivo
- AI Detection: >90% precisión

**Negocio:**

- Top 3 competitivo
- +25% adopción usuarios

---

## Lanzamiento

- **v4.9.0-alpha** (Semana 3): Autofix básico
- **v4.9.0-beta** (Semana 5): Autofix + Métricas
- **v4.9.0-rc.1** (Semana 7): + Detección IA
- **v4.9.0** (Semana 10): Release completo

---

## Riesgos

1. **Autofix bugs:** Validación + rollback
2. **Performance:** Benchmarking continuo
3. **Reglas complejas:** Schema simple

---

## Próximos Pasos

1. Confirmar prioridades (Hoy)
2. Setup desarrollo (Día 1)
3. Iniciar Fase 1 (Día 2)

---

*Metodología: Socrático-Adaptivo según CLAUDE.md*

*Copyright © 2025 Narapa LLC, Miami, Florida*
