# 2026-10-13 — IaC/YAML triage on public repositories

Sanitized worklog, added 2026-10-16 so that the `yaml-iac` entries of the
`hefestoai-language-learnings` skill have an in-repo source. It records a read-only `hefesto analyze`
run on public open-source repositories and a manual spot-check of some findings. Nothing was fixed.

## Run

| Repo | License | Files | Findings (summary) |
|---|---|---|---|
| docker/awesome-compose | CC0-1.0 | 108 | 102: DOCKER003×61, DOCKER001×33, YAML_SECRET_EXPOSURE×3, DOCKER010×2, SQL020, BARE_EXCEPT, R3 |
| terraform-aws-modules/terraform-aws-vpc | Apache-2.0 | 83 | 60: TF001B×50, TF002B×9, YAML_UNSAFE_COMMAND×1 |
| kubernetes/examples | Apache-2.0 | 304 | 62: YAML_UNSAFE_COMMAND×19, missing-safety×18, DOCKER001×15, YAML_SYNTAX_ERROR×5, DOCKER003×3, others |

## Spot-checks that point at analyzer problems

- terraform-aws-vpc, TF001B on `complete/main.tf:112`: false positive / mislabel. It is a
  `default_network_acl` **egress** rule, reported as "Security group allows ingress".
  `network-acls/main.tf:28` is also a network ACL rule, not a security group.
- awesome-compose, YAML_SECRET_EXPOSURE on `nginx-flask-mysql/compose.yaml:10` and the
  `nginx-aspnet-mysql` compose file (line 22): false positive. The password is read from
  `/run/secrets` via `$$(cat ...)`, the Docker secrets pattern.
- kubernetes/examples, YAML_SYNTAX_ERROR on `newrelic-config-template.yaml:7` (`{{config_data}}`):
  false positive. The file is a template placeholder, not YAML until rendered.

## Improvement notes (open)

1. TF001B/TF002B fire on AWS network ACL rules (including egress) with the security-group/"ingress"
   message: wrong resource type and direction.
2. YAML_SECRET_EXPOSURE flags `password=$(cat /run/secrets/...)`, the recommended Docker secrets pattern.
3. YAML_SYNTAX_ERROR on `{{ }}` template files; consider skipping templates.
