"""Choose one language when a path matches more than one format.

The order is the precedence table in
``docs/design/devops-analyzers-wiring.md``. Path globs still decide which
files a directory walk opens; this module only refines that guess.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from hefesto.core.languages.specs import Language

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore


_SERVERLESS_NAMES = frozenset({"serverless.yml", "serverless.yaml"})
_HELM_VALUE_NAMES = frozenset({"values.yaml", "values.yml"})
_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


def _is_arm(data: dict) -> bool:
    schema = data.get("$schema")
    if not isinstance(schema, str):
        return False
    return "deploymenttemplate.json" in schema.lower()


def _resource_type_is_aws(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    resource_type = value.get("Type")
    return isinstance(resource_type, str) and resource_type.startswith("AWS::")


def _is_cloudformation(data: dict) -> bool:
    if "AWSTemplateFormatVersion" in data:
        return True
    resources = data.get("Resources")
    if isinstance(resources, dict) and any(
        _resource_type_is_aws(value) for value in resources.values()
    ):
        return True
    return False


def _is_serverless(data: dict) -> bool:
    return "service" in data or "provider" in data


def _is_helm_values_path(file_path: Path) -> bool:
    name = file_path.name.lower()
    if name not in _HELM_VALUE_NAMES and not (
        name.startswith("values-") and name.endswith((".yaml", ".yml"))
    ):
        return False
    return (file_path.parent / "Chart.yaml").is_file()


def _yaml_documents(content: str) -> Optional[List[Any]]:
    if yaml is None:
        return None
    try:
        return [doc for doc in yaml.safe_load_all(content) if doc is not None]
    except Exception:
        return None


def _single_mapping(documents: Optional[List[Any]]) -> Optional[dict]:
    if documents is None or len(documents) != 1 or not isinstance(documents[0], dict):
        return None
    return documents[0]


def _refine_json(guessed: Language, content: Optional[str]) -> Language:
    if content is None:
        return Language.JSON if guessed != Language.ARM else guessed
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return Language.JSON
    if isinstance(data, dict):
        if _is_arm(data):
            return Language.ARM
        if _is_cloudformation(data):
            return Language.CLOUDFORMATION
    return Language.JSON


def _refine_yaml(guessed: Language, file_path: Path, content: Optional[str]) -> Language:
    name = file_path.name.lower()
    documents = _yaml_documents(content) if content is not None else None
    mapping = _single_mapping(documents) if content is not None else None
    if mapping is not None and _is_cloudformation(mapping):
        return Language.CLOUDFORMATION
    if name in _SERVERLESS_NAMES and mapping is not None and _is_serverless(mapping):
        return Language.SERVERLESS
    if _is_helm_values_path(file_path):
        # A values file that is not valid YAML stays YAML so the syntax
        # check still runs. Helm's values file is plain YAML.
        if content is not None and documents is None:
            return Language.YAML
        return Language.HELM
    if file_path.suffix.lower() in _YAML_SUFFIXES or guessed in {
        Language.YAML,
        Language.HELM,
        Language.SERVERLESS,
        Language.CLOUDFORMATION,
    }:
        return Language.YAML
    return guessed


def refine_language(guessed: Language, file_path: Path, content: Optional[str]) -> Language:
    """Apply the precedence table to a path-based guess."""
    name = file_path.name.lower()
    suffix = file_path.suffix.lower()

    if name.endswith(".tf.json") or guessed == Language.TERRAFORM:
        return Language.TERRAFORM

    if suffix == ".json" or guessed in {Language.JSON, Language.ARM}:
        if suffix != ".yaml" and suffix != ".yml":
            return _refine_json(guessed, content)

    if (
        suffix in _YAML_SUFFIXES
        or name in _SERVERLESS_NAMES
        or guessed in {Language.YAML, Language.HELM, Language.SERVERLESS}
        or (guessed == Language.CLOUDFORMATION and suffix in _YAML_SUFFIXES)
    ):
        return _refine_yaml(guessed, file_path, content)

    if guessed == Language.HELM and not _is_helm_values_path(file_path):
        return Language.YAML
    return guessed
