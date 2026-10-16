# YAML and IaC learnings

These three came from a manual review of public repositories on 2026-10-07. They are not fixed
as far as the sources show; check the analyzer before relying on them.

### TF001B/TF002B on network ACL rules, reported as security-group ingress

- **Symptom:** "Security group allows ingress" on a `default_network_acl` **egress** rule (terraform-aws-vpc `complete/main.tf:112`).
- **Cause:** the rule fires on AWS network ACL rules with the security-group/ingress message: wrong resource type and direction.
- **Fix:** none yet. Triage such findings as mislabels.
- **Official source:** https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html
- **PR/commit:** handoff `2026-10-07-hefesto-growth-x-content.md`
- **Verified:** 2026-10-07
- **Status:** Open

### YAML_SECRET_EXPOSURE on Docker secrets

- **Symptom:** YAML_SECRET_EXPOSURE on `password=$(cat /run/secrets/...)` (awesome-compose).
- **Cause:** the rule treats the recommended Docker secrets pattern as a literal secret.
- **Fix:** none yet. Triage as false positive.
- **Official source:** https://docs.docker.com/compose/how-tos/use-secrets/
- **PR/commit:** handoff `2026-10-07-hefesto-growth-x-content.md`
- **Verified:** 2026-10-07
- **Status:** Open

### YAML_SYNTAX_ERROR on `{{ }}` template files

- **Symptom:** YAML_SYNTAX_ERROR on `newrelic-config-template.yaml:7` (`{{config_data}}`).
- **Cause:** the file is a template, not YAML until rendered.
- **Fix:** none yet (skipping templates was proposed). Triage as false positive.
- **Official source:** https://yaml.org/spec/1.2.2/
- **PR/commit:** handoff `2026-10-07-hefesto-growth-x-content.md`
- **Verified:** 2026-10-07
- **Status:** Open

### YAML_INDENTATION on normally nested files

- **Symptom:** "Inconsistent indentation (5 levels)" on line 1 of a GitHub workflow.
- **Cause:** the rule counted distinct indentation widths and flagged more than 3.
- **Fix:** it now judges the step between nesting levels. The COBOL corpus baseline also records non-COBOL findings, so it had to drop 2 stale entries.
- **Official source:** https://yaml.org/spec/1.2.2/#61-indentation-spaces
- **PR/commit:** CHANGELOG 4.17.0
- **Verified:** 4.17.0
- **Status:** Fixed
