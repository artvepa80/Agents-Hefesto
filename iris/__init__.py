"""
Iris - Production Monitoring & Alerting Component
Part of OMEGA Guardian Complete DevOps Intelligence Suite
"""

__version__ = "1.0.0"
__description__ = "Production Monitoring & Alerting with ML Anomaly Detection"

# Core components
from . import config, core, monitors

__all__ = ["__version__", "__description__", "core", "monitors", "config"]
