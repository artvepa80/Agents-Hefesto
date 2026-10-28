# Contributing to Hefesto

Thank you for your interest in contributing to Hefesto!

## 🎯 Scope

**Phase 0 (Free - MIT License)**:
- Open for community contributions
- Submit PRs for bugs, features, docs
- No CLA required for MIT-licensed code

**Phase 1 (Pro - Commercial License, see [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md))**:
- Closed source, proprietary code
- Bug reports welcome via GitHub Issues
- Managed by Narapa LLC team

## 🐛 Reporting Bugs

1. Check existing issues first
2. Use issue template
3. Include:
   - Hefesto version (`hefesto --version`)
   - Python version
   - Operating system
   - Minimal reproduction code
   - Expected vs actual behavior

## 💡 Suggesting Features

1. Open GitHub Discussion first
2. Explain use case and business value
3. Consider if it's Phase 0 (free) or Phase 1 (pro) feature
4. Wait for maintainer feedback before implementing

## 🔧 Development Setup

```bash
# Clone repository
git clone https://github.com/artvepa80/Agents-Hefesto.git
cd Agents-Hefesto

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode (the lint extra provides black, flake8, isort, ruff)
pip install -e ".[dev,lint]"

# Run tests
pytest

# Local pre-push checks (same commands as CI for guard, mypy, and flake8;
# ruff enforces the flake8 rule set from pyproject.toml)
python scripts/guard_public_repo.py
ruff check
python -m mypy hefesto --ignore-missing-imports
python -m flake8 hefesto tests

# Dogfood the Python files this change touches (this repo's CLI, hefesto-ai 4.20.4)
HEFESTO_TELEMETRY=0 python -m hefesto analyze <changed.py> --severity LOW

# Changed-file gate (CI: .github/workflows/dogfood.yml, job dogfood-hefesto).
# ruff check --force-exclude (no --fix) on the changed .py files, then hefesto
# on the changed files except those matching `exclude` in .hefesto.yaml
# (path components, not globs; the script filters explicit paths itself, and
# falls back to tests/fixtures/ and .github/action-smoke/ without the file):
HEFESTO_TELEMETRY=0 python -m hefesto analyze <changed files> \
  --severity medium --fail-on critical --allow-no-files
# Proves a planted CRITICAL fails and the current hefesto/ tree has no
# CRITICAL findings (the PostHog public key is reported as LOW).
# One tracked file fails the gate when touched:
# scripts/validate_aggregates_jsonl.py:48 (VERY_HIGH_COMPLEXITY, until split):
python scripts/dogfood_changed.py --self-check

# Verify version parity (pyproject.toml vs README, llms.txt, server.json,
# agent-card.json, SKILL.md, copilot-instructions.md — also runs in CI)
python scripts/verify_readme.py

# Validate server.json against the official MCP registry schema (also in CI)
python scripts/verify_server_json.py
```

## 📝 Code Style

- **Formatter**: Black (line length: 100)
- **Import sorting**: isort
- **Type hints**: Required for all public functions
- **Docstrings**: Google style
- **Testing**: pytest with >80% coverage
- **Parsing analyzed Python**: call `hefesto.core.safe_parse.safe_parse` (or `parse_or_none`), never `ast.parse` directly. It keeps compiler warnings off stderr and makes the result independent of `PYTHONWARNINGS` / `-W`; `tests/test_safe_parse.py` fails on any other `ast.parse(` call under `hefesto/`.

## 🧪 Testing Requirements

All PRs must:
- Include tests for new code
- Maintain or improve coverage (currently 96%)
- Pass all existing tests
- Pass linters (black, isort, ruff, flake8, mypy)
- Run the local pre-push checks in Development Setup

### Cursor agents and HefestoAI dogfooding

`.cursor/mcp.json` registers the hosted `hefestoai` MCP server, and
`.cursor/rules/hefesto-dogfood.mdc` (always applied) asks Cursor agents to analyze
every changed file and report the result in the PR. Human contributors follow the
same rule: run `HEFESTO_TELEMETRY=0 hefesto analyze <changed files>` and paste the
command and output under a `Dogfood` heading in the PR body. Cloud agents only get
the MCP server if it is added in cursor.com/agents (MCP dropdown) or
Dashboard > Plugins & MCPs; otherwise they use the CLI.

## 📤 Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests
5. Run test suite (`HEFESTO_TELEMETRY=0 python -m pytest -q -m "not integration and not slow"`)
6. Run the local pre-push checks:
   `python scripts/guard_public_repo.py`
   `ruff check`
   `python -m mypy hefesto --ignore-missing-imports`
   `python -m flake8 hefesto tests`
   `HEFESTO_TELEMETRY=0 python -m hefesto analyze <changed files> --severity medium --fail-on critical --allow-no-files`
   `python scripts/dogfood_changed.py --self-check`
7. Commit (`git commit -m 'feat: Add amazing feature'`)
8. Push (`git push origin feature/amazing-feature`)
9. Open Pull Request

### Commit Message Format

Follow Conventional Commits:

```
feat: Add new feature
fix: Fix bug
docs: Update documentation
test: Add tests
refactor: Refactor code
chore: Update dependencies
```

Co-author trailers: your own `Co-authored-by` lines for people who worked on the change are welcome. Commits made with the maintainer's tooling carry only `Co-authored-by: HefestoAI <noreply@narapallc.com>`. CI rejects commits whose author or co-author names an internal automation identity (`python scripts/guard_public_repo.py --check-commits origin/main..HEAD`).

## 🔒 Security

For security vulnerabilities:
- **DO NOT** open public issues
- Email: support@narapallc.com
- We'll respond within 48 hours
- Fix will be released ASAP

## 📜 License Agreement

By contributing to Phase 0 (MIT-licensed code), you agree that your contributions will be licensed under the MIT License.

Phase 1 (Pro) code is proprietary and cannot be contributed to without a written agreement with Narapa LLC.

## 🙏 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Thanked in our documentation

---

**Questions?** Email: support@narapallc.com

Thank you for making Hefesto better! 🚀

