"""
Setup configuration for Hefesto package.

Copyright © 2025 Narapa LLC, Miami, Florida
"""

from setuptools import setup, find_packages
import os

# Read version
with open(os.path.join('hefesto', '__version__.py')) as f:
    exec(f.read())

# Read README
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Base dependencies (Phase 0 - Free)
install_requires = [
    'fastapi>=0.104.0,<1.0.0',
    'uvicorn[standard]>=0.24.0,<1.0.0',
    'pydantic>=2.5.0,<3.0.0',
    'click>=8.0.0,<9.0.0',
    'google-cloud-bigquery>=3.10.0,<4.0.0',
    'google-generativeai>=0.3.0',
    'httpx>=0.25.0,<1.0.0',
    'python-dateutil>=2.8.2,<3.0.0',
]

# Pro dependencies (Phase 1 - Paid)
extras_require = {
    'pro': [
        'sentence-transformers>=2.2.2,<3.0.0',
        'torch>=2.0.1,<3.0.0',
        'numpy>=1.24.0,<2.0.0',
    ],
    'dev': [
        'pytest>=7.4.0,<8.0.0',
        'pytest-cov>=4.1.0,<5.0.0',
        'pytest-asyncio>=0.21.0,<1.0.0',
        'black>=23.0.0',
        'isort>=5.12.0',
        'mypy>=1.7.0',
    ],
    'all': [],  # Will be populated below
}

# Combine all extras
extras_require['all'] = list(set(
    extras_require['pro'] +
    extras_require['dev']
))

setup(
    name='hefesto',
    version=__version__,
    author='Narapa LLC',
    author_email='sales@narapa.com',
    description='AI-Powered Code Quality Guardian with Gemini integration',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/artvepa80/Agents-Hefesto',
    project_urls={
        'Documentation': 'https://github.com/artvepa80/Agents-Hefesto#readme',
        'Source': 'https://github.com/artvepa80/Agents-Hefesto',
        'Issues': 'https://github.com/artvepa80/Agents-Hefesto/issues',
        'Pro License': 'https://buy.stripe.com/hefesto-pro',
    },
    packages=find_packages(exclude=['tests', 'tests.*', 'examples', 'docs']),
    python_requires='>=3.10',
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'hefesto=hefesto.cli.main:cli',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Code Generators',
        'License :: OSI Approved :: MIT License',
        'License :: Other/Proprietary License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
        'Typing :: Typed',
    ],
    keywords='ai code-quality refactoring security gemini llm devtools',
    license='Dual License (MIT + Commercial)',
    include_package_data=True,
    zip_safe=False,
)

