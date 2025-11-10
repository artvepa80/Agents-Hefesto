#!/usr/bin/env python3
"""
OMEGA Guardian - Complete DevOps Intelligence Suite
Setup script for Hefesto + Iris integration
"""

import os

from setuptools import find_packages, setup


# Read version from version file
def get_version():
    """Read version safely without using exec()."""
    version_file = os.path.join(os.path.dirname(__file__), "omega", "__version__.py")
    if os.path.exists(version_file):
        import re

        with open(version_file, "r") as f:
            content = f.read()
        # Safely extract __version__ using regex instead of exec()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    return "1.0.0"


# Read long description from README
def get_long_description():
    readme_file = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_file):
        with open(readme_file, "r", encoding="utf-8") as f:
            return f.read()
    return "OMEGA Guardian - Complete DevOps Intelligence Suite"


# Read requirements
def get_requirements():
    requirements_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if os.path.exists(requirements_file):
        with open(requirements_file, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []


setup(
    name="hefesto-ai",
    version=get_version(),
    author="Narapa LLC",
    author_email="support@narapa.app",
    description="Hefesto AI - Intelligent Code Quality Analysis and Technical Debt Detection",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/artvepa80/Agents-Hefesto",
    project_urls={
        "Bug Reports": "https://github.com/artvepa80/Agents-Hefesto/issues",
        "Source": "https://github.com/artvepa80/Agents-Hefesto",
        "Documentation": "https://docs.omega-guardian.com",
        "Website": "https://omega-guardian.com",
    },
    packages=find_packages(include=["hefesto", "hefesto.*", "iris", "iris.*", "omega", "omega.*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Environment :: Web Environment",
    ],
    python_requires=">=3.8",
    install_requires=get_requirements(),
    extras_require={
        "cloud": [
            "google-cloud-bigquery>=3.11.0",
            "google-cloud-pubsub>=2.18.0",
            "google-cloud-logging>=3.5.0",
            "google-cloud-run>=0.9.0",
            "google-cloud-aiplatform>=1.35.0",
            "stripe>=6.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
            "sphinx>=7.0.0",
            "sphinx-rtd-theme>=1.3.0",
        ],
        "all": [
            "google-cloud-bigquery>=3.11.0",
            "google-cloud-pubsub>=2.18.0",
            "google-cloud-logging>=3.5.0",
            "google-cloud-run>=0.9.0",
            "google-cloud-aiplatform>=1.35.0",
            "stripe>=6.0.0",
            "scikit-learn>=1.3.0",
            "pandas>=2.0.0",
            "numpy>=1.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "hefesto=hefesto.cli.main:cli",
            "iris=iris.cli:main",
            "omega-guardian=omega.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "hefesto": ["config/*.yaml", "rules/*.yaml"],
        "iris": ["config/*.yaml", "rules/*.yaml"],
        "omega": ["config/*.yaml", "templates/*.yaml"],
    },
    zip_safe=False,
    keywords=[
        "code-quality",
        "static-analysis",
        "technical-debt",
        "ml",
        "ai",
        "hefesto",
        "code-analysis",
        "security-scanning",
        "duplicate-detection",
        "ci-cd",
        "python",
        "code-review",
        "quality-assurance",
    ],
    platforms=["any"],
    license="MIT",
)
