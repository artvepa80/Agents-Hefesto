# Wiring the nine DevOps and cloud analyzers

This note is the design for dispatching the analyzers that already ship but that `hefesto analyze` does not call. It was written before the dispatch code. The noise counts at the end were measured on the analyzers as they stood, then checked again after the rules below.

## What is required

`hefesto analyze config.json` reports no file when the JSON contains `api_key` and `aws_secret`, because `JsonAnalyzer` is never selected. The same gap covers PowerShell, TOML, Makefile, Groovy/Jenkins, CloudFormation, ARM, Helm, and Serverless. Each module already exists and already has unit tests. The work is to recognize the file, choose one analyzer when several could claim it, and keep generated lockfiles from dominating the report.

Assumptions, stated so they can be checked:

- The public entry point is `hefesto analyze` (the CLI the GitHub Action and the hooks call). A file counts as supported only when that command puts it in the report.
- Dispatch reuses the existing analyzer classes. Their method names and rule IDs stay. No new rule is added to fill a gap in a module.
- A file is analyzed by one language, not by every analyzer whose suffix matches.
- Directory walks keep today's default directory excludes (`node_modules/`, `.git/`, virtualenvs, build output). New excludes are filenames of generated lockfiles only.
- A path the user names on the command line is still analyzed even when a directory walk would skip that filename. That is the same rule vendored JavaScript already uses.
- Shipped in 4.20.0 (the change was merged as unreleased work on 4.19.0, PR #124).

## Invariants

These are the properties detection has to keep. The CLI tests in `tests/test_devops_dispatch.py` are the check.

1. A supported file given to `hefesto analyze` appears in the JSON report with that language, and the fixture for each of the nine types produces at least one finding from its own rule id.
2. `.txt` and `.md` files are not analyzed.
3. `*.tf.json` is Terraform, including when the JSON object also looks like a CloudFormation template.
4. A JSON object is an ARM template only when `$schema` contains `deploymentTemplate.json` (the resource-group, subscription, management-group, and tenant schema names all contain that suffix). Otherwise a JSON object is CloudFormation only when it has `AWSTemplateFormatVersion` or a `Resources` object whose entries have `Type` values beginning with `AWS::`. Anything else stays JSON.
5. A YAML file is CloudFormation under the same structural test, and only when it is a single document. Helm `values.yaml` / `values.yml` / `values-*.yaml` is Helm only in a directory that contains `Chart.yaml`. `serverless.yml` and `serverless.yaml` are Serverless Framework only when the document is a mapping with `service` or `provider` and it is not CloudFormation. `Chart.yaml` and `templates/` stay YAML.
6. `package.json` keys `author` and dependency names are not secrets. Lockfiles named below are omitted from directory walks. `tsconfig.json` is still analyzed, so a real `api_key` there is reported.
7. An `echo` of `curl | sh` in a Makefile recipe is not MF002. A recipe that runs `curl | sh` still is.

## How the overlaps sort out

Deduction is what the page that was opened actually says. Conjecture is marked as such.

| Case | What the opened docs say | Decision |
| --- | --- | --- |
| JSON vs `*.tf.json` | HashiCorp: Terraform reads native syntax from `.tf` and JSON syntax from `.tf.json`. RFC 8259 defines the JSON text, not a filename. | The `.tf.json` suffix wins, before any JSON content test. |
| JSON vs CloudFormation | AWS template anatomy: a template is a JSON or YAML text file. The format-version page: `AWSTemplateFormatVersion` is optional and the only valid value is the literal `2010-09-09`. The resources page: `Resources` is a required object; each entry has `Type` of the form `AWS::ServiceName::ResourceType`. | Content test on `.json` and on `.yaml`/`.yml`. The version key alone is enough (the section is optional to omit, so its presence is decisive). A `Resources` object counts only when some `Type` starts with `AWS::`. |
| JSON vs ARM | Microsoft: an ARM template is JSON. `$schema` is required and is one of the `deploymentTemplate.json` URLs (resource group, subscription, management group, tenant). `resources` may be an array or, with `languageVersion` 2.0, an object. Bicep is a different language. | `$schema` containing `deploymenttemplate.json` (case-insensitive) selects ARM. Parameter files use `deploymentParameters.json`, which does not contain that substring, so they stay JSON. |
| ARM vs CloudFormation in one file | Neither page describes a file that is both. | Conjecture, locked by a test: the ARM `$schema` wins. It is a required URL, not a section name that another format reuses. |
| YAML vs CloudFormation | The AWS pages above show a YAML form of the same sections. The YAML sample writes `AWSTemplateFormatVersion: 2010-09-09` without quotes. | Same structural test as JSON. The key is enough; the value is not compared, because a YAML 1.1 loader may read the unquoted date as a timestamp. More than one YAML document is not a CloudFormation template (the pages show one document). |
| YAML vs Helm values | Helm chart layout: `Chart.yaml` is required; `values.yaml` sits beside it and is plain YAML. Extra values files are passed with `helm install -f`. | `values.yaml`, `values.yml`, and `values-*.yaml` / `values-*.yml` are Helm only when `Chart.yaml` is in the same directory. The same rule covers a subchart (`charts/<name>/`). |
| YAML vs Helm templates | Helm: `templates/` holds Go templates. They are not valid YAML until rendered (`{{ .Release.Name }}` and similar). | `templates/` stays YAML. `YamlAnalyzer` already skips the syntax check when the file contains `{{` and a sibling of `templates/` is `Chart.yaml`. `HelmAnalyzer` only reads values files, so sending templates to it would drop that syntax skip and report nothing. |
| `Chart.yaml` | Helm: required metadata (`apiVersion`, `name`, `version`), not the values file. | Stays YAML. `HelmAnalyzer` returns no findings for it. |
| YAML vs Serverless | Serverless Framework reference: the service file is `serverless.yml`, with top-level `service` and `provider`. | Filename `serverless.yml` or `serverless.yaml`, and a single mapping that has `service` or `provider`. CloudFormation structure wins if both match. A file with that name that does not parse, or that has neither key, stays YAML. |
| Makefile names | GNU make manual (`make.txt` 3.2): default names are `GNUmakefile`, `makefile`, `Makefile`, in that order. Section 3.3: `include` takes filenames and the manual's example uses `*.mk`. | Those three names, plus `*.mk`. No `*.mak` (the manual section that was read does not use it). |
| Jenkinsfile vs `*.groovy` | Jenkins: a `Jenkinsfile` in the project is the pipeline, declarative (`pipeline { }`) or scripted (no `pipeline` block). | `Jenkinsfile` and `*.groovy`. Not gated on `pipeline { }`, which would drop scripted pipelines. |
| PowerShell suffixes | `about_Scripts`: a script is `.ps1`; a script module is `.psm1`. `about_Module_Manifests`: a manifest is `.psd1`. | `*.ps1`, `*.psm1`, `*.psd1`. PS001–PS006 are Hefesto rules. They are not the PSScriptAnalyzer catalog (that page lists different rule names, such as `AvoidUsingInvokeExpression`). |
| TOML suffix | TOML v1.0.0 defines the text (UTF-8, case-sensitive keys). It does not name a suffix. | `*.toml`, which is the suffix the analyzer and `pyproject.toml` already assume. |
| JSON comments | RFC 8259 allows insignificant whitespace and does not allow comments. | `tsconfig.json` with comments fails `json.loads` and uses the existing regex fallback. It is not excluded. |

### Precedence

First match wins.

| Order | File | Analyzer |
| --- | --- | --- |
| 1 | Name ends with `.tf.json` | Terraform |
| 2 | JSON object whose `$schema` contains `deploymentTemplate.json` | ARM (`ArmAnalyzer`, JSON only) |
| 3 | JSON or single-document YAML with `AWSTemplateFormatVersion`, or a `Resources` object with a `Type` starting `AWS::` | CloudFormation |
| 4 | `serverless.yml` / `serverless.yaml` mapping with `service` or `provider`, and not row 3 | Serverless |
| 5 | `values.yaml`, `values.yml`, `values-*.yaml`, `values-*.yml` next to `Chart.yaml`, and the file parses as YAML | Helm |
| 6 | Other `*.json` | JSON |
| 7 | Other `*.yaml` / `*.yml`, including `Chart.yaml` and `templates/` | YAML |
| 8 | `Makefile`, `makefile`, `GNUmakefile`, `*.mk` | Makefile |
| 9 | `Jenkinsfile`, `*.groovy` | Groovy/Jenkins |
| 10 | `*.ps1`, `*.psm1`, `*.psd1` | PowerShell |
| 11 | `*.toml` | TOML |

Path globs still decide which files a directory walk opens. `.json` is owned by the JSON spec (first registration wins), and ARM/CloudFormation are chosen from the contents. Extra globs `*.cfn.json`, `*.cfn.yaml`, and `*.cfn.yml` only add names; the same content test still runs.

## What was rejected

- Treating every `*.json` as CloudFormation or ARM. Kubernetes lists, `package.json`, and PyPI metadata all use JSON. The AWS and Microsoft pages give structural markers; the suffix does not.
- Treating `Resources` as CloudFormation when it is an array, or when the value under a logical id is a string. The resources page shows an object of objects with `Type`. A probe file `{"Resources": [{"Type": "Widget"}]}` stays JSON.
- Requiring `pipeline { }` before running the Groovy analyzer. The Jenkinsfile page shows a scripted pipeline that starts at `node`, with no `pipeline` block.
- Sending `Chart.yaml` and `templates/` to `HelmAnalyzer`. That class returns immediately unless the basename is a values file, so the YAML syntax check on templates would disappear.
- Classifying a values file as Helm when `Chart.yaml` is absent. Helm's layout puts them together. A lone `values.yaml` stays YAML.
- Classifying YAML as ARM. The Microsoft page describes a JSON template. `ArmAnalyzer.analyze` returns `[]` unless the path ends in `.json`. YAML ARM is not implemented here.
- Walking `languageVersion` 2.0 `resources` objects inside `ArmAnalyzer`. The class only walks a list. Dispatch still selects ARM from `$schema`; resource rules may not run for the object form. That limitation is left as it is.
- Excluding `package.json` and `tsconfig*.json`. A real `api_key` in either file should be reported. The flood was the key test, not the filename.
- Excluding `pnpm-lock.yaml`. YAML already analyzes it. This change does not take existing YAML findings away.
- Implementing J003. `json_analyzer.py` has J001, J002, J004, and J005. The 4.5.0 changelog lists those four. The README line that said J001–J005 overstated the module.
- Implementing the PSScriptAnalyzer rule list. The opened rule index is a different product. Hefesto's PS001–PS006 stay the rules that run.
- Comparing `AWSTemplateFormatVersion` to the string `2010-09-09` after a YAML load. The AWS YAML sample is unquoted, and PyYAML 6 reads `2010-09-09` as a `datetime.date`. The key is the marker.

## Noise

Key matching used to be a substring (`"auth" in "author"`, `"credential" in "@aws-sdk/credential-providers"`). Measured by running the analyzers on every file the new dispatch would open, with today's directory excludes and without lockfile excludes. The same trees were measured again after token matching, dependency-map skips, the Makefile quote mask, and the lockfile names:

| Repo | Commit | Files opened (before) | Findings before | Files opened (after) | Findings after |
| --- | --- | --- | --- | --- | --- |
| This repo | `0e2c140` | JSON 6, TOML 1 | 0 | JSON 6, TOML 1 | 0 |
| helm/helm | `9b88efd62a6908fb11215f8e8b50c3c62a246df0` | Makefile 2, Helm values 200, JSON 18, PowerShell 2 | MF002 ×2, HELM_S001 ×1 | same counts | HELM_S001 ×1 |
| python-poetry/poetry | `38a86661d2ae58694c76d0bb4e628e1400d6dc6f` | TOML 110, JSON 106 | J001 ×98, J002 ×1 | same counts | J002 ×1 |
| serverless/serverless | `a61c2187afb6d9f01517065d115c38d3eb107e43` | JSON 104, Makefile 2, CloudFormation 8, Serverless 206, TOML 21 | J001 ×79, CFN_I001 ×4 | JSON 98, Makefile 2, CloudFormation 8, Serverless 206, TOML 21 | J001 ×2, CFN_I001 ×4 |

The six JSON files no longer opened in serverless/serverless are `package-lock.json` (the repository root and five package fixtures). `hefesto analyze` on this repository today, before this change, opens none of these files. The "before" column is what naive dispatch produced. The "after" column is what the engine reports. The new fixtures under `tests/fixtures/devops_dispatch/` and the generated `htmlcov/` tree are not in this count.

The Poetry J001 hits are PyPI JSON fixtures whose keys are `author` and `author_email`. The Serverless J001 hits are `package-lock.json` dependency names (`@aws-sdk/credential-provider-node` mapped to a version) plus `author` in `package.json`.

Rules that follow from that measurement:

- A secret or URL key matches a whole token (`api_key`, `api-key`, `apiKey`), not a substring. A key that contains whitespace is a label (`AWS Credentials` in a docs menu), not a secret key. A trailing plural still matches (`passwords`).
- Immediate keys of `dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies`, `bundledDependencies`, and `requires` are package names. They are not secret keys. Nested objects under them are still walked.
- Directory walks skip these generated lockfiles: `package-lock.json`, `npm-shrinkwrap.json`, `composer.lock`, `poetry.lock`, `Cargo.lock`, `uv.lock`, `Pipfile.lock`, `packages.lock.json`, `flake.lock`, `deno.lock`, `bun.lock`. Naming one of them on the command line still analyzes it.
- MF002 ignores `curl`/`wget` piped to a shell when that text sits inside quotes, which is how the Helm Makefile prints an install hint. An unquoted recipe still matches.

Findings that remain, and why they are not suppressed:

- Helm `HELM_S001` on `tlsSecret: wordpress.local-tls` in a testdata chart. The existing rule treats a key token `secret` with a non-empty string as a possible secret. The value is a Kubernetes Secret name. One hit, in testdata. The Helm rule was not rewritten.
- Serverless `CFN_I001` on S3 buckets in its own CloudFormation fixtures (missing `PublicAccessBlockConfiguration`). That is the existing rule on real `AWS::S3::Bucket` resources.
- Poetry `J002` on `download_url: http://pyyaml.org/download/pyyaml/PyYAML-3.13.tar.gz` in an archived PyPI fixture. The key is a URL field and the value is HTTP.
- Serverless test events `resultToken` and `Postman-Token`. The keys are token fields with literal values. The rule is doing what its tests describe.

`tsconfig.json` produced no findings in these four trees, so it is not excluded.

## Pages actually opened

- JSON: https://www.rfc-editor.org/rfc/rfc8259
- TOML v1.0.0: https://toml.io/en/v1.0.0
- CloudFormation template sections: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html
- CloudFormation format version: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/format-version-structure.html
- CloudFormation Resources: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resources-section-structure.html
- CloudFormation Transform: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/transform-section-structure.html
- ARM template structure: https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/syntax
- Helm charts: https://helm.sh/docs/topics/charts/
- Helm chart templates: https://helm.sh/docs/chart_template_guide/
- Helm values files: https://helm.sh/docs/chart_template_guide/values_files/
- Serverless Framework `serverless.yml`: https://www.serverless.com/framework/docs/providers/aws/guide/serverless.yml
- Jenkins pipeline syntax: https://www.jenkins.io/doc/book/pipeline/syntax/
- Using a Jenkinsfile: https://www.jenkins.io/doc/book/pipeline/jenkinsfile/
- GNU make manual (text): https://www.gnu.org/software/make/manual/make.txt (sections 3.2 and 3.3)
- PowerShell scripts: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_scripts
- PowerShell module manifests: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_module_manifests
- PSScriptAnalyzer rules: https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/rules/readme
- Terraform JSON syntax: https://developer.hashicorp.com/terraform/language/syntax/json

`https://www.gnu.org/software/make/manual/html_node/Makefile-Names.html` returned 403 to the fetch client. The text manual at `make.txt` on the same host is the page the Makefile names are taken from.
