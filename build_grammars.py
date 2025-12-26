#!/usr/bin/env python3
"""Build TreeSitter language grammars."""
import os
from pathlib import Path

from tree_sitter import Language

# Create build directory
build_dir = Path(__file__).parent / "build"
build_dir.mkdir(exist_ok=True)

# Clone grammar repositories
grammars_dir = build_dir / "grammars"
grammars_dir.mkdir(exist_ok=True)

repos = [
    ("tree-sitter-python", "https://github.com/tree-sitter/tree-sitter-python"),
    ("tree-sitter-typescript", "https://github.com/tree-sitter/tree-sitter-typescript"),
    ("tree-sitter-javascript", "https://github.com/tree-sitter/tree-sitter-javascript"),
]

print("Cloning grammar repositories...")
os.chdir(grammars_dir)
for name, url in repos:
    if not Path(name).exists():
        os.system(f"git clone {url}")
        print(f"✅ Cloned {name}")
    else:
        print(f"⏭️  {name} already exists")

# Build language library
os.chdir(Path(__file__).parent)
print("\nBuilding language library...")

Language.build_library(
    str(build_dir / "languages.so"),
    [
        str(grammars_dir / "tree-sitter-python"),
        str(grammars_dir / "tree-sitter-typescript" / "typescript"),
        str(grammars_dir / "tree-sitter-typescript" / "tsx"),
        str(grammars_dir / "tree-sitter-javascript"),
    ],
)

print("✅ Grammars built successfully: build/languages.so")
