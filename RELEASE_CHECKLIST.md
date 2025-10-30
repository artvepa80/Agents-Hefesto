# Hefesto v4.0.1 Release Checklist

## Pre-Release ✅

- [x] Version bumped to 4.0.1 in `hefesto/__version__.py`
- [x] Version bumped to 4.0.1 in `pyproject.toml`
- [x] CHANGELOG.md updated with v4.0.1 entry
- [x] All 118+ tests passing
- [x] Code coverage 85-100% on new modules
- [x] Documentation complete (API, BigQuery setup, architecture)

## Build & Test 🔧

- [ ] Clean previous builds: `rm -rf dist/ build/ *.egg-info`
- [ ] Build distribution: `python3 -m build`
- [ ] Verify wheel and tarball created in `dist/`
- [ ] Test local installation:
  ```bash
  python3 -m venv test_venv
  source test_venv/bin/activate
  pip install dist/hefesto_ai-4.0.1-py3-none-any.whl
  hefesto --version
  hefesto serve &
  sleep 3
  curl http://localhost:8000/health
  deactivate
  rm -rf test_venv
  ```

## PyPI Upload 📦

- [ ] Test PyPI upload: `python3 -m twine upload --repository testpypi dist/*`
- [ ] Verify on Test PyPI: https://test.pypi.org/project/hefesto-ai/
- [ ] Production PyPI upload: `python3 -m twine upload dist/*`
- [ ] Verify on PyPI: https://pypi.org/project/hefesto-ai/
- [ ] Test pip install: `pip install hefesto-ai==4.0.1`

## GitHub Release 🚀

- [ ] Commit all changes to main
- [ ] Create annotated tag: `git tag -a v4.0.1 -m "REST API Release"`
- [ ] Push tag: `git push origin v4.0.1`
- [ ] Create GitHub release at https://github.com/artvepa80/Agents-Hefesto/releases/new
- [ ] Attach `dist/hefesto-ai-4.0.1.tar.gz` to release
- [ ] Copy release notes from CHANGELOG.md

## Post-Release 🎉

- [ ] Update website (hefesto.narapa.app) with v4.0.1
- [ ] Announce on Product Hunt
- [ ] Post on LinkedIn
- [ ] Share on Twitter/X
- [ ] Post on Reddit (r/Python, r/programming, r/devops)
- [ ] Email existing users (if applicable)

## Monitoring 📊

- [ ] Check PyPI download stats (first 24 hours)
- [ ] Monitor GitHub issues for bug reports
- [ ] Track support emails
- [ ] Review user feedback

## Success Metrics (Week 1)

- [ ] 100+ PyPI downloads
- [ ] 50+ GitHub stars
- [ ] 5+ user feedback messages
- [ ] 0 critical bugs reported

---

**Release Date**: 2025-10-30
**Version**: 4.0.1
**Prepared By**: Arturo Vepa
