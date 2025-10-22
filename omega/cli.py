#!/usr/bin/env python3
"""
OMEGA Guardian CLI - Unified Command Line Interface
Combines Hefesto (Code Quality) + Iris (Production Monitoring) + ML Correlation
"""

import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

# Version info
__version__ = "1.0.0"
__author__ = "Narapa LLC"
__email__ = "support@omega-guardian.com"

def print_banner():
    """Print OMEGA Guardian banner"""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                    🛡️ OMEGA Guardian                          ║
║              Complete DevOps Intelligence Suite                ║
║                                                                ║
║  🔨 Hefesto (Code Quality) + 🔍 Iris (Production Monitoring)  ║
║  🧠 ML Correlation Engine = 🚀 Complete DevOps Intelligence   ║
╚════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_help():
    """Print comprehensive help"""
    help_text = """
🛡️ OMEGA Guardian - Complete DevOps Intelligence Suite

USAGE:
    omega-guardian <command> [options]

COMMANDS:
    🔨 hefesto <subcommand>     Code quality analysis (FREE tier)
    🔍 iris <subcommand>        Production monitoring (PRO tier)
    🧠 correlate <subcommand>   ML correlation engine (PRO tier)
    🚀 init                     Initialize OMEGA Guardian
    📊 dashboard                Open web dashboard
    💳 billing                  Manage subscription
    ❓ help                     Show this help

EXAMPLES:
    # Start with FREE Hefesto code quality
    omega-guardian hefesto scan /path/to/project
    
    # Initialize full OMEGA Guardian (PRO)
    omega-guardian init
    
    # Monitor production + correlate with code quality
    omega-guardian iris start --correlate
    
    # View correlation dashboard
    omega-guardian dashboard

TIERS:
    🆓 FREE:     Hefesto standalone (1 repo, 50K LOC/month)
    💎 PRO:      Full suite ($99/month) - Hefesto + Iris + ML Correlation
    🏢 ENTERPRISE: Custom pricing (100+ repos, SLA, dedicated support)

LEARN MORE:
    📖 Documentation: https://docs.omega-guardian.com
    🌐 Website: https://omega-guardian.com
    💬 Discord: https://discord.gg/omega-guardian
    🐦 Twitter: @OmegaGuardian

🔥 FOUNDING MEMBERS SPECIAL:
    Lock in $99/month FOREVER (Regular: $149/month)
    Limited to first 50 teams. [43 spots remaining]
    https://omega-guardian.com/founding-members
"""
    print(help_text)

def run_hefesto_command(args: List[str]) -> int:
    """Run Hefesto subcommand"""
    try:
        # Import and run Hefesto CLI
        from hefesto.cli import main as hefesto_main
        return hefesto_main(args)
    except ImportError:
        print("❌ Error: Hefesto not installed. Run: pip install omega-guardian")
        return 1
    except Exception as e:
        print(f"❌ Error running Hefesto: {e}")
        return 1

def run_iris_command(args: List[str]) -> int:
    """Run Iris subcommand"""
    try:
        # Import and run Iris CLI
        from iris.cli import main as iris_main
        return iris_main(args)
    except ImportError:
        print("❌ Error: Iris not installed. Run: pip install omega-guardian[pro]")
        return 1
    except Exception as e:
        print(f"❌ Error running Iris: {e}")
        return 1

def init_command(args: argparse.Namespace) -> int:
    """Initialize OMEGA Guardian"""
    print("🚀 Initializing OMEGA Guardian...")
    
    # Check if already initialized
    config_dir = Path.home() / ".omega-guardian"
    if config_dir.exists():
        print("✅ OMEGA Guardian already initialized")
        return 0
    
    # Create config directory
    config_dir.mkdir(exist_ok=True)
    
    # Create default config
    config_file = config_dir / "config.yaml"
    default_config = """# OMEGA Guardian Configuration
version: "1.0.0"
tier: "free"  # free, pro, enterprise

# Hefesto Configuration
hefesto:
  enabled: true
  languages: ["python", "javascript", "typescript"]
  exclude_patterns:
    - "node_modules/"
    - "venv/"
    - "*.test.js"
  
# Iris Configuration (PRO tier only)
iris:
  enabled: false
  project_id: ""
  bigquery_dataset: "omega_audit"
  pubsub_topics:
    email: "iris_notifications_hermes"
    slack: "iris_notifications_apollo"
    sms: "iris_notifications_artemis"

# ML Correlation Engine (PRO tier only)
correlation:
  enabled: false
  ml_model: "correlation_v1"
  confidence_threshold: 0.7
"""
    
    with open(config_file, 'w') as f:
        f.write(default_config)
    
    print("✅ OMEGA Guardian initialized successfully!")
    print(f"📁 Config directory: {config_dir}")
    print("🔨 Hefesto (FREE): Ready to use")
    print("🔍 Iris (PRO): Run 'omega-guardian billing' to upgrade")
    print("🧠 ML Correlation (PRO): Run 'omega-guardian billing' to upgrade")
    
    return 0

def dashboard_command(args: argparse.Namespace) -> int:
    """Open web dashboard"""
    print("📊 Opening OMEGA Guardian Dashboard...")
    
    # Check tier
    config_dir = Path.home() / ".omega-guardian"
    config_file = config_dir / "config.yaml"
    
    if not config_file.exists():
        print("❌ OMEGA Guardian not initialized. Run: omega-guardian init")
        return 1
    
    # For now, just print dashboard URL
    print("🌐 Dashboard: https://dashboard.omega-guardian.com")
    print("💡 Tip: Upgrade to PRO for full dashboard features")
    
    return 0

def billing_command(args: argparse.Namespace) -> int:
    """Manage subscription"""
    print("💳 OMEGA Guardian Billing Management")
    print()
    print("🔥 FOUNDING MEMBERS SPECIAL:")
    print("   Lock in $99/month FOREVER (Regular: $149/month)")
    print("   Limited to first 50 teams. [43 spots remaining]")
    print()
    print("🌐 Upgrade: https://omega-guardian.com/founding-members")
    print("📧 Support: support@omega-guardian.com")
    
    return 0

def main() -> int:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="omega-guardian",
        description="OMEGA Guardian - Complete DevOps Intelligence Suite",
        add_help=False
    )
    
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"OMEGA Guardian {__version__}"
    )
    
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show help message"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Hefesto subcommand
    hefesto_parser = subparsers.add_parser(
        "hefesto",
        help="Code quality analysis (FREE tier)"
    )
    hefesto_parser.add_argument(
        "hefesto_args",
        nargs="*",
        help="Hefesto command arguments"
    )
    
    # Iris subcommand
    iris_parser = subparsers.add_parser(
        "iris",
        help="Production monitoring (PRO tier)"
    )
    iris_parser.add_argument(
        "iris_args",
        nargs="*",
        help="Iris command arguments"
    )
    
    # Init subcommand
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize OMEGA Guardian"
    )
    
    # Dashboard subcommand
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Open web dashboard"
    )
    
    # Billing subcommand
    billing_parser = subparsers.add_parser(
        "billing",
        help="Manage subscription"
    )
    
    # Parse arguments
    args, unknown_args = parser.parse_known_args()
    
    # Handle help
    if args.help or not args.command:
        print_banner()
        print_help()
        return 0
    
    # Route to appropriate command
    if args.command == "hefesto":
        return run_hefesto_command(args.hefesto_args or unknown_args)
    elif args.command == "iris":
        return run_iris_command(args.iris_args or unknown_args)
    elif args.command == "init":
        return init_command(args)
    elif args.command == "dashboard":
        return dashboard_command(args)
    elif args.command == "billing":
        return billing_command(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
