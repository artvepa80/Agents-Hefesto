#!/usr/bin/env python3
"""
HEFESTO CLI - Command Line Interface

Provides commands for running Hefesto API server and analyzing code.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

import click
import sys
import os
from typing import Optional

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
@click.option('--host', default=None, help='Host to bind (default: 0.0.0.0)')
@click.option('--port', default=None, type=int, help='Port to bind (default: 8080)')
@click.option('--reload', is_flag=True, help='Auto-reload on code changes')
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
        click.echo("   pip install hefesto[api]", err=True)
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
@click.argument('path', type=click.Path(exists=True))
@click.option('--severity', default='MEDIUM', help='Minimum severity (LOW/MEDIUM/HIGH/CRITICAL)')
@click.option('--output', type=click.Choice(['text', 'json']), default='text')
def analyze(path: str, severity: str, output: str):
    """
    Analyze code file or directory.
    
    Example:
        hefesto analyze mycode.py
        hefesto analyze src/ --severity HIGH
        hefesto analyze . --output json
    """
    click.echo(f"🔍 Analyzing: {path}")
    click.echo(f"📊 Minimum severity: {severity}")
    click.echo("")
    
    # TODO: Implement code analysis
    click.echo("⚠️  Analysis feature coming soon!")
    click.echo("💡 For now, use the API server:")
    click.echo("   hefesto serve")
    click.echo("   curl -X POST http://localhost:8080/suggest/refactor ...")


@cli.command()
def info():
    """Show Hefesto configuration and license info."""
    from hefesto import is_pro, get_info
    from hefesto.llm.license_validator import get_license_validator
    
    settings = get_settings()
    package_info = get_info()
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
    click.echo(f"   Pro Features: {'✅ Enabled' if license_info['is_pro'] else '❌ Disabled (upgrade to Pro)'}")
    
    if license_info['is_pro']:
        click.echo(f"   Enabled Features:")
        for feature in sorted(license_info['features_enabled']):
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
        'fastapi': 'FastAPI (API server)',
        'pydantic': 'Pydantic (data validation)',
        'google.cloud.bigquery': 'BigQuery (tracking)',
        'google.generativeai': 'Gemini API (LLM)',
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
        'sentence_transformers': 'Sentence Transformers (semantic analysis)',
        'torch': 'PyTorch (ML backend)',
    }
    
    for module_name, description in pro_deps.items():
        spec = importlib.util.find_spec(module_name)
        if spec:
            click.echo(f"   ✅ {description}")
        else:
            click.echo(f"   ⚠️  {description} - Install with: pip install hefesto[pro]")
    
    click.echo("")
    click.echo("✅ Installation check complete!")


if __name__ == '__main__':
    cli()

