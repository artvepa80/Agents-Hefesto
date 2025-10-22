"""
OMEGA Guardian - Complete DevOps Intelligence Suite
"""

__version__ = "1.0.0"
__author__ = "Narapa LLC"
__email__ = "support@omega-guardian.com"
__description__ = "Complete DevOps Intelligence Suite - Hefesto (Code Quality) + Iris (Production Monitoring) + ML Correlation"

# Core components
from . import cli
from . import config
from . import correlation

__all__ = [
    "__version__",
    "__author__", 
    "__email__",
    "__description__",
    "cli",
    "config", 
    "correlation"
]
