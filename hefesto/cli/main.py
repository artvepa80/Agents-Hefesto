#!/usr/bin/env python3
"""
HEFESTO CLI - Command Line Interface

Provides commands for running Hefesto API server and analyzing code.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import sys
from typing import Optional, Tuple

import click

from hefesto.__version__ import __version__
from hefesto.telemetry.client import TelemetryClient

# Initialize telemetry
telemetry = TelemetryClient()


def _detect_command(argv: list[str]) -> str:
    """
    Return a stable telemetry command name:
      - "serve"
      - "analyze"
      - "telemetry status"
      - "telemetry clear"
    Ignores global flags like --help/--version and their values.
    """
    tokens = argv[1:]  # skip program name

    # Pre-checks for help/version which might not be caught by generic logic
    if any(a in ("-h", "--help") for a in tokens):
        return "help"
    if any(a == "--version" for a in tokens):
        return "version"

    cmd_parts = _parse_command_parts(tokens)

    if not cmd_parts:
        return "unknown"
    return " ".join(cmd_parts)


def _parse_command_parts(tokens: list[str]) -> list[str]:
    cmd_parts: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t.startswith("-"):
            if "=" not in t and (i + 1) < len(tokens) and not tokens[i + 1].startswith("-"):
                i += 2
            else:
                i += 1
            continue

        cmd_parts.append(t)
        i += 1

        if t == "telemetry":
            i = _parse_telemetry_subcommand(tokens, i, cmd_parts)
            break

        break
    return cmd_parts


def _parse_telemetry_subcommand(tokens: list[str], i: int, cmd_parts: list[str]) -> int:
    while i < len(tokens) and tokens[i].startswith("-"):
        if "=" not in tokens[i] and (i + 1) < len(tokens) and not tokens[i + 1].startswith("-"):
            i += 2
        else:
            i += 1
    if i < len(tokens) and not tokens[i].startswith("-"):
        cmd_parts.append(tokens[i])
    return i


def _exit(code: int) -> None:
    raise SystemExit(code)


@click.group()
@click.version_option(version=__version__)
def cli():
    """
    HEFESTO - AI-Powered Code Quality Guardian

    Autonomous code analysis, refactoring, and quality assurance.
    """
    pass


@cli.command()
@click.option("--host", default=None, help="Host to bind (default: 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to bind (default: 8080)")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes")
def serve(host: Optional[str], port: Optional[int], reload: bool):
    """
    Start Hefesto API server.

    Example:
        hefesto serve
        hefesto serve --port 9000
        hefesto serve --reload  # Development mode
    """
    from hefesto.pro_optional import HAS_API_HARDENING

    if not HAS_API_HARDENING:
        click.echo(
            "This feature requires Hefesto PRO/OMEGA. " "Install from the private distribution.",
            err=True,
        )
        _exit(1)

    try:
        from hefesto.server import create_app
    except ImportError as e:
        click.echo(f"Server dependencies missing: {e}", err=True)
        click.echo("Install with: pip install hefesto-ai[server]", err=True)
        _exit(1)

    from hefesto.pro_optional import HardeningSettings, apply_hardening

    settings = HardeningSettings()
    resolved_host = host or settings.bind_host
    resolved_port = port or 8080

    app = create_app()
    apply_hardening(app, settings=settings)

    # Mount IRIS ingest endpoints if available (PRO + IRIS installed)
    _mount_iris_ingest(app)

    click.echo(f"Starting Hefesto API server on {resolved_host}:{resolved_port}")
    if HAS_API_HARDENING:
        click.echo("  Hardening: ACTIVE (CORS, auth, rate-limit, request-id)")

    import uvicorn

    uvicorn.run(
        app,
        host=resolved_host,
        port=resolved_port,
        reload=reload,
        log_level="info",
    )


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True), required=True)
@click.option(
    "--severity",
    default="MEDIUM",
    type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
    help="Minimum severity filter (default: MEDIUM)",
)
@click.option(
    "--output",
    type=click.Choice(["text", "json", "html"]),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--exclude",
    default="",
    help="Comma-separated patterns to exclude (e.g., tests/,docs/)",
)
@click.option("--save-html", help="Save HTML report to file")
@click.option(
    "--fail-on",
    type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"], case_sensitive=False),
    default=None,
    help="Exit with code 1 if issues at this severity or higher are found",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Minimal output (summary only, no pipeline details)",
)
@click.option(
    "--max-issues",
    type=int,
    default=None,
    help="Maximum number of issues to display (default: all)",
)
@click.option(
    "--exclude-types",
    default="",
    help=(
        "Comma-separated issue types to exclude from gate"
        " (e.g., VERY_HIGH_COMPLEXITY,LONG_FUNCTION)"
    ),
)
# -- Scope gating flags (PRO EPIC 1) --
@click.option("--include-third-party", is_flag=True, help="Include third-party files in analysis")
@click.option("--include-generated", is_flag=True, help="Include generated files in analysis")
@click.option("--include-fixtures", is_flag=True, help="Include test fixture files in analysis")
@click.option("--scope-allow", multiple=True, help="Extra path patterns to include (repeatable)")
@click.option("--scope-deny", multiple=True, help="Extra path patterns to exclude (repeatable)")
# -- Reliability drift flags (EPIC 4) --
@click.option(
    "--enable-memory-budget-gate",
    is_flag=True,
    help="Enable opt-in memory budget gate (EPIC 4). Threshold via env var.",
)
# -- Enrichment flags (PRO EPIC 3) --
@click.option(
    "--enrich",
    type=click.Choice(["off", "local", "remote"], case_sensitive=False),
    default="off",
    help="Enrichment mode: off (default), local, or remote (requires PRO)",
)
@click.option("--enrich-provider", multiple=True, help="Enrichment provider allowlist (repeatable)")
@click.option(
    "--enrich-timeout", type=int, default=30, help="Enrichment timeout in seconds (default: 30)"
)
@click.option("--enrich-cache-ttl", type=int, default=300, help="Enrichment cache TTL in seconds")
@click.option("--enrich-cache-max", type=int, default=500, help="Enrichment cache max entries")
def analyze(
    paths: Tuple[str, ...],
    severity: str,
    output: str,
    exclude: str,
    save_html: Optional[str],
    fail_on: Optional[str],
    quiet: bool,
    max_issues: Optional[int],
    exclude_types: str,
    enable_memory_budget_gate: bool,
    include_third_party: bool,
    include_generated: bool,
    include_fixtures: bool,
    scope_allow: Tuple[str, ...],
    scope_deny: Tuple[str, ...],
    enrich: str,
    enrich_provider: Tuple[str, ...],
    enrich_timeout: int,
    enrich_cache_ttl: int,
    enrich_cache_max: int,
):
    """
    Analyze code files or directories.

    Supports multiple paths in a single command.

    Examples:
        hefesto analyze mycode.py
        hefesto analyze src/ lib/ types/
        hefesto analyze . --severity HIGH
        hefesto analyze . --output json
        hefesto analyze . --fail-on HIGH  # CI gate
        hefesto analyze . --quiet  # Summary only
    """
    # When --output json, all non-JSON text goes to stderr so stdout is pure JSON.
    json_mode = output == "json"

    paths_list = list(paths)
    _echo_analysis_config(paths_list, severity, exclude, quiet, json_mode)

    # Parse exclude patterns
    exclude_patterns = [p.strip() for p in exclude.split(",") if p.strip()]

    # Build scope gating config (PRO EPIC 1)
    scope_config = _build_scope_config(
        include_third_party,
        include_generated,
        include_fixtures,
        scope_allow,
        scope_deny,
    )

    # Build enrichment config (PRO EPIC 3)
    enrich_config = _build_enrich_config(
        enrich,
        enrich_provider,
        enrich_timeout,
        enrich_cache_ttl,
        enrich_cache_max,
    )

    try:
        engine = _setup_analyzer_engine(severity, quiet, json_mode, scope_config, enrich_config)
        if not engine:
            _exit(1)

        # Memory budget gate (EPIC 4, opt-in)
        budget_result = None
        if enable_memory_budget_gate:
            from hefesto.core.memory_budget_gate import MemoryBudgetGate

            gate = MemoryBudgetGate()
            (all_file_results, total_loc, total_duration, source_cache), budget_result = (
                gate.measure(lambda: _run_analysis_loop(engine, paths_list, exclude_patterns))
            )
            if not quiet and not json_mode:
                click.echo(f"  Memory gate: {budget_result.message}", err=json_mode)
        else:
            all_file_results, total_loc, total_duration, source_cache = _run_analysis_loop(
                engine, paths_list, exclude_patterns
            )

        _run_ml_analysis(all_file_results, source_cache, quiet, json_mode)

        meta = engine._build_meta() if hasattr(engine, "_build_meta") else {}
        if budget_result is not None:
            meta["dynamic_budget_results"] = budget_result.to_dict()

        combined_report = _generate_report(
            all_file_results,
            total_loc,
            total_duration,
            output,
            save_html,
            meta=meta,
        )

        _print_report(combined_report, output, save_html, quiet, max_issues)

        exit_code = _determine_exit_code(combined_report, fail_on, exclude_types, quiet, json_mode)
        _exit(exit_code)

    except Exception as e:
        click.echo(f"Analysis failed: {e}", err=True)
        _exit(1)


def _echo_analysis_config(paths_list, severity, exclude, quiet, json_mode=False):
    use_stderr = json_mode
    if not quiet:
        click.echo(f"Analyzing: {', '.join(paths_list)}", err=use_stderr)
        click.echo(f"Minimum severity: {severity.upper()}", err=use_stderr)

    exclude_patterns = [p.strip() for p in exclude.split(",") if p.strip()]
    if exclude_patterns and not quiet:
        click.echo(f"Excluding: {', '.join(exclude_patterns)}", err=use_stderr)


@cli.command()
def info():
    """Show Hefesto configuration and license info."""
    click.echo(
        "This feature requires Hefesto PRO/OMEGA. " "Install from the private distribution.",
        err=True,
    )
    _exit(1)


@cli.command()
def check():
    """Check Hefesto installation and dependencies."""
    import importlib.util

    click.echo("Checking Hefesto installation...")
    click.echo("")

    # Check Python version
    py_version = sys.version_info
    click.echo(f"Python: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 10):
        click.echo("   [ERROR] Python 3.10+ required", err=True)
    else:
        click.echo("   [OK] Version OK")

    click.echo("")
    click.echo("Core Dependencies:")

    deps = {
        "click": "Click (CLI framework)",
        "pydantic": "Pydantic (data validation)",
        "radon": "Radon (complexity metrics)",
        "bandit": "Bandit (security scanning)",
        "vulture": "Vulture (dead code detection)",
        "pylint": "Pylint (linting)",
        "jinja2": "Jinja2 (report templates)",
    }

    for module_name, description in deps.items():
        spec = importlib.util.find_spec(module_name)
        if spec:
            click.echo(f"   [OK] {description}")
        else:
            click.echo(f"   [MISSING] {description}")

    click.echo("")
    click.echo("Installation check complete!")


@cli.command()
@click.argument("license_key")
def activate(license_key: str):
    """
    Activate Hefesto Professional with license key.

    Usage:
        hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX
    """
    click.echo(
        "This feature requires Hefesto PRO/OMEGA. " "Install from the private distribution.",
        err=True,
    )
    _exit(1)


@cli.command()
def deactivate():
    """
    Deactivate Hefesto Professional license.

    This will remove your license key and revert to free tier.
    """
    click.echo(
        "This feature requires Hefesto PRO/OMEGA. " "Install from the private distribution.",
        err=True,
    )
    _exit(1)


@cli.command()
def status():
    """
    Show current license status and tier information.
    """
    click.echo(
        "This feature requires Hefesto PRO/OMEGA. " "Install from the private distribution.",
        err=True,
    )
    _exit(1)


@cli.command()
@click.option(
    "--project-root", type=click.Path(exists=True), default=".", help="Project root directory"
)  # noqa: E501
def check_ci_parity(project_root: str):
    """
    Check for discrepancies between local and CI environments.

    This validator compares:
    - Tool versions (flake8, black, isort, pytest)
    - Flake8 configuration (max-line-length, ignore rules)
    - Python version compatibility

    Example:
        hefesto check-ci-parity
        hefesto check-ci-parity --project-root /path/to/project
    """
    from pathlib import Path

    from hefesto.validators.ci_parity import CIParityChecker

    click.echo("Checking CI parity...")
    click.echo("")

    checker = CIParityChecker(Path(project_root))
    issues = checker.check_all()
    checker.print_report(issues)

    # Exit with error if HIGH priority issues found
    high_priority = [i for i in issues if i.severity.value == "HIGH"]
    if high_priority:
        _exit(1)


@cli.command()
@click.argument("test_directory", type=click.Path(exists=True), default="tests")
def check_test_contradictions(test_directory: str):
    """
    Detect contradictory assertions in test suite.

    Finds tests that call the same function with the same inputs
    but expect different outputs - a sign of logical inconsistency.

    Example:
        hefesto check-test-contradictions tests/
        hefesto check-test-contradictions .
    """
    from hefesto.validators.test_contradictions import TestContradictionDetector

    click.echo(f"Checking test contradictions in: {test_directory}")
    click.echo("")

    detector = TestContradictionDetector(test_directory)
    contradictions = detector.find_contradictions()
    detector.print_report(contradictions)

    # Exit with error if contradictions found
    if contradictions:
        _exit(1)


@cli.command()
@click.option("--force", is_flag=True, help="Overwrite existing hooks")
def install_hooks(force: bool):
    """
    Install/update Hefesto git hooks (pre-commit + pre-push).

    Copies hooks from scripts/git-hooks/ to .git/hooks/.
    Hooks use venv-first Python resolution and are portable across platforms.

    Example:
        hefesto install-hooks
        hefesto install-hooks --force
    """
    repo_root = _find_repo_root()
    if not repo_root:
        _exit(1)

    for hook_name in ("pre-commit", "pre-push"):
        _install_hook(repo_root, hook_name, force)


@cli.group()
def telemetry_cmd():
    """Telemetry utilities (local-only, privacy-first)."""
    pass


@telemetry_cmd.command("status")
def telemetry_status():
    """Show telemetry config and local file status."""
    s = telemetry.get_status()
    click.echo("Telemetry Status:")
    click.echo(f"  Enabled:   {bool(s.get('enabled'))}")
    click.echo(f"  Path:      {s.get('path')}")
    click.echo(f"  Size:      {s.get('size_bytes')} bytes")
    click.echo(f"  Max Bytes: {s.get('max_bytes')}")
    click.echo(f"  Max Files: {s.get('max_files')}")
    click.echo(f"  Schema:    v{s.get('schema_version')}")


@telemetry_cmd.command("clear")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def telemetry_clear(yes: bool):
    """Delete local telemetry data (active + rotated backups)."""
    if not yes:
        ok = click.confirm(
            "This will delete local telemetry files (active + rotated). Continue?",
            default=False,
        )
        if not ok:
            click.echo("Cancelled.")
            return
    telemetry.clear_data()
    click.echo("Telemetry data cleared.")


# Register the group
cli.add_command(telemetry_cmd, name="telemetry")


def main() -> None:
    # Start telemetry if valid command
    cmd = _detect_command(list(sys.argv))
    telemetry.start(command=cmd, version=__version__, argv=list(sys.argv))

    try:
        cli.main(prog_name="hefesto", standalone_mode=False)
        telemetry.end(exit_code=0)
        sys.exit(0)
    except SystemExit as e:
        code = e.code
        if code is None:
            code = 0
        elif not isinstance(code, int):
            code = 1
        telemetry.end(exit_code=int(code))
        sys.exit(code)
    except Exception as e:
        # Unexpected crash
        click.echo(f"Unexpected error: {e}", err=True)
        telemetry.end(exit_code=1)
        sys.exit(1)


def _find_repo_root():
    import subprocess
    from pathlib import Path

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return parent

    click.echo("Error: Not a git repository!", err=True)
    click.echo("   Run this command from within a git repository.")
    return None


def _install_hook(repo_root, hook_name, force):
    import os
    import shutil
    import stat

    git_dir = repo_root / ".git"
    source_hook = repo_root / "scripts" / "git-hooks" / hook_name

    if not source_hook.exists():
        click.echo(f"Skipping {hook_name}: template not found at {source_hook}", err=True)
        return

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    dest_hook = hooks_dir / hook_name

    if dest_hook.exists() and not force:
        try:
            with open(source_hook, "r") as src, open(dest_hook, "r") as dst:
                if src.read() == dst.read():
                    click.echo(f"{hook_name}: already up to date.")
                    return
        except Exception:
            pass
        click.echo(f"{hook_name}: already exists at {dest_hook}. Use --force to overwrite.")
        return

    try:
        shutil.copy2(source_hook, dest_hook)
        st = os.stat(dest_hook)
        os.chmod(dest_hook, st.st_mode | stat.S_IEXEC)
        click.echo(f"{hook_name}: installed to {dest_hook}")
    except Exception as e:
        click.echo(f"Error installing {hook_name}: {e}", err=True)
        _exit(1)


def _mount_iris_ingest(app):
    """Mount IRIS Learning Risk Engine ingest endpoints if iris is installed.

    Uses the same optional-import pattern as other PRO features.
    Store selection: BigQueryStore when IRIS_BQ_PROJECT is set, else InMemoryStore.
    """
    try:
        import os

        from iris.core.ingest import create_ingest_router

        if os.environ.get("IRIS_BQ_PROJECT"):
            from iris.core.ingest import BigQueryStore

            store = BigQueryStore(
                project_id=os.environ["IRIS_BQ_PROJECT"],
                dataset=os.environ.get("IRIS_BQ_DATASET", "omega_audit"),
            )
        else:
            from iris.core.ingest import InMemoryStore

            store = InMemoryStore()

        router = create_ingest_router(store)
        if router is not None:
            app.include_router(router)
            click.echo("  IRIS: ingest endpoints mounted (/v1/ingest/)")
    except ImportError:
        pass  # IRIS not installed — skip silently


def _setup_analyzer_engine(severity, quiet, json_mode=False, scope_config=None, enrich_config=None):
    from hefesto.analyzers import (
        BestPracticesAnalyzer,
        CodeSmellAnalyzer,
        ComplexityAnalyzer,
        SecurityAnalyzer,
    )
    from hefesto.core.analyzer_engine import AnalyzerEngine

    # When json_mode, suppress verbose output so stdout stays clean
    verbose = not quiet and not json_mode

    if verbose:
        import click

        click.echo("")

    try:
        engine = AnalyzerEngine(
            severity_threshold=severity,
            verbose=verbose,
            scope_config=scope_config,
            enrich_config=enrich_config,
        )

        # Register all analyzers
        engine.register_analyzer(ComplexityAnalyzer())
        engine.register_analyzer(CodeSmellAnalyzer())
        engine.register_analyzer(SecurityAnalyzer())
        engine.register_analyzer(BestPracticesAnalyzer())

        # EPIC 4: Resource Safety Pack v1
        from hefesto.security.packs.resource_safety_v1 import ResourceSafetyAnalyzer

        engine.register_analyzer(ResourceSafetyAnalyzer())

        return engine
    except Exception as e:
        import click

        click.echo(f"Analysis failed: {e}", err=True)
        return None


def _run_analysis_loop(engine, paths_list, exclude_patterns):
    all_file_results = []
    total_loc = 0
    total_duration = 0.0

    for path in paths_list:
        report = engine.analyze_path(path, exclude_patterns)
        all_file_results.extend(report.file_results)
        total_loc += report.summary.total_loc
        total_duration += report.summary.duration_seconds

    source_cache = getattr(engine, "source_cache", {})
    return all_file_results, total_loc, total_duration, source_cache


def _run_ml_analysis(all_file_results, source_cache, quiet, json_mode):
    """Run ML-powered semantic duplication analysis (OMEGA/PRO only)."""
    import os

    tier = os.environ.get("HEFESTO_TIER", "")
    if tier not in ("professional", "omega"):
        return
    try:
        from hefesto.analyzers.semantic_duplication import find_semantic_duplicates

        if not quiet and not json_mode:
            import click

            click.echo("Running ML semantic analysis...", err=json_mode)
        ml_issues, stats = find_semantic_duplicates(all_file_results, source_cache)
        if ml_issues:
            file_map = {fr.file_path: fr for fr in all_file_results}
            for issue in ml_issues:
                fr = file_map.get(issue.file_path)
                if fr:
                    fr.issues.append(issue)
            if not quiet and not json_mode:
                import click

                click.echo(
                    "   ML: {} functions, {} duplicates ({:.0f}ms)".format(
                        stats["functions"], stats["pairs"], stats["duration_ms"]
                    ),
                    err=json_mode,
                )
        elif not quiet and not json_mode:
            import click

            click.echo("   ML: No semantic duplicates found", err=json_mode)
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug("ML analysis skipped: %s", e)


def _generate_report(all_file_results, total_loc, total_duration, output, save_html, meta=None):
    from hefesto.core.analysis_models import AnalysisReport, AnalysisSummary

    # Get all issues from combined file results
    all_issues = []
    for file_result in all_file_results:
        all_issues.extend(file_result.issues)

    # Create combined report
    combined_summary = AnalysisSummary(
        files_analyzed=len(all_file_results),
        total_issues=len(all_issues),
        critical_issues=sum(1 for i in all_issues if i.severity.value == "CRITICAL"),
        high_issues=sum(1 for i in all_issues if i.severity.value == "HIGH"),
        medium_issues=sum(1 for i in all_issues if i.severity.value == "MEDIUM"),
        low_issues=sum(1 for i in all_issues if i.severity.value == "LOW"),
        total_loc=total_loc,
        duration_seconds=total_duration,
    )

    combined_report = AnalysisReport(
        summary=combined_summary,
        file_results=all_file_results,
        meta=meta or {},
    )
    return combined_report


def _print_report(combined_report, output, save_html, quiet, max_issues):
    import click

    from hefesto.reports import HTMLReporter, JSONReporter, TextReporter

    json_mode = output == "json"

    # Apply max_issues limit if specified (affects display only)
    display_issues = combined_report.get_all_issues()
    if max_issues and len(display_issues) > max_issues:
        if not quiet:
            click.echo(
                f"(Showing first {max_issues} of {len(display_issues)} issues)",
                err=json_mode,
            )

    # Generate output
    if output == "text":
        reporter = TextReporter()
        result = reporter.generate(combined_report)
        click.echo(result)
    elif output == "json":
        reporter = JSONReporter()
        result = reporter.generate(combined_report)
        click.echo(result)
    elif output == "html":
        reporter = HTMLReporter()
        result = reporter.generate(combined_report)

        if save_html:
            with open(save_html, "w", encoding="utf-8") as f:
                f.write(result)
            click.echo(f"HTML report saved to: {save_html}")
        else:
            click.echo(result)


def _determine_exit_code(combined_report, fail_on, exclude_types, quiet, json_mode=False):
    import click

    use_stderr = json_mode
    exit_code = 0

    if fail_on:
        severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        fail_on_idx = severity_order.index(fail_on.upper())

        # Parse exclude_types for gate filtering
        excluded_types = set()
        if exclude_types:
            excluded_types = {t.strip().upper() for t in exclude_types.split(",") if t.strip()}

        # Filter issues for gate evaluation (exclude specified types)
        gate_issues = [
            issue
            for issue in combined_report.get_all_issues()
            if issue.issue_type.value not in excluded_types
        ]

        for issue in gate_issues:
            issue_idx = severity_order.index(issue.severity.value)
            if issue_idx >= fail_on_idx:
                exit_code = 1
                break

        if exit_code == 1 and not quiet:
            click.echo(
                f"\nGate failure: {fail_on.upper()} or higher issues found (exit 1)",
                err=use_stderr,
            )
        elif not quiet:
            if excluded_types:
                click.echo(
                    f"\nGate passed: no {fail_on.upper()}+ issues"
                    f" after excluding {len(excluded_types)} type(s))",
                    err=use_stderr,
                )
            else:
                click.echo(
                    f"\nGate passed: no {fail_on.upper()}+ issues",
                    err=use_stderr,
                )
    # Without --fail-on: always exit 0 (findings reported in output, not via exit code)

    return exit_code


@cli.command()
@click.argument("template_file", type=click.Path(exists=True))
@click.option("--region", required=True, help="AWS Region")
@click.option("--stack-name", help="CloudFormation Stack Name")
@click.option("--tags", help="Tags to resolve (key=value,key2=value2)")
@click.option(
    "--fail-on",
    type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
    help="Fail if severity >= level",
)
def drift(template_file, region, stack_name, tags, fail_on):
    """Detect configuration drift in IaC."""
    from hefesto.core.drift_runner import DriftRunner

    # Parse tags
    tag_dict = {}
    if tags:
        try:
            for item in tags.split(","):
                k, v = item.split("=")
                tag_dict[k.strip()] = v.strip()
        except ValueError:
            click.echo("Error: Invalid tags format. Use key=value,key2=value2", err=True)
            sys.exit(1)

    runner = DriftRunner()
    result = runner.run(
        template_path=template_file,
        region=region,
        stack_name=stack_name,
        tags=tag_dict,
    )

    # Print Report
    click.echo("\nDrift Analysis Report")
    click.echo("---------------------")
    click.echo(f"Region: {result.summary['region']}")
    if result.summary.get("stack_name"):
        click.echo(f"Stack: {result.summary['stack_name']}")

    click.echo(f"\nFindings: {len(result.findings)}")
    for finding in result.findings:
        click.echo(f"- [{finding.severity}] {finding.evidence}")

    # Exit Code Logic
    exit_code = 0
    severity_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

    # Determine threshold (default to HIGH if not specified)
    threshold_level = fail_on if fail_on else "HIGH"
    threshold = severity_map[threshold_level]

    for finding in result.findings:
        if severity_map.get(finding.severity, 0) >= threshold:
            exit_code = 2
            break

    sys.exit(exit_code)


def _build_scope_config(
    include_third_party, include_generated, include_fixtures, scope_allow, scope_deny
):
    """Build ScopeGatingConfig from CLI flags, or None if PRO unavailable."""
    from hefesto.pro_optional import HAS_SCOPE_GATING, ScopeGatingConfig

    if not HAS_SCOPE_GATING:
        return None

    return ScopeGatingConfig(
        include_third_party=include_third_party,
        include_generated=include_generated,
        include_fixtures=include_fixtures,
        allow_patterns=list(scope_allow),
        deny_patterns=list(scope_deny),
    )


def _build_enrich_config(
    enrich, enrich_provider, enrich_timeout, enrich_cache_ttl, enrich_cache_max
):
    """Build EnrichmentConfig from CLI flags, or None if off/unavailable."""
    if enrich == "off":
        return None

    from hefesto.pro_optional import HAS_ENRICHMENT, EnrichmentConfig

    if not HAS_ENRICHMENT or EnrichmentConfig is None:
        click.echo("Warning: --enrich requires Hefesto PRO; enrichment will be skipped.", err=True)
        return None

    if not enrich_provider:
        click.echo(
            "Warning: enrichment enabled but no providers configured; will be skipped.", err=True
        )

    return EnrichmentConfig(
        enabled=True,
        local_only=(enrich == "local"),
        timeout_seconds=float(enrich_timeout),
        cache_ttl_seconds=enrich_cache_ttl,
        cache_max_size=enrich_cache_max,
        providers=list(enrich_provider),
    )


if __name__ == "__main__":
    main()
