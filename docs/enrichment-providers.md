# Connecting an enrichment provider

Enrichment adds an optional, metadata-only note to findings (`issue.metadata["enrichment"]`).
It needs Hefesto PRO and a provider package you install yourself. Hefesto ships no provider.

**Requires `hefesto-pro >= 3.10.1` (pending release).** With older PRO releases the
`--enrich-timeout` limit does not stop the wait for a slow provider, and `--enrich local`
skips every provider.
Enrichment never changes the finding list, severities or the exit code.

## 1. Write a provider

A provider is any object with a `name` and an `enrich(inp, config)` method that returns an
`EnrichmentResult` (the `EnrichmentProvider` protocol of the PRO enrichment API):

```python
# EnrichmentResult is provided by the Hefesto PRO enrichment API.


class OllamaProvider:
    name = "ollama"      # must equal the entry-point name below
    is_local = True      # optional, see "Local-only mode"

    def enrich(self, inp, config):
        # inp.finding_summary and inp.snippet are already masked and size-bounded.
        text = call_your_model(inp.finding_summary, inp.snippet, timeout=config.timeout_seconds)
        return EnrichmentResult(status="ok", summary=text)
```

## 2. Register it as an entry point

In your package's `pyproject.toml`:

```toml
[project.entry-points."hefesto.enrichment_providers"]
ollama = "my_pkg.providers:OllamaProvider"
```

The target can be a class (created with no arguments) or a ready instance.
Install the package in the same environment as Hefesto (`pip install my-pkg`).

## 3. Turn it on

```bash
hefesto analyze src/ --enrich remote --enrich-provider ollama
```

Only the names passed with `--enrich-provider` are imported; other installed providers are
never loaded. A provider is used only if it implements the protocol and its `name` matches the
entry-point name. If a provider is not installed, fails to import or start, or fails those checks,
Hefesto prints a warning on stderr and keeps going without it.

## Limits

| Flag | Default | Meaning |
| --- | --- | --- |
| `--enrich-min-severity` | `MEDIUM` | Only findings at or above this severity are sent. |
| `--enrich-max-findings` | `50` | At most this many findings per run, highest severity first. `0` sends none. |
| `--enrich-timeout` | `30` | Seconds per provider call. |
| `--enrich-cache-ttl` / `--enrich-cache-max` | `300` / `500` | In-run cache of identical (masked) inputs. |

Calls run one after another, one per selected finding. Findings that are not selected get no
`enrichment` key. A call that exceeds the timeout is abandoned, not cancelled: it may keep
running in the background, and a paid remote provider may still bill for it.

## Local-only mode

`--enrich local` runs only providers that declare `is_local = True` (set it only if the provider
never sends data off the machine). Providers without the attribute are treated as remote and
skipped. PRO releases before 3.10.1 skip every provider in local mode.

## Duplicate provider names

If two installed packages register the same entry-point name, Hefesto prints a warning to stderr
naming both packages and uses the first one in alphabetical order of package name.

## Not covered

`hefesto serve`, the GitHub Action and `hefesto pr-review` do not load providers.
`pr-review` comments show an "AI insight" line only when a finding already carries an
`enrichment` result with `status: ok`.
