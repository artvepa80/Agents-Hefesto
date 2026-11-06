# HefestoAI skill: moved

The HefestoAI agent skill moved to [`skills/hefestoai/`](../skills/hefestoai/SKILL.md)
(`name: hefestoai`, following the [Agent Skills specification](https://agentskills.io/specification)).
Its reference docs (`commands.md`, `issue_types.md`, `integration.md`,
`semantic_drift.md`, `reliability_drift.md` and `analysis/`) moved with it.

The Hefesto Code Gate skills for Claude Code, Codex and Cursor now live in
[artvepa80/hefesto-code-gate](https://github.com/artvepa80/hefesto-code-gate)
(v1.0.0). Install in Claude Code:

```text
/plugin marketplace add artvepa80/hefesto-code-gate
/plugin install hefesto-code-gate@hefestoai
```

Requires `hefesto-ai>=4.21.0,<5`.
