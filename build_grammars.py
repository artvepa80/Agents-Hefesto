#!/usr/bin/env python3
"""Build TreeSitter language grammars for all supported languages."""

import os
import subprocess
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
    ("tree-sitter-java", "https://github.com/tree-sitter/tree-sitter-java"),
    ("tree-sitter-go", "https://github.com/tree-sitter/tree-sitter-go"),
    ("tree-sitter-rust", "https://github.com/tree-sitter/tree-sitter-rust"),
    ("tree-sitter-c-sharp", "https://github.com/tree-sitter/tree-sitter-c-sharp"),
]

print("Cloning grammar repositories...")
os.chdir(grammars_dir)
for name, url in repos:
    if not Path(name).exists():
        subprocess.run(["git", "clone", "--depth", "1", url], check=True)
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
        str(grammars_dir / "tree-sitter-java"),
        str(grammars_dir / "tree-sitter-go"),
        str(grammars_dir / "tree-sitter-rust"),
        str(grammars_dir / "tree-sitter-c-sharp"),
    ],
)

print("✅ Grammars built successfully: build/languages.so")
print("\n🌐 Supported languages:")
print("   - Python (.py, .pyi)")
print("   - TypeScript (.ts, .tsx)")
print("   - JavaScript (.js, .jsx, .mjs, .cjs)")
print("   - Java (.java)")
print("   - Go (.go)")
print("   - Rust (.rs)")
print("   - C# (.cs)")
