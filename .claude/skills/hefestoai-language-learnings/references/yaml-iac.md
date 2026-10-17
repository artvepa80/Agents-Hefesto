# YAML and IaC learnings

These three came from a manual review of public repositories on 2026-10-13
(`docs/worklog/2026-10-13-iac-yaml-triage.md`). They are not fixed
as far as the sources show; check the analyzer before relying on them.

### TF001B/TF002B on network ACL rules, reported as security-group ingress

- **Symptom:** "Security group allows ingress" on a `default_network_acl` **egress** rule (terraform-aws-vpc `complete/main.tf:112`).
- **Cause:** the rule fires on AWS network ACL rules with the security-group/ingress message: wrong resource type and direction.
- **Fix:** none yet. Triage such findings as mislabels.
- **Official source:** https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html
- **PR/commit:** `docs/worklog/2026-10-13-iac-yaml-triage.md`
- **Verified:** 2026-10-13
- **Status:** Open

### YAML_SECRET_EXPOSURE on Docker secrets

- **Symptom:** YAML_SECRET_EXPOSURE on `password=$(cat /run/secrets/...)` (awesome-compose).
- **Cause:** the rule treats the recommended Docker secrets pattern as a literal secret.
- **Fix:** none yet. Triage as false positive.
- **Official source:** https://docs.docker.com/compose/how-tos/use-secrets/
- **PR/commit:** `docs/worklog/2026-10-13-iac-yaml-triage.md`
- **Verified:** 2026-10-13
- **Status:** Open

### YAML_SYNTAX_ERROR on `{{ }}` template files

- **Symptom:** YAML_SYNTAX_ERROR on `newrelic-config-template.yaml:7` (`{{config_data}}`).
- **Cause:** the file is a template, not YAML until rendered.
- **Fix:** none yet (skipping templates was proposed). Triage as false positive.
- **Official source:** https://yaml.org/spec/1.2.2/
- **PR/commit:** `docs/worklog/2026-10-13-iac-yaml-triage.md`
- **Verified:** 2026-10-13
- **Status:** Open

### YAML_INDENTATION on normally nested files

- **Symptom:** "Inconsistent indentation (5 levels)" on line 1 of a GitHub workflow.
- **Cause:** the rule counted distinct indentation widths and flagged more than 3.
- **Fix:** it now judges the step between nesting levels. The COBOL corpus baseline also records non-COBOL findings, so it had to drop 2 stale entries.
- **Official source:** https://yaml.org/spec/1.2.2/#61-indentation-spaces
- **PR/commit:** CHANGELOG 4.17.0
- **Verified:** 4.17.0
- **Status:** Fixed

### YAML file parsed more than once, and always with SafeLoader

- **Symptom:** `hefesto analyze` on a 1 MB multi-document Kubernetes manifest was about 1.8 s on 4.19.0 and about 4.5 s on 4.20.0 and 4.20.1 (this machine; see the 4.20.2 changelog).
- **Cause:** since 4.20.0, format detection and the analyzer each call `yaml.safe_load_all`. A file named on the command line is classified a third time. `safe_load` and `safe_load_all` always use the pure-Python `SafeLoader`, even when libyaml is installed.
- **Fix:** one parse per file, shared by detection and analysis, with `yaml.CSafeLoader` when it exists and `yaml.SafeLoader` otherwise. A document `yaml.parse` rejects is loaded once with `SafeLoader`. A `CSafeLoader` exception after that scan is parsed again with `SafeLoader`, so the line and the message stay the pure-Python ones. Nesting is always measured with `yaml.parse`. Deeper than 256 uses `SafeLoader`: the C loader segfaults between 20,000 and 30,000 levels, and `SafeLoader` rejects from depth 486-489 (recursion limit 1000, about 2 frames per level). A tab, a line starting with `%`, U+FEFF, `[|>][0-9+-]*#` (X4QW, `block: ># comment`), or an empty flow `?` key also uses `SafeLoader`. Valid documents with `?` or `!` inside a flow collection (`urls: [http://example.com/?a=1, b]`, `{foo: a?}`, `a: [!!str, c]`, JR7V, WZ62) stay on libyaml and are no longer flagged. Around depth 483-488 the finding is HIGH where 4.20.1 passed. Any exception from the loader, including `ValueError` from a timestamp, stays a syntax finding so the file's other findings are kept. Helm chart templates under `templates/` next to `Chart.yaml` that contain `{{` are not parsed.
- **Official source:** https://pyyaml.org/wiki/PyYAMLDocumentation
- **PR/commit:** #139, CHANGELOG 4.20.2, `docs/worklog/2026-10-17-yaml-single-parse.md`
- **Verified:** 4.20.2
- **Status:** Fixed
