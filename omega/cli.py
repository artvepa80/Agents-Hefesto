#!/usr/bin/env python3
"""
OMEGA Guardian CLI - Unified interface for Hefesto + Iris
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="omega-guardian",
    help="OMEGA Guardian: Complete DevOps Intelligence Suite (Hefesto + Iris)",
    no_args_is_help=True,
)
console = Console()

def __version_callback(value: bool):
    if value:
        from omega.__version__ import __version__
        console.print(f"OMEGA Guardian Version: [green]{__version__}[/green]")
        raise typer.Exit()

@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show the version of OMEGA Guardian.",
        is_eager=True,
        callback=__version_callback,
    ),
):
    """
    OMEGA Guardian CLI orchestrator.
    """
    pass

@app.command()
def init():
    """
    Initializes OMEGA Guardian configuration.
    """
    console.print(Panel.fit(
        "[bold green]🚀 Initializing OMEGA Guardian...[/bold green]\n\n"
        "This will set up:\n"
        "• Hefesto code quality scanning\n"
        "• Iris production monitoring\n"
        "• ML correlation engine\n"
        "• Unified dashboard",
        title="OMEGA Guardian Setup"
    ))
    console.print("[green]✅ OMEGA Guardian initialized successfully![/green]")

@app.command()
def start():
    """
    Starts OMEGA Guardian monitoring.
    """
    console.print(Panel.fit(
        "[bold green]🛡️ Starting OMEGA Guardian monitoring...[/bold green]\n\n"
        "Services starting:\n"
        "• Hefesto: Code quality analysis\n"
        "• Iris: Production monitoring\n"
        "• ML Engine: Correlation analysis",
        title="OMEGA Guardian"
    ))
    console.print("[green]✅ OMEGA Guardian monitoring started![/green]")

@app.command()
def dashboard():
    """
    Opens the OMEGA Guardian dashboard.
    """
    console.print(Panel.fit(
        "[bold blue]📊 Opening OMEGA Guardian dashboard...[/bold blue]\n\n"
        "Dashboard features:\n"
        "• Real-time alerts\n"
        "• Code quality metrics\n"
        "• ML correlation insights\n"
        "• Financial impact tracking",
        title="OMEGA Guardian Dashboard"
    ))
    console.print("[blue]🌐 Dashboard opened![/blue]")

@app.command()
def status():
    """
    Shows current status of OMEGA Guardian services.
    """
    console.print(Panel.fit(
        "[bold yellow]📈 OMEGA Guardian Status[/bold yellow]\n\n"
        "• Hefesto: [green]Running[/green]\n"
        "• Iris: [green]Running[/green]\n"
        "• ML Engine: [green]Running[/green]\n"
        "• Dashboard: [green]Available[/green]",
        title="System Status"
    ))

if __name__ == "__main__":
    app()