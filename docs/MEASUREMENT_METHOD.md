# Measuring rule precision

This is how a rule earns a precision claim in `docs/ANALYSIS_RULES.md`. Until a rule meets the bar below, it stays experimental.

## Corpora
- Only public repositories pinned to a full commit SHA. They are cloned, shallow, and read. They are never built or executed.
- There are two sets:
  - **Tuning repositories:** used while the rule is written or narrowed.
  - **Held-out repositories:** listed before the measurement and never used for tuning.
- A precision claim comes only from held-out repositories. Results on tuning repositories are reported as context and labelled "tuning".

## Sampling
- Run with the rule's experimental names and `--severity LOW --output json`.
- Collect every finding of the rule. Drop exact duplicates, meaning the same file, line and rule; a file reached through several symlinks counts once.
- When a rule has more hits than can be labelled, draw a simple random sample. Record the seed and the script next to the results. Otherwise label every hit.
- Report hits and labels per repository and per root cause (for example: protocol-mandated digest, DDL identifier, internal format table). This keeps one large repository from hiding behind a single percentage.

## Labels
Each finding gets two labels and a one-line reason:
- **A, definition match:** the code is what the rule documents. This is near-circular, because the rule was written to match exactly that, so A only catches parser or matching bugs. It is never the published number.
- **B, actionable:** a security reviewer should change the code or check it by hand. B is FP when the flagged value is provably bounded or constant, protocol-mandated, internal-only, or in benchmark or data files.

A second labeller labels a blind random subset (file, line and pinned SHA only, without the first labels). Disagreements are reported with the result.

## The bar
- The published number is B as `correct/n`.
- A claim of 95% precision needs n ≥ 59 B-labelled findings with **0 errors**. This is the exact one-sided bound: 0.95^59 < 0.05.
- A Wilson 95% interval is reported next to every B figure as context. It is not the bar.
- A rule below the bar is reported with its numbers and stays experimental. A rule whose B is near 0 is narrowed, moved to LOW as an inventory, or dropped. The decision and its reasons go in `docs/ANALYSIS_RULES.md`.

## Release gate
Opt-in rules must not change default output. `scripts/release_gate.py` runs main and the branch with **no flags** on the pinned corpora in `scripts/release_gate_corpora.txt`, ignores timing fields, and fails on any difference in findings, counts or exit code. The `Release Gate` workflow runs it on pull requests to main. It is required for the 4.21.0 release.

When a pull request intentionally changes default analyzer output, a red `no-flag-diff` job on that pull request is expected. The pull request description must state the exact expected difference (corpus, file, line, rule, and old and new issue counts). The reviewer checks that difference against the job log; everything else must match exactly, and `CHANGELOG.md` must carry an upgrade note for users of the `@v4` Action. The comparison is never disabled, and no expected-delta file is used.
