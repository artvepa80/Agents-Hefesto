"""
External Provider Base Interface for Hefesto v4.4.0.

Defines the contract for external lint/analysis tools integration.
Providers wrap tools like yamllint, shellcheck, hadolint, tflint, etc.

Copyright 2025 Narapa LLC, Miami, Florida
"""

import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hefesto.core.analysis_models import AnalysisIssue, ProviderResult
from hefesto.core.languages.specs import Language


class ExternalProvider(ABC):
    """
    Abstract base class for external analysis providers.
    
    Providers wrap external tools (yamllint, shellcheck, etc.) and
    normalize their output to Hefesto AnalysisIssue format.
    """

    name: str = "base"
    display_name: str = "Base Provider"
    supported_languages: Set[Language] = set()
    default_timeout: int = 60

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize provider with optional configuration.
        
        Args:
            config: Provider-specific configuration (timeout, rules, etc.)
        """
        self.config = config or {}
        self._version: Optional[str] = None
        self._available: Optional[bool] = None

    @abstractmethod
    def get_binary_name(self) -> str:
        """Get the name of the external binary (e.g., yamllint)."""
        pass

    @abstractmethod
    def parse_output(self, output: str, file_path: Path) -> List[AnalysisIssue]:
        """
        Parse provider output into AnalysisIssue list.
        
        Args:
            output: Raw stdout/stderr from the tool
            file_path: Path to the analyzed file
            
        Returns:
            List of normalized AnalysisIssue objects
        """
        pass

    def is_available(self) -> bool:
        """Check if the external tool is installed and accessible."""
        if self._available is None:
            binary = self.get_binary_name()
            self._available = shutil.which(binary) is not None
        return self._available

    def get_version(self) -> str:
        """Get the version of the external tool."""
        if self._version is None:
            if not self.is_available():
                self._version = "not installed"
            else:
                try:
                    result = subprocess.run(
                        [self.get_binary_name(), "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    self._version = result.stdout.strip().split("\n")[0]
                except Exception:
                    self._version = "unknown"
        return self._version

    def build_command(self, files: List[Path], cwd: Path) -> List[str]:
        """
        Build the command to execute the external tool.
        
        Override in subclasses for tool-specific arguments.
        
        Args:
            files: List of files to analyze
            cwd: Working directory for execution
            
        Returns:
            Command as list of strings
        """
        cmd = [self.get_binary_name()]
        cmd.extend([str(f) for f in files])
        return cmd

    def run_batch(
        self,
        files: List[Path],
        cwd: Path,
        config: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult:
        """
        Run the provider on a batch of files.
        
        Args:
            files: List of files to analyze
            cwd: Working directory
            config: Runtime configuration overrides
            
        Returns:
            ProviderResult with issues and metadata
        """
        start_time = time.time()
        merged_config = {**self.config, **(config or {})}
        timeout = merged_config.get("timeout", self.default_timeout)

        if not self.is_available():
            return ProviderResult(
                provider_name=self.name,
                provider_version="not installed",
                issues=[],
                duration_ms=0,
                success=False,
                errors=[f"{self.display_name} is not installed"],
            )

        try:
            cmd = self.build_command(files, cwd)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
            )

            all_issues = []
            output = result.stdout + result.stderr

            for file_path in files:
                issues = self.parse_output(output, file_path)
                all_issues.extend(issues)

            duration_ms = (time.time() - start_time) * 1000

            return ProviderResult(
                provider_name=self.name,
                provider_version=self.get_version(),
                issues=all_issues,
                duration_ms=duration_ms,
                success=True,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.time() - start_time) * 1000
            return ProviderResult(
                provider_name=self.name,
                provider_version=self.get_version(),
                issues=[],
                duration_ms=duration_ms,
                success=False,
                errors=[f"Timeout after {timeout}s"],
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ProviderResult(
                provider_name=self.name,
                provider_version=self.get_version(),
                issues=[],
                duration_ms=duration_ms,
                success=False,
                errors=[str(e)],
            )


__all__ = ["ExternalProvider"]
