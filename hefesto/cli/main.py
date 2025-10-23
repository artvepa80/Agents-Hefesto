#!/usr/bin/env python3
"""
HEFESTO CLI - Command Line Interface

Provides commands for running Hefesto API server and analyzing code.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import sys
from typing import Optional

import click

from hefesto.__version__ import __version__
from hefesto.config import get_settings


@click.group()
@click.version_option(version=__version__)
def cli():
    """
    🔨 HEFESTO - AI-Powered Code Quality Guardian

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
    try:
        import uvicorn

        from hefesto.api.health import app
    except ImportError as e:
        click.echo(f"❌ Error: {e}", err=True)
        click.echo("\n💡 Install API dependencies:", err=True)
        click.echo("   pip install hefesto-ai[api]", err=True)
        sys.exit(1)

    settings = get_settings()

    host = host or settings.api_host
    port = port or settings.api_port

    click.echo(f"🔨 HEFESTO v{__version__}")
    click.echo(f"🌐 Starting server at http://{host}:{port}")
    click.echo(f"📚 Docs: http://{host}:{port}/docs")
    click.echo(f"🔍 Health: http://{host}:{port}/ping")
    click.echo("")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=reload,
    )


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--severity", default="MEDIUM", help="Minimum severity (LOW/MEDIUM/HIGH/CRITICAL)")
@click.option("--output", type=click.Choice(["text", "json", "html"]), default="text")
@click.option(
    "--exclude", default="", help="Comma-separated patterns to exclude (e.g., tests/,docs/)"
)
@click.option("--save-html", help="Save HTML report to file")
def analyze(path: str, severity: str, output: str, exclude: str, save_html: Optional[str]):
    """
    Analyze code file or directory.

    Example:
        hefesto analyze mycode.py
        hefesto analyze src/ --severity HIGH
        hefesto analyze . --output json
        hefesto analyze . --output html --save-html report.html
    """
    from hefesto.analyzers import (
        ComplexityAnalyzer,
        CodeSmellAnalyzer,
        SecurityAnalyzer,
        BestPracticesAnalyzer,
    )
    from hefesto.core.analyzer_engine import AnalyzerEngine
    from hefesto.reports import TextReporter, JSONReporter, HTMLReporter

    click.echo(f"🔍 Analyzing: {path}")
    click.echo(f"📊 Minimum severity: {severity}")

    # Parse exclude patterns
    exclude_patterns = [p.strip() for p in exclude.split(",") if p.strip()]

    if exclude_patterns:
        click.echo(f"🚫 Excluding: {', '.join(exclude_patterns)}")

    click.echo("")

    # Create analyzer engine (with verbose mode)
    try:
        engine = AnalyzerEngine(severity_threshold=severity, verbose=True)

        # Register all analyzers
        engine.register_analyzer(ComplexityAnalyzer())
        engine.register_analyzer(CodeSmellAnalyzer())
        engine.register_analyzer(SecurityAnalyzer())
        engine.register_analyzer(BestPracticesAnalyzer())

        # Run analysis
        report = engine.analyze_path(path, exclude_patterns)

        # Generate output
        if output == "text":
            reporter = TextReporter()
            result = reporter.generate(report)
            click.echo(result)
        elif output == "json":
            reporter = JSONReporter()
            result = reporter.generate(report)
            click.echo(result)
        elif output == "html":
            reporter = HTMLReporter()
            result = reporter.generate(report)

            if save_html:
                with open(save_html, "w", encoding="utf-8") as f:
                    f.write(result)
                click.echo(f"✅ HTML report saved to: {save_html}")
            else:
                click.echo(result)

        # Exit with error code if critical issues found
        if report.summary.critical_issues > 0:
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def info():
    """Show Hefesto configuration and license info."""
    from hefesto import get_info  # noqa: F401
    from hefesto.llm.license_validator import get_license_validator

    settings = get_settings()
    validator = get_license_validator()
    license_info = validator.get_info()

    click.echo(f"🔨 HEFESTO v{__version__}")
    click.echo("")
    click.echo("📦 Configuration:")
    click.echo(f"   Environment: {settings.environment}")
    click.echo(f"   GCP Project: {settings.gcp_project_id or 'Not configured'}")
    click.echo(f"   Gemini API Key: {'✅ Set' if settings.gemini_api_key else '❌ Not set'}")
    click.echo(f"   Model: {settings.gemini_model}")
    click.echo("")
    click.echo("💰 Budget:")
    click.echo(f"   Daily Limit: ${settings.daily_budget_usd}")
    click.echo(f"   Monthly Limit: ${settings.monthly_budget_usd}")
    click.echo("")
    click.echo("📜 License:")
    click.echo(f"   Tier: {license_info['tier'].upper()}")
    click.echo(
        f"   Pro Features: {'✅ Enabled' if license_info['is_pro'] else '❌ Disabled (upgrade to Pro)'}  # noqa: E501"
    )

    if license_info["is_pro"]:
        click.echo("   Enabled Features:")
        for feature in sorted(license_info["features_enabled"]):
            click.echo(f"      • {feature}")
    else:
        click.echo("")
        click.echo("💡 Upgrade to Pro for:")
        click.echo("   • ML-based semantic analysis")
        click.echo("   • Duplicate detection")
        click.echo("   • CI/CD automation")
        click.echo("   • Advanced analytics")
        click.echo("")
        click.echo("🛒 Purchase: https://buy.stripe.com/hefesto-pro")


@cli.command()
def check():
    """Check Hefesto installation and dependencies."""
    import importlib.util

    click.echo("🔍 Checking Hefesto installation...")
    click.echo("")

    # Check Python version
    py_version = sys.version_info
    click.echo(f"🐍 Python: {py_version.major}.{py_version.minor}.{py_version.micro}")
    if py_version < (3, 10):
        click.echo("   ❌ Python 3.10+ required", err=True)
    else:
        click.echo("   ✅ Version OK")

    click.echo("")
    click.echo("📦 Dependencies:")

    # Core dependencies
    deps = {
        "fastapi": "FastAPI (API server)",
        "pydantic": "Pydantic (data validation)",
        "google.cloud.bigquery": "BigQuery (tracking)",
        "google.generativeai": "Gemini API (LLM)",
    }

    for module_name, description in deps.items():
        spec = importlib.util.find_spec(module_name)
        if spec:
            click.echo(f"   ✅ {description}")
        else:
            click.echo(f"   ❌ {description} - Not installed")

    # Pro dependencies
    click.echo("")
    click.echo("🌟 Pro Dependencies (Optional):")

    pro_deps = {
        "sentence_transformers": "Sentence Transformers (semantic analysis)",
        "torch": "PyTorch (ML backend)",
    }

    for module_name, description in pro_deps.items():
        spec = importlib.util.find_spec(module_name)
        if spec:
            click.echo(f"   ✅ {description}")
        else:
            click.echo(f"   ⚠️  {description} - Install with: pip install hefesto-ai[pro]")

    click.echo("")
    click.echo("✅ Installation check complete!")


@cli.command()
@click.argument("license_key")
def activate(license_key: str):
    """
    Activate Hefesto Professional with license key.

    Usage:
        hefesto activate HFST-XXXX-XXXX-XXXX-XXXX-XXXX
    """
    from hefesto.config.config_manager import ConfigManager
    from hefesto.licensing.key_generator import LicenseKeyGenerator

    click.echo("🔑 Activating Hefesto Professional...")

    # Validate format
    if not LicenseKeyGenerator.validate_format(license_key):
        click.echo("❌ Invalid license key format", err=True)
        click.echo("   Expected format: HFST-XXXX-XXXX-XXXX-XXXX-XXXX")
        return

    # Store license key
    config = ConfigManager()
    config.set_license_key(license_key)

    # Get tier info
    from hefesto.licensing.feature_gate import FeatureGate

    tier_info = FeatureGate.get_tier_info()

    click.echo("✅ License activated successfully!")
    click.echo(f"   Tier: {tier_info['tier_display']}")
    click.echo(f"   Key: {license_key}")
    click.echo("\n🚀 You now have access to:")

    feature_names = {
        "ml_semantic_analysis": "   • ML semantic code analysis",
        "ai_recommendations": "   • AI-powered code recommendations",
        "security_scanning": "   • Security vulnerability scanning",
        "automated_triage": "   • Automated issue triage",
        "github_gitlab_bitbucket": "   • Full Git integrations (GitHub, GitLab, Bitbucket)",
        "jira_slack_integration": "   • Jira & Slack integration",
        "priority_support": "   • Priority email support (4-8 hour response)",
        "analytics_dashboard": "   • Usage analytics dashboard",
    }

    for feature in tier_info["limits"]["features"]:
        if feature in feature_names:
            click.echo(feature_names[feature])


@cli.command()
def deactivate():
    """
    Deactivate Hefesto Professional license.

    This will remove your license key and revert to free tier.
    """
    from hefesto.config.config_manager import ConfigManager

    config = ConfigManager()
    license_key = config.get_license_key()

    if not license_key:
        click.echo("ℹ️  No active license found. Already using free tier.")
        return

    if click.confirm("⚠️  This will deactivate your Professional license. Continue?"):
        config.clear_license()
        click.echo("✅ License deactivated. Reverted to free tier.")
        click.echo("\n   To reactivate, use: hefesto activate YOUR-KEY")
    else:
        click.echo("❌ Deactivation cancelled.")


@cli.command()
def status():
    """
    Show current license status and tier information.
    """
    from hefesto.config.config_manager import ConfigManager
    from hefesto.licensing.feature_gate import FeatureGate

    config = ConfigManager()
    license_key = config.get_license_key()
    tier_info = FeatureGate.get_tier_info()

    click.echo("═" * 60)
    click.echo("HEFESTO LICENSE STATUS")
    click.echo("═" * 60)

    if license_key:
        click.echo(f"Tier: {tier_info['tier_display']}")
        click.echo(f"License: {license_key}")
    else:
        click.echo("Tier: Free")
        click.echo("License: Not activated")

    click.echo("\n" + "─" * 60)
    click.echo("USAGE LIMITS")
    click.echo("─" * 60)

    limits = tier_info["limits"]
    click.echo(f"Repositories: {limits['repositories']}")
    click.echo(f"LOC/month: {limits['loc_monthly']:,}")

    if limits["analysis_runs"] == float("inf"):
        click.echo("Analysis runs: Unlimited")
    else:
        click.echo(f"Analysis runs: {limits['analysis_runs']}/month")

    click.echo("\n" + "─" * 60)
    click.echo("AVAILABLE FEATURES")
    click.echo("─" * 60)

    feature_names = {
        "basic_quality": "Basic code quality checks",
        "pr_analysis": "Pull request analysis",
        "ide_integration": "IDE integration",
        "ml_semantic_analysis": "ML semantic code analysis",
        "ai_recommendations": "AI-powered recommendations",
        "security_scanning": "Security vulnerability scanning",
        "automated_triage": "Automated issue triage",
        "github_gitlab_bitbucket": "Full Git integrations",
        "jira_slack_integration": "Jira & Slack integration",
        "priority_support": "Priority email support",
        "analytics_dashboard": "Usage analytics dashboard",
    }

    for feature in limits["features"]:
        if feature in feature_names:
            click.echo(f"✓ {feature_names[feature]}")

    if tier_info["tier"] == "free":
        click.echo("\n" + "═" * 60)
        click.echo("UPGRADE TO PROFESSIONAL")
        click.echo("═" * 60)
        click.echo("🚀 First 25 teams: $59/month forever (40% off)")
        click.echo(f"   → {tier_info['founding_url']}")
        click.echo("\n   Or start 14-day free trial:")
        click.echo(f"   → {tier_info['upgrade_url']}")

    click.echo("═" * 60)


if __name__ == "__main__":
    cli()
