"""
Language specifications for Hefesto v4.4.0 - DevOps Enterprise Support.

Defines LanguageSpec dataclass for all supported languages including
Ola 1 DevOps languages: YAML, Terraform/HCL, Shell, Dockerfile, SQL.

Copyright 2025 Narapa LLC, Miami, Florida
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional


class Language(Enum):
    """Supported programming languages."""

    # Core languages (existing)
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CSHARP = "csharp"

    # Ola 1 DevOps languages (v4.4.0)
    YAML = "yaml"
    TERRAFORM = "terraform"
    SHELL = "shell"
    DOCKERFILE = "dockerfile"
    SQL = "sql"

    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderRef:
    """Reference to an external provider for a language."""

    name: str
    mode: Literal["external", "internal"] = "external"
    priority: int = 100
    enabled_by_default: bool = True


@dataclass(frozen=True)
class LanguageSpec:
    """
    Complete specification for a supported language.

    Includes detection patterns, parsers, internal analyzers (fallback),
    and external providers.
    """

    language: Language
    display_name: str
    file_globs: List[str]
    detect_by_filename: bool = False
    filename_patterns: List[str] = field(default_factory=list)
    detect_by_shebang: bool = False
    shebang_patterns: List[str] = field(default_factory=list)
    parser_type: Optional[str] = None
    internal_analyzers: List[str] = field(default_factory=list)
    providers: List[ProviderRef] = field(default_factory=list)
    tier_required: Literal["FREE", "PRO", "OMEGA"] = "FREE"


# Language specifications registry
LANGUAGE_SPECS: List[LanguageSpec] = [
    # Core languages (existing)
    LanguageSpec(
        language=Language.PYTHON,
        display_name="Python",
        file_globs=["*.py", "*.pyi"],
        parser_type="python_ast",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.TYPESCRIPT,
        display_name="TypeScript",
        file_globs=["*.ts", "*.tsx"],
        parser_type="treesitter:typescript",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.JAVASCRIPT,
        display_name="JavaScript",
        file_globs=["*.js", "*.jsx", "*.mjs", "*.cjs"],
        parser_type="treesitter:javascript",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.JAVA,
        display_name="Java",
        file_globs=["*.java"],
        parser_type="treesitter:java",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.GO,
        display_name="Go",
        file_globs=["*.go"],
        parser_type="treesitter:go",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.RUST,
        display_name="Rust",
        file_globs=["*.rs"],
        parser_type="treesitter:rust",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    LanguageSpec(
        language=Language.CSHARP,
        display_name="C#",
        file_globs=["*.cs"],
        parser_type="treesitter:c_sharp",
        internal_analyzers=["code_smells", "complexity", "security", "best_practices"],
    ),
    # Ola 1 DevOps languages (v4.4.0)
    LanguageSpec(
        language=Language.YAML,
        display_name="YAML",
        file_globs=["*.yml", "*.yaml"],
        parser_type="yaml",
        internal_analyzers=["yaml_analyzer"],
        providers=[
            ProviderRef(name="yamllint", mode="external", priority=100),
        ],
    ),
    LanguageSpec(
        language=Language.TERRAFORM,
        display_name="Terraform/HCL",
        file_globs=["*.tf", "*.tfvars", "*.tf.json"],
        parser_type="hcl",
        internal_analyzers=["terraform_analyzer"],
        providers=[
            ProviderRef(name="tflint", mode="external", priority=100),
            ProviderRef(name="tfsec", mode="external", priority=90),
            ProviderRef(name="checkov", mode="external", priority=80, enabled_by_default=False),
        ],
        tier_required="FREE",
    ),
    LanguageSpec(
        language=Language.SHELL,
        display_name="Shell/Bash",
        file_globs=["*.sh", "*.bash"],
        detect_by_shebang=True,
        shebang_patterns=[
            "#!/bin/bash",
            "#!/usr/bin/env bash",
            "#!/bin/sh",
            "#!/usr/bin/env sh",
        ],
        parser_type="shell",
        internal_analyzers=["shell_analyzer"],
        providers=[
            ProviderRef(name="shellcheck", mode="external", priority=100),
        ],
    ),
    LanguageSpec(
        language=Language.DOCKERFILE,
        display_name="Dockerfile",
        file_globs=["Dockerfile", "Dockerfile.*", "*.Dockerfile"],
        detect_by_filename=True,
        filename_patterns=["Dockerfile", "Dockerfile.*"],
        parser_type="dockerfile",
        internal_analyzers=["dockerfile_analyzer"],
        providers=[
            ProviderRef(name="hadolint", mode="external", priority=100),
        ],
    ),
    LanguageSpec(
        language=Language.SQL,
        display_name="SQL",
        file_globs=["*.sql"],
        parser_type="sql",
        internal_analyzers=["sql_analyzer"],
        providers=[
            ProviderRef(name="sqlfluff", mode="external", priority=100),
        ],
    ),
]


__all__ = ["Language", "LanguageSpec", "ProviderRef", "LANGUAGE_SPECS"]
