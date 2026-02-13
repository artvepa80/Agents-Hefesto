# MEMORY - HefestoAI Project Status

> Last updated: 2026-02-13

---

## PENDING: PyPI Release v4.8.5

**STATUS: BLOCKED - Needs user action**

**Error:** PyPI user `OmegaAI` does not have a verified primary email address.

**Steps to unblock:**
1. Go to https://pypi.org/manage/account/
2. Log in as **OmegaAI**
3. Verify the primary email (check inbox for verification link)
4. Once verified, re-push the tag to trigger the release workflow:
   ```bash
   git push origin :refs/tags/v4.8.5 && git push origin v4.8.5
   ```
   The hardened workflow will now:
   - Publish to PyPI (with continue-on-error)
   - Create/update GitHub Release with build artifacts

**Context:**
- PyPI latest is v4.5.5 (versions 4.6.x - 4.8.x never published due to this email issue)
- Token is valid (stored in GitHub Secrets as `PYPI_API_TOKEN` and GCP Secret Manager)
- Package builds fine, `twine check` passes
- All CI gates pass: verify_release_tag.py, verify_readme.py, 42 tests

---

## Version Alignment (RESOLVED 2026-02-13)

| Location | Version | Status |
|----------|---------|--------|
| VM (installed) | 4.8.5 | OMEGA Guardian, editable install |
| GitHub main | 4.8.5 | pyproject.toml at commit 5e517f1 |
| Tag v4.8.5 | 4.8.5 | Annotated tag at 94de09b |
| GitHub Release | v4.8.5 | Created as Latest |
| OneDrive (local) | 4.8.5 | Synced to origin/main |
| PyPI | 4.5.5 | BLOCKED (email verification) |

---

## Sync Workflow (Single Source of Truth)

**GitHub (origin/main) is the source of truth.**

To resync any working copy:
```bash
git fetch --all --tags
git checkout main
git reset --hard origin/main
git clean -fd
# Verify:
grep "^version" pyproject.toml   # should show 4.8.5
git describe --tags --always      # should show v4.8.5 or ahead
```

---

## Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| **GCP VM** | Active | `34.172.218.79`, user `user`, SSH key `~/.ssh/google_compute_engine` |
| **GCP Project** | Active | `bustling-wharf-478016-p9` |
| **GitHub Repo** | Active | `artvepa80/Agents-Hefesto` |
| **PyPI** | BLOCKED | Email verification needed for OmegaAI account |
| **ClawHub Skill** | Published | `@artvepa80/hefestoai-auditor@1.2.0` |

---

## Release Workflow (Hardened)

The `.github/workflows/release.yml` now:
1. Verifies tag matches pyproject.toml version
2. Builds sdist + wheel
3. Runs twine check
4. Publishes to PyPI (continue-on-error, will not block workflow)
5. Reports PyPI publish status
6. Creates GitHub Release with build artifacts attached (NEW)

---

## Credentials Reference

- **GitHub PAT:** stored in `~/.claude.json` (artvepa80)
- **Stripe API:** stored in `~/.claude.json`
- **PyPI Token:** Stored in GitHub Secrets (`PYPI_API_TOKEN`) and GCP Secret Manager
- **PyPI Account:** `OmegaAI` (needs email verification)
- **VM SSH:** `ssh -i ~/.ssh/google_compute_engine user@34.172.218.79`
