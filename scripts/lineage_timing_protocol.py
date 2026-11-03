"""Pre-registered timing protocol for the JCL part of ``--lineage``.

One run of this script is the measurement. It does, in order:

1. Records the commit SHA of ``--repo``, the sha256 of this file, the machine
   and the Python version.
2. Generates the seeded synthetic JCL trees (seed 7): 2,000, 4,000, 8,000 and
   16,000 jobs, each job 4 ``EXEC PGM`` steps and 1 PROC call (2 PROC steps),
   so 6 JCL steps per job; 20 PROCs and 500 COBOL programs.
3. Flag-off check on every size: JSON (timing fields removed) and SARIF of
   ``--repo`` without ``--lineage`` equal to ``--main``, and no JCL file opened
   without the flag (``sys.addaudithook`` on ``open``).
4. Timing: 1 warm-up round (discarded) and 21 rounds. Each round runs the 8
   configurations (4 sizes x flag off/on) in the order
   ``random.Random(20261104 + round).shuffle``; round 0 is the warm-up. Each CLI
   run is timed with ``time.perf_counter_ns()`` around ``Popen`` and
   ``os.wait4``. No ``timeout=`` is passed anywhere: CPython waits with a
   timeout by polling in up to 50 ms sleeps, which quantises the readings.
   Run the whole script under an outside watchdog instead, for example
   ``timeout 14400 python scripts/lineage_timing_protocol.py ...``.
5. Statistic: added time per size and round = flag-on minus flag-off of the
   same round; per size the median over the 21 rounds. ``k`` = least-squares
   slope of log(median added time) on log(jobs). 95 % interval from 10,000
   bootstrap resamples of rounds (seed 20261104), percentile method. If any
   resample has a non-positive median, the interval is undefined and fails.
6. Pass only if all: ``k <= 1.25``; upper bound of ``k`` <= 1.35; median added
   time per 100,000 JCL steps <= 10 s at every size; the flag-off check holds.
   Consecutive ratios with intervals, best and median per size and peak RSS are
   reported, not decisive. There is no lower bound.

Usage::

    timeout 14400 python scripts/lineage_timing_protocol.py \\
        --repo . --main ../main-checkout --python /path/to/venv/bin/python \\
        --workdir /tmp/lineage-timing --out /tmp/lineage-timing/result

``--python`` must be an interpreter where ``hefesto`` imports from
``PYTHONPATH``; each tree is selected with ``PYTHONPATH``. ``--smoke`` runs tiny
sizes and 2 rounds to check the script itself; its output is marked as not a
protocol run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

SIZES = (2000, 4000, 8000, 16000)
STEPS_PER_JOB = 6
ROUNDS = 21
SHUFFLE_SEED = 20261104
BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20261104
GEN_SEED = 7
K_MAX = 1.25
K_UPPER_MAX = 1.35
PER_100K_MAX_S = 10.0

JCL_SUFFIXES = (".jcl", ".prc", ".proc", ".jcllib")
OPENS_SHIM = (
    "import atexit, runpy, sys\n"
    "hits = []\n"
    "def hook(event, args):\n"
    "    if event == 'open' and isinstance(args[0], str) and args[0].lower().endswith(%r):\n"
    "        hits.append(args[0])\n"
    "sys.addaudithook(hook)\n"
    "atexit.register(lambda: sys.__stderr__.write('JCL_OPENS=%%d\\n' %% len(hits)))\n"
    "sys.argv = ['hefesto', *sys.argv[1:]]\n"
    "runpy.run_module('hefesto.cli.main', run_name='__main__')\n"
) % (JCL_SUFFIXES,)
TIMING_KEYS = re.compile(r'"(duration[a-z_]*|timestamp|[a-z_]*_ms|analysis_time[a-z_]*)": [^,}\n]+')


def generate(jobs: int, out: Path) -> None:
    """The seeded synthetic tree (seed 7)."""
    rnd = random.Random(GEN_SEED)
    for sub in ("jcl", "proc", "cbl"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    for p in range(500):
        (out / "cbl" / f"P{p:05d}.cbl").write_text(
            f"       IDENTIFICATION DIVISION.\n       PROGRAM-ID. P{p:05d}.\n"
            "       ENVIRONMENT DIVISION.\n"
            "       INPUT-OUTPUT SECTION.\n       FILE-CONTROL.\n"
            "           SELECT IN-F ASSIGN TO INFILE.\n"
            "           SELECT OUT-F ASSIGN TO OUTFILE.\n       PROCEDURE DIVISION.\n"
            "           GOBACK.\n"
        )
    for r in range(20):
        (out / "proc" / f"PR{r:03d}.prc").write_text(
            f"//PR{r:03d} PROC\n//PS1 EXEC PGM=P{r:05d}\n"
            f"//INFILE DD DSN=SYN.PROC{r}.IN,DISP=SHR\n"
            f"//OUTFILE DD DSN=SYN.PROC{r}.OUT,DISP=(NEW,CATLG)\n//PS2 EXEC PGM=IEBGENER\n"
            f"//SYSUT1 DD DSN=SYN.PROC{r}.OUT,DISP=SHR\n"
        )
    for j in range(jobs):
        lines = [f"//J{j:05d} JOB (ACCT),'SYN',CLASS=A"]
        for s in range(4):
            pgm = "IDCAMS" if s == 3 else f"P{rnd.randrange(500):05d}"
            lines += [
                f"//S{s} EXEC PGM={pgm}",
                f"//INFILE DD DSN=SYN.J{j}.S{s}.IN,DISP=SHR",
                f"//OUTFILE DD DSN=SYN.J{j}.S{s}.OUT,",
                "//   DISP=(NEW,CATLG,DELETE)",
                "//SYSOUT DD SYSOUT=*",
            ]
        lines.append(f"//S4 EXEC PR{rnd.randrange(20):03d}")
        (out / "jcl" / f"J{j:05d}.jcl").write_text("\n".join(lines) + "\n")


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def env_for(tree: Path) -> Dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(tree))


def capture(py: str, tree: Path, args: Sequence[str], shim: bool = False) -> Tuple[int, str, str]:
    """Run the CLI and capture its output (no timeout: see the module docstring)."""
    head = [py, "-c", OPENS_SHIM] if shim else [py, "-m", "hefesto.cli.main"]
    proc = subprocess.Popen(
        [*head, "analyze", *args],
        cwd=tree,
        env=env_for(tree),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate()
    return proc.returncode, out, err


def timed(py: str, tree: Path, corpus: Path, lineage: bool) -> Tuple[int, int, int]:
    """(elapsed ns, exit code, peak RSS KiB) of one CLI run, output discarded."""
    args = [py, "-m", "hefesto.cli.main", "analyze", str(corpus), "--output", "json", "--quiet"]
    if lineage:
        args.append("--lineage")
    start = time.perf_counter_ns()
    proc = subprocess.Popen(
        args, cwd=tree, env=env_for(tree), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    _, status, usage = os.wait4(proc.pid, 0)
    elapsed = time.perf_counter_ns() - start
    proc.returncode = os.waitstatus_to_exitcode(status)
    return elapsed, proc.returncode, usage.ru_maxrss


def git_sha(tree: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tree, text=True).strip()


def git_dirty(tree: Path) -> bool:
    out = subprocess.check_output(["git", "status", "--porcelain"], cwd=tree, text=True)
    return bool(out.strip())


def machine() -> Dict[str, object]:
    cpu = platform.processor()
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem = line.split(":", 1)[1].strip()
    except OSError:
        pass
    return {
        "cpu": cpu,
        "cores": os.cpu_count(),
        "memory": mem,
        "os": platform.platform(),
        "python": sys.version.split()[0],
    }


def slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx, my = statistics.fmean(lx), statistics.fmean(ly)
    num = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    den = sum((a - mx) ** 2 for a in lx)
    return num / den


def percentile(values: List[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def analyse(sizes: Sequence[int], added: Dict[int, List[float]]) -> Dict[str, Any]:
    """Medians, k, and bootstrap intervals over resampled rounds."""
    n = len(added[sizes[0]])
    medians = {s: statistics.median(added[s]) for s in sizes}
    positive = all(m > 0 for m in medians.values())
    k = slope(sizes, [medians[s] for s in sizes]) if positive else float("nan")
    rnd = random.Random(BOOTSTRAP_SEED)
    ks: List[float] = []
    ratios: Dict[str, List[float]] = {f"{b}/{a}": [] for a, b in zip(sizes, sizes[1:])}
    invalid = 0
    for _ in range(BOOTSTRAP):
        idx = [rnd.randrange(n) for _ in range(n)]
        med = {s: statistics.median(added[s][i] for i in idx) for s in sizes}
        for a, b in zip(sizes, sizes[1:]):
            if med[a] > 0:
                ratios[f"{b}/{a}"].append(med[b] / med[a])
        if all(m > 0 for m in med.values()):
            ks.append(slope(sizes, [med[s] for s in sizes]))
        else:
            invalid += 1
    return {
        "median_added_s": medians,
        "k": k,
        "k_ci95": [percentile(ks, 0.025), percentile(ks, 0.975)] if ks else None,
        "bootstrap_invalid": invalid,
        "ratios": {
            key: {
                "point": medians[int(key.split("/")[0])] / medians[int(key.split("/")[1])],
                "ci95": [percentile(v, 0.025), percentile(v, 0.975)] if v else None,
            }
            for key, v in ratios.items()
        },
    }


def flag_off_check(
    py: str, repo: Path, main: Path, corpora: Dict[int, Path]
) -> Tuple[bool, List[str], Dict[int, int]]:
    ok, lines, steps = True, [], {}
    for size, corpus in corpora.items():
        for fmt in ("json", "sarif"):
            a = capture(py, main, [str(corpus), "--output", fmt, "--quiet"])
            b = capture(py, repo, [str(corpus), "--output", fmt, "--quiet"])
            if fmt == "json":
                same = TIMING_KEYS.sub('"T": 0', a[1]) == TIMING_KEYS.sub('"T": 0', b[1])
            else:
                same = a[1] == b[1]
            same = same and a[0] == b[0]
            ok &= same
            lines.append(
                f"{size} jobs {fmt} flag off vs main: {'identical' if same else 'DIFF'}"
                f" (rc {a[0]}/{b[0]}, {len(a[1])}/{len(b[1])} bytes)"
            )
        opens = []
        for tree, flags in ((main, ()), (repo, ()), (repo, ("--lineage",))):
            rc, out, err = capture(
                py, tree, [str(corpus), "--output", "json", "--quiet", *flags], shim=True
            )
            found = re.search(r"JCL_OPENS=(\d+)", err)
            opens.append(int(found.group(1)) if found else -1)
            if flags:
                data = json.loads(out[out.index("{") :])
                nodes = data.get("lineage", {}).get("nodes", [])
                steps[size] = sum(1 for node in nodes if node.get("kind") == "jcl_step")
        none_off = opens[0] == 0 and opens[1] == 0
        ok &= none_off and opens[2] > 0
        lines.append(
            f"{size} jobs JCL opens: main={opens[0]} off={opens[1]} lineage={opens[2]}"
            f" -> {'ok' if none_off else 'JCL OPENED WITHOUT FLAG'}"
        )
        lines.append(f"{size} jobs jcl_step nodes with --lineage: {steps[size]}")
    return ok, lines, steps


class Log:
    """Prints a line and appends it to ``result.txt``."""

    def __init__(self, path: Path) -> None:
        self.handle = path.open("w")

    def __call__(self, text: str) -> None:
        print(text, flush=True)
        self.handle.write(text + "\n")
        self.handle.flush()


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--repo", type=Path, required=True, help="checkout under test")
    parser.add_argument("--main", type=Path, required=True, help="main checkout")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true", help="tiny sizes; not a protocol run")
    return parser.parse_args(argv)


def header(say: Log, opts: argparse.Namespace, repo: Path, main_tree: Path, sha: str) -> None:
    say("SMOKE RUN - NOT A PROTOCOL RUN" if opts.smoke else "lineage timing protocol run")
    say(f"repo {repo} commit {git_sha(repo)} dirty={git_dirty(repo)}")
    say(f"main {main_tree} commit {git_sha(main_tree)} dirty={git_dirty(main_tree)}")
    say(f"script {Path(__file__).resolve()} sha256 {sha}")
    say(f"python {opts.python}")
    say(f"machine {json.dumps(machine(), sort_keys=True)}")
    say(f"started {time.strftime('%Y-%m-%dT%H:%M:%S%z')} loadavg {os.getloadavg()}")


def prepare(say: Log, workdir: Path, sizes: Sequence[int]) -> Dict[int, Path]:
    corpora: Dict[int, Path] = {}
    for size in sizes:
        corpus = workdir / f"syn{size}"
        if not corpus.exists():
            generate(size, corpus)
        corpora[size] = corpus
        say(f"corpus {size} jobs: {corpus} tree sha256 {tree_digest(corpus)}")
    return corpora


def run_rounds(
    say: Log, py: str, repo: Path, corpora: Dict[int, Path], rounds: int, csv_path: Path
) -> List[List[float]]:
    """Warm-up round 0, then rounds 1..N; one CSV row per CLI run."""
    configs = [(s, flag) for s in corpora for flag in (False, True)]
    rows: List[List[float]] = []
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["round", "warmup", "order", "jobs", "lineage", "ns", "rc", "maxrss_kib", "load1"]
        )
        for rnd_no in range(rounds + 1):
            order = list(configs)
            random.Random(SHUFFLE_SEED + rnd_no).shuffle(order)
            load_start = os.getloadavg()[0]
            for pos, (size, flag) in enumerate(order):
                ns, rc, rss = timed(py, repo, corpora[size], flag)
                row = [rnd_no, int(rnd_no == 0), pos, size, int(flag), ns, rc, rss, load_start]
                writer.writerow(row)
                handle.flush()
                rows.append(row)
            warm = " (warm-up)" if rnd_no == 0 else ""
            say(f"round {rnd_no}{warm}: load1 start {load_start:.2f} end {os.getloadavg()[0]:.2f}")
    return rows


def per_100k(median_s: float, jobs: int) -> float:
    return median_s * 100_000 / (jobs * STEPS_PER_JOB)


def report_sizes(
    say: Log,
    rows: List[List[float]],
    timing: Dict[Tuple[float, float, float], float],
    sizes: Sequence[int],
    rounds: int,
    medians: Dict[int, float],
) -> None:
    for size in sizes:
        on = [timing[(n, size, 1)] for n in range(1, rounds + 1)]
        off = [timing[(n, size, 0)] for n in range(1, rounds + 1)]
        rss_on = max(r[7] for r in rows if r[3] == size and r[4] == 1) / 1024
        rss_off = max(r[7] for r in rows if r[3] == size and r[4] == 0) / 1024
        say(
            f"{size} jobs: median added {medians[size]:.4f}s ="
            f" {per_100k(medians[size], size):.2f}s per 100k steps;"
            f" off best {min(off):.4f} median {statistics.median(off):.4f};"
            f" on best {min(on):.4f} median {statistics.median(on):.4f};"
            f" peak RSS off {rss_off:.0f} MB on {rss_on:.0f} MB"
        )


def criteria(
    stats: Dict[str, Any],
    medians: Dict[int, float],
    sizes: Sequence[int],
    ok_off: bool,
    rows: List[List[float]],
) -> Dict[str, bool]:
    k, ci = stats["k"], stats["k_ci95"]
    # A resample with a non-positive median has no log: the interval is then
    # undefined and this criterion fails rather than dropping resamples.
    upper_ok = ci is not None and not stats["bootstrap_invalid"] and ci[1] <= K_UPPER_MAX
    return {
        "k <= 1.25": k <= K_MAX,
        "k upper bound <= 1.35": upper_ok,
        "<= 10 s per 100k steps at every size": all(
            per_100k(medians[s], s) <= PER_100K_MAX_S for s in sizes
        ),
        "flag off identical and no JCL opened": ok_off,
        "every run exited 0 or 1": all(r[6] in (0, 1) for r in rows),
    }


def main(argv: Sequence[str] | None = None) -> int:
    opts = parse_args(argv)
    sizes = (20, 40, 80, 160) if opts.smoke else SIZES
    rounds = 2 if opts.smoke else ROUNDS
    repo, main_tree = opts.repo.resolve(), opts.main.resolve()
    opts.out.mkdir(parents=True, exist_ok=True)
    say = Log(opts.out / "result.txt")
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    header(say, opts, repo, main_tree, script_sha)
    corpora = prepare(say, opts.workdir, sizes)

    ok_off, lines, steps = flag_off_check(opts.python, repo, main_tree, corpora)
    for line in lines:
        say(line)
    for size in sizes:
        if steps.get(size) != size * STEPS_PER_JOB:
            say(f"step count {steps.get(size)} != {size * STEPS_PER_JOB} for {size} jobs")
            ok_off = False

    rows = run_rounds(say, opts.python, repo, corpora, rounds, opts.out / "rounds.csv")
    timing = {(r[0], r[3], r[4]): r[5] / 1e9 for r in rows if r[0] > 0}
    added = {
        s: [timing[(n, s, 1)] - timing[(n, s, 0)] for n in range(1, rounds + 1)] for s in sizes
    }
    stats = analyse(sizes, added)
    medians: Dict[int, float] = stats["median_added_s"]
    report_sizes(say, rows, timing, sizes, rounds, medians)
    for key, value in stats["ratios"].items():
        say(f"ratio {key}: {value['point']:.3f} ci95 {value['ci95']} (info)")
    say(
        f"k = {stats['k']:.4f} ci95 {stats['k_ci95']}"
        f" (bootstrap {BOOTSTRAP}, seed {BOOTSTRAP_SEED})"
    )
    if stats["bootstrap_invalid"]:
        say(f"bootstrap resamples with a non-positive median: {stats['bootstrap_invalid']}")

    checks = criteria(stats, medians, sizes, ok_off, rows)
    for name, passed in checks.items():
        say(f"criterion {name}: {'PASS' if passed else 'FAIL'}")
    verdict = all(checks.values())
    say(f"finished {time.strftime('%Y-%m-%dT%H:%M:%S%z')} loadavg {os.getloadavg()}")
    suffix = " (smoke, not a protocol run)" if opts.smoke else ""
    say(f"VERDICT {'PASS' if verdict else 'FAIL'}{suffix}")
    summary = {
        "script_sha256": script_sha,
        "commit": git_sha(repo),
        "smoke": opts.smoke,
        "stats": {**stats, "median_added_s": {str(s): v for s, v in medians.items()}},
        "checks": checks,
        "verdict": verdict,
    }
    (opts.out / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
