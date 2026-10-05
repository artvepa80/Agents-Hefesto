# Cognitive core mapping for HefestoAI

Product architecture note (not a research claim). Applies Andrej Karpathy’s
“cognitive core” idea to how we want agents to use HefestoAI—and, briefly,
how the same split shows up in Kronos.

## What “cognitive core” means here

In the [Dwarkesh interview with Andrej Karpathy](https://www.dwarkesh.com/p/andrej-karpathy),
Karpathy describes a small reasoning core stripped of memorized knowledge: keep
the algorithms for thought and problem-solving, force lookup of facts instead of
inventing them, and leave room for external memory and tools. He also floated a
rough ~1B-parameter speculation for such a core; that figure is informal, not a
benchmark we claim. Community one-pagers (e.g. “Local Language Model Engineering
2026” infographics) sometimes summarize the same thesis—they are not
peer-reviewed papers. Separately, harness work such as
[arXiv:2609.00006](https://arxiv.org/abs/2609.00006) stresses that an agent is a
model plus a runtime that can verify outcomes externally; Hefesto sits on that
verification side.

## Mapping for HefestoAI

| Layer | In Hefesto terms | What it must do |
|-------|------------------|-----------------|
| **Core** | Decision and verification rules (analyzers, severities, exit codes, hooks) | Decide pass/fail from evidence; never invent green |
| **Memory** | README, [`skill/SKILL.md`](../skill/SKILL.md), repo files, CI logs, analyze reports | Be looked up, not guessed |

Agents must **force lookup**: run `hefesto analyze` (and read the report) before
claiming the tree is clean. That gate is now explicit in the public skill docs
merged in [#53](https://github.com/artvepa80/Agents-Hefesto/pull/53)
(YAML agentskills frontmatter + mandatory analyze-before-commit). The model’s
job is to interpret findings and fix code; Hefesto’s job is to be the external
truth check.

## Skills as cartridges

Treat `skill/` as progressive-disclosure cartridges: a short task prompt plus
pointers to truth files (`commands.md`, `issue_types.md`, analyzers, hooks).
Load only what the task needs. Do not paste the whole catalog into every
session. Same pattern as [#53]: discoverable frontmatter, then deeper docs on
demand.

## Five concrete dogfood cases

Use these as manual or CI-oriented checks that the core-vs-memory split holds:

1. **Lying README** — README claims a CLI entrypoint that `[project.scripts]`
   does not define (or the reverse). Expect Operational Truth / docs-vs-entrypoints
   style findings when analyzing the project root.
2. **Hardcoded secret vs env** — Commit a fake API key string in source while
   `.env.example` documents the same name as an env var. Expect
   `HARDCODED_SECRET` (or equivalent) on analyze; fixing means env/config, not
   silencing the rule.
3. **Missing analyze before commit** — Agent edits code and opens a PR without a
   fresh `hefesto analyze` exit `0`. Skill rules say this is not allowed; hooks
   (`hefesto install-hooks`) make the same rule mechanical.
4. **Packaging version drift** — Bump version in only one of `pyproject.toml`,
   CHANGELOG, or README badge. Expect packaging-parity findings.
5. **Import undeclared** — Add a third-party import used in code but absent from
   `pyproject.toml` / requirements. Expect imports-vs-deps finding; the fix is
   declare or remove, not “it worked in my shell.”

These are acceptance scenarios for the architecture, not claims of zero false
positives.

## Kronos (brief)

Kronos is a Hyperliquid trading bot running a **cloud** loop on Railway. It is
not a place to host a local LLM cognitive core. The useful analogy only: trading
**rules / risk policy = core**; live market and API state = **external memory**.
Do not plan on-box LLM inference inside that Railway service as part of this
mapping.

## What we are not doing next

- Training or shipping a ~1B “cognitive core” model for Hefesto or Kronos.
- Running a local LLM as the Kronos runtime on Railway.
- Treating community infographics or interview speculation as peer-reviewed
  evidence or product SLAs.

## See also

- [`skill/SKILL.md`](../skill/SKILL.md) — agent discovery + analyze-before-commit
- [`docs/ai-discovery.md`](ai-discovery.md) — MCP / guardrail discovery surface
