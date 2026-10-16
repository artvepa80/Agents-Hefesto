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

    # Legacy languages (v4.12.0)
    COBOL = "cobol"

    # Ola 2 / cloud formats dispatched by the engine (v4.20.0)
    POWERSHELL = "powershell"
    JSON = "json"
    TOML = "toml"
    MAKEFILE = "makefile"
    GROOVY = "groovy"
    CLOUDFORMATION = "cloudformation"
    ARM = "arm"
    HELM = "helm"
    SERVERLESS = "serverless"

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
    # Legacy languages (v4.12.0)
    LanguageSpec(
        language=Language.COBOL,
        display_name="COBOL",
        file_globs=[
            "*.cbl",
            "*.cob",
            "*.cobol",
            "*.cpy",
            "*.pco",
            "*.CBL",
            "*.COB",
            "*.COBOL",
            "*.CPY",
            "*.PCO",
        ],
        parser_type="cobol_structural",
        internal_analyzers=["cobol_governance"],
        providers=[],
        tier_required="FREE",
    ),
    # Formats that already had analyzers. Globs discover files; content
    # classification in content_classify.py breaks suffix ties.
    LanguageSpec(
        language=Language.POWERSHELL,
        display_name="PowerShell",
        file_globs=["*.ps1", "*.psm1", "*.psd1"],
        parser_type="powershell",
        internal_analyzers=["powershell_analyzer"],
    ),
    LanguageSpec(
        language=Language.JSON,
        display_name="JSON",
        file_globs=["*.json"],
        parser_type="json",
        internal_analyzers=["json_analyzer"],
    ),
    LanguageSpec(
        language=Language.TOML,
        display_name="TOML",
        file_globs=["*.toml"],
        parser_type="toml",
        internal_analyzers=["toml_analyzer"],
    ),
    LanguageSpec(
        language=Language.MAKEFILE,
        display_name="Makefile",
        file_globs=["Makefile", "makefile", "GNUmakefile", "*.mk"],
        parser_type="makefile",
        internal_analyzers=["makefile_analyzer"],
    ),
    LanguageSpec(
        language=Language.GROOVY,
        display_name="Groovy/Jenkins",
        file_globs=["Jenkinsfile", "*.groovy"],
        parser_type="groovy",
        internal_analyzers=["groovy_jenkins_analyzer"],
    ),
    LanguageSpec(
        language=Language.CLOUDFORMATION,
        display_name="CloudFormation",
        file_globs=["*.cfn.json", "*.cfn.yaml", "*.cfn.yml"],
        parser_type="cloudformation",
        internal_analyzers=["cloudformation_analyzer"],
    ),
    LanguageSpec(
        language=Language.ARM,
        display_name="ARM",
        file_globs=["*.json"],
        parser_type="arm",
        internal_analyzers=["arm_analyzer"],
    ),
    LanguageSpec(
        language=Language.HELM,
        display_name="Helm",
        file_globs=["values.yaml", "values.yml", "values-*.yaml", "values-*.yml"],
        parser_type="helm",
        internal_analyzers=["helm_analyzer"],
    ),
    LanguageSpec(
        language=Language.SERVERLESS,
        display_name="Serverless",
        file_globs=["serverless.yml", "serverless.yaml"],
        parser_type="serverless",
        internal_analyzers=["serverless_analyzer"],
    ),
]


__all__ = ["Language", "LanguageSpec", "ProviderRef", "LANGUAGE_SPECS"]
