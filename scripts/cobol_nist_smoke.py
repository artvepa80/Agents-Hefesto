#!/usr/bin/env python3
"""Crash/timing smoke test of the COBOL analyzer against the NIST COBOL85 suite.

The suite is NOT vendored in this repo. It is downloaded on demand (the same
mirror GnuCOBOL's test suite uses) into a temporary or given directory,
split into its programs and copybooks, and each one is analyzed in-process.

Usage:
    python scripts/cobol_nist_smoke.py [--workdir DIR] [--newcob PATH]

Exit code 1 if any member raises an exception. Not run in CI (network).
"""

import argparse
import collections
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

URL = "https://gnucobol.sourceforge.io/files/newcob.val.tar.gz"


def fetch(workdir: Path) -> Path:
    target = workdir / "newcob.val"
    if target.exists():
        return target
    archive = workdir / "newcob.val.tar.gz"
    urllib.request.urlretrieve(URL, archive)  # noqa: S310 - fixed https URL
    with tarfile.open(archive) as tar:
        member = tar.getmember("newcob.val")
        tar.extract(member, workdir)
    return target


def split_members(newcob: Path):
    """Yield (kind, name, text). Members start with *HEADER,<kind>,<name>."""
    kind = name = None
    buf = []
    for line in newcob.read_text(encoding="latin-1").splitlines():
        if line.startswith("*HEADER,"):
            if name:
                yield kind, name, "\n".join(buf) + "\n"
            parts = line.split(",")
            kind, name = parts[1].strip(), parts[2].strip()
            buf = []
        elif line.startswith("*END-OF,"):
            continue
        elif name:
            buf.append(line[:80])
    if name:
        yield kind, name, "\n".join(buf) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--newcob", type=Path, help="Existing newcob.val file")
    args = parser.parse_args()

    from hefesto.analyzers.devops.cobol_governance_analyzer import CobolGovernanceAnalyzer

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="nist-cobol85-"))
    workdir.mkdir(parents=True, exist_ok=True)
    newcob = args.newcob or fetch(workdir)

    analyzer = CobolGovernanceAnalyzer()
    kinds = collections.Counter()
    rules = collections.Counter()
    formats = collections.Counter()
    crashes = []
    slowest = (0.0, "")
    total_lines = 0
    start_all = time.perf_counter()
    for kind, name, text in split_members(newcob):
        if kind not in ("COBOL", "CLBRY"):
            continue  # data files, JCL-like members
        kinds[kind] += 1
        total_lines += text.count("\n")
        filename = f"{name}.CPY" if kind == "CLBRY" else f"{name}.CBL"
        t0 = time.perf_counter()
        try:
            issues = analyzer.analyze(filename, text)
        except Exception as exc:  # noqa: BLE001 - we are hunting crashes
            crashes.append((name, repr(exc)))
            continue
        elapsed = time.perf_counter() - t0
        slowest = max(slowest, (elapsed, name))
        formats[analyzer.last_format_reason] += 1
        rules.update(i.rule_id for i in issues)

    total = time.perf_counter() - start_all
    print(f"members analyzed: {dict(kinds)}  lines: {total_lines}")
    print(f"total time: {total:.2f}s  slowest: {slowest[1]} {slowest[0] * 1000:.1f} ms")
    print(f"format decisions: {dict(formats)}")
    print(f"findings by rule: {dict(sorted(rules.items()))}")
    print(f"crashes: {len(crashes)}")
    for name, err in crashes[:20]:
        print(f"  {name}: {err}")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main())
