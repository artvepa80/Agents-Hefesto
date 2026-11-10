"""A broken hefesto_pro install must degrade, not crash ``hefesto.pro_optional``."""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fake_pro(root: Path, enrichment_init: str) -> None:
    pkg = root / "hefesto_pro"
    (pkg / "enrichment").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "enrichment" / "__init__.py").write_text(textwrap.dedent(enrichment_init))


def _import_pro_optional(fake_root: Path) -> subprocess.CompletedProcess:
    code = "import hefesto.pro_optional as p; print('HAS_ENRICHMENT', p.HAS_ENRICHMENT)"
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        cwd=fake_root,
        env={"PYTHONPATH": f"{fake_root}:{REPO_ROOT}", "HEFESTO_TELEMETRY": "0"},
    )


def test_broken_enrichment_import_warns_and_continues(tmp_path: Path) -> None:
    _fake_pro(tmp_path, "from .missing_module_attr import nothing  # noqa\n")
    (tmp_path / "hefesto_pro" / "enrichment" / "missing_module_attr.py").write_text("")
    proc = _import_pro_optional(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "HAS_ENRICHMENT False" in proc.stdout
    assert "hefesto_pro is installed but enrichment failed to import" in proc.stderr
    assert "ImportError" in proc.stderr


def test_license_required_stays_silent(tmp_path: Path) -> None:
    # ProLicenseRequired subclasses ModuleNotFoundError: no warning, just fallback.
    _fake_pro(
        tmp_path,
        """
        class ProLicenseRequired(ModuleNotFoundError):
            pass

        raise ProLicenseRequired("hefesto_pro.enrichment requires a license")
        """,
    )
    proc = _import_pro_optional(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "HAS_ENRICHMENT False" in proc.stdout
    assert "enrichment failed to import" not in proc.stderr


def test_missing_pro_dependency_warns(tmp_path: Path) -> None:
    # PRO is installed but one of its own dependencies is missing: warn, not silent.
    _fake_pro(tmp_path, "import some_missing_pro_dependency_xyz  # noqa\n")
    proc = _import_pro_optional(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "HAS_ENRICHMENT False" in proc.stdout
    assert "hefesto_pro is installed but enrichment failed to import" in proc.stderr
    assert "some_missing_pro_dependency_xyz" in proc.stderr


def test_missing_pro_submodule_stays_silent(tmp_path: Path) -> None:
    # A hefesto_pro submodule that is not shipped counts as "not installed".
    (tmp_path / "hefesto_pro").mkdir()
    (tmp_path / "hefesto_pro" / "__init__.py").write_text("")
    proc = _import_pro_optional(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "HAS_ENRICHMENT False" in proc.stdout
    assert "failed to import" not in proc.stderr


def test_pro_not_installed_stays_silent(tmp_path: Path) -> None:
    proc = _import_pro_optional(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "HAS_ENRICHMENT False" in proc.stdout
    assert "failed to import" not in proc.stderr
