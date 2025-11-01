# Contributing to Hefesto

Thank you for your interest in contributing to Hefesto!

## 🎯 Scope

**Phase 0 (Free - MIT License)**:
- Open for community contributions
- Submit PRs for bugs, features, docs
- No CLA required for MIT-licensed code

**Phase 1 (Pro - Commercial License)**:
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

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linters
black .
isort .
mypy hefesto/
```

## 📝 Code Style

- **Formatter**: Black (line length: 100)
- **Import sorting**: isort
- **Type hints**: Required for all public functions
- **Docstrings**: Google style
- **Testing**: pytest with >80% coverage

## 🧪 Testing Requirements

All PRs must:
- Include tests for new code
- Maintain or improve coverage (currently 96%)
- Pass all existing tests
- Pass linters (black, isort, mypy)

## 📤 Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests
5. Run test suite (`pytest`)
6. Run linters (`black . && isort . && mypy hefesto/`)
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

**Questions?** Email: opensource@narapallc.com

Thank you for making Hefesto better! 🚀

