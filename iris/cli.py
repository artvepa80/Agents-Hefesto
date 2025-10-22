#!/usr/bin/env python3
"""
Iris CLI - Production Monitoring Component
Part of OMEGA Guardian Complete DevOps Intelligence Suite
"""

import sys
import argparse
import asyncio
from pathlib import Path
from typing import List, Optional

# Version info
__version__ = "1.0.0"

def print_banner():
    """Print Iris banner"""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                        🔍 IRIS                                ║
║              Production Monitoring & Alerting                 ║
║                    (OMEGA Guardian Component)                 ║
╚════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_help():
    """Print Iris help"""
    help_text = """
🔍 Iris - Production Monitoring & Alerting

USAGE:
    iris <command> [options]

COMMANDS:
    🚀 start                    Start monitoring cycle
    ⏹️  stop                     Stop monitoring
    📊 status                   Show monitoring status
    🔧 config                   Manage configuration
    📈 alerts                   View recent alerts
    🧠 correlate                Enable Hefesto correlation
    ❓ help                     Show this help

EXAMPLES:
    # Start monitoring with Hefesto correlation
    iris start --correlate
    
    # View recent alerts
    iris alerts --hours 24
    
    # Check monitoring status
    iris status

REQUIREMENTS:
    💎 PRO Tier Required: iris is part of OMEGA Guardian Professional
    🔑 GCP Project: Configured with BigQuery and Pub/Sub
    📧 Notifications: Email (Hermes), Slack (Apollo), SMS (Artemis)

LEARN MORE:
    📖 Documentation: https://docs.omega-guardian.com/iris
    🌐 Website: https://omega-guardian.com
    💬 Discord: https://discord.gg/omega-guardian
"""
    print(help_text)

def start_command(args: argparse.Namespace) -> int:
    """Start Iris monitoring"""
    print("🚀 Starting Iris Production Monitoring...")
    
    try:
        from iris.core.iris_alert_manager import IrisAlertManager
        
        manager = IrisAlertManager()
        
        if args.correlate:
            print("🧠 Hefesto correlation enabled")
            manager.enable_hefesto_correlation = True
        
        print("✅ Iris monitoring started successfully!")
        print("📊 Monitoring: BigQuery queries every 15 minutes")
        print("📧 Notifications: Email via Hermes")
        print("🔍 Correlation: Hefesto findings (if enabled)")
        
        # Run monitoring cycle
        asyncio.run(manager.run_monitoring_cycle())
        
    except ImportError:
        print("❌ Error: Iris core not available. Check installation.")
        return 1
    except Exception as e:
        print(f"❌ Error starting Iris: {e}")
        return 1
    
    return 0

def status_command(args: argparse.Namespace) -> int:
    """Show Iris status"""
    print("📊 Iris Monitoring Status")
    print()
    
    try:
        from iris.core.iris_alert_manager import IrisAlertManager
        
        manager = IrisAlertManager()
        print("✅ Iris core loaded successfully")
        print("🔍 Monitoring capabilities available")
        
    except ImportError:
        print("❌ Iris core not available")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

def alerts_command(args: argparse.Namespace) -> int:
    """View recent alerts"""
    print(f"📈 Recent Alerts (last {args.hours} hours)")
    print()
    
    try:
        from iris.core.iris_alert_manager import IrisAlertManager
        
        manager = IrisAlertManager()
        alerts = manager.get_recent_alerts(hours=args.hours)
        
        if not alerts:
            print("✅ No alerts in the specified time period")
            return 0
        
        for alert in alerts:
            print(f"🚨 {alert['severity']}: {alert['message']}")
            print(f"   📅 {alert['timestamp']}")
            if alert.get('hefesto_context'):
                print(f"   🔗 Hefesto: {alert['hefesto_context']}")
            print()
        
    except ImportError:
        print("❌ Error: Iris core not available. Check installation.")
        return 1
    except Exception as e:
        print(f"❌ Error fetching alerts: {e}")
        return 1
    
    return 0

def config_command(args: argparse.Namespace) -> int:
    """Manage Iris configuration"""
    print("🔧 Iris Configuration Management")
    print()
    
    print("📁 Configuration files:")
    print("  - iris/config/bigquery_schema.sql")
    print("  - iris/config/code_findings_schema.sql")
    print("📖 Edit the config files to customize Iris settings")
    print()
    print("Key settings:")
    print("  - project_id: Your GCP project ID")
    print("  - bigquery_dataset: Dataset for audit logs")
    print("  - pubsub_topics: Notification channels")
    print("  - correlation.enabled: Enable Hefesto correlation")
    
    return 0

def main() -> int:
    """Main Iris CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="iris",
        description="Iris - Production Monitoring & Alerting",
        add_help=False
    )
    
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"Iris {__version__}"
    )
    
    parser.add_argument(
        "--help", "-h",
        action="store_true",
        help="Show help message"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start subcommand
    start_parser = subparsers.add_parser(
        "start",
        help="Start monitoring cycle"
    )
    start_parser.add_argument(
        "--correlate",
        action="store_true",
        help="Enable Hefesto correlation"
    )
    
    # Status subcommand
    subparsers.add_parser(
        "status",
        help="Show monitoring status"
    )
    
    # Alerts subcommand
    alerts_parser = subparsers.add_parser(
        "alerts",
        help="View recent alerts"
    )
    alerts_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back (default: 24)"
    )
    
    # Config subcommand
    subparsers.add_parser(
        "config",
        help="Manage configuration"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle help
    if args.help or not args.command:
        print_banner()
        print_help()
        return 0
    
    # Route to appropriate command
    if args.command == "start":
        return start_command(args)
    elif args.command == "status":
        return status_command(args)
    elif args.command == "alerts":
        return alerts_command(args)
    elif args.command == "config":
        return config_command(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
