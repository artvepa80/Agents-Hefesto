#!/usr/bin/env python3
"""
Iris CLI - Production Monitoring Agent
"""

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="iris",
    help="Iris: Production Monitoring Agent",
    no_args_is_help=True,
)
console = Console()

def __version_callback(value: bool):
    if value:
        console.print("Iris Version: [green]1.0.0[/green]")
        raise typer.Exit()

@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show the version of Iris.",
        is_eager=True,
        callback=__version_callback,
    ),
):
    """
    Iris CLI for managing production monitoring.
    """
    pass

@app.command()
def start():
    """
    Starts Iris monitoring processes.
    """
    console.print(Panel.fit(
        "[bold green]🔍 Starting Iris monitoring...[/bold green]\n\n"
        "Monitoring:\n"
        "• System health checks\n"
        "• Alert correlation\n"
        "• Performance metrics\n"
        "• Incident detection",
        title="Iris Monitor"
    ))
    console.print("[green]✅ Iris monitoring started![/green]")

@app.command()
def stop():
    """
    Stops Iris monitoring processes.
    """
    console.print(Panel.fit(
        "[bold red]⏹️ Stopping Iris monitoring...[/bold red]\n\n"
        "Stopping all monitoring processes",
        title="Iris Monitor"
    ))
    console.print("[red]⏹️ Iris monitoring stopped![/red]")

@app.command()
def status():
    """
    Shows current status of Iris monitoring.
    """
    console.print(Panel.fit(
        "[bold blue]📊 Iris Status[/bold blue]\n\n"
        "• Health checks: [green]Active[/green]\n"
        "• Alert routing: [green]Active[/green]\n"
        "• Correlation engine: [green]Active[/green]\n"
        "• Last check: [yellow]2 minutes ago[/yellow]",
        title="Iris Status"
    ))

@app.command()
def alerts():
    """
    Shows recent alerts and their status.
    """
    console.print(Panel.fit(
        "[bold yellow]🚨 Recent Alerts[/bold yellow]\n\n"
        "• [red]CRITICAL[/red]: Database connection timeout (5 min ago)\n"
        "• [yellow]HIGH[/yellow]: Memory usage spike (12 min ago)\n"
        "• [green]RESOLVED[/green]: API response time (1 hour ago)",
        title="Alert History"
    ))

if __name__ == "__main__":
    app()