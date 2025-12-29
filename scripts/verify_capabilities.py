#!/usr/bin/env python3
"""
Verify capabilities.yml against codebase reality.
"""
import sys
import yaml # PyYAML required
import importlib
import pkgutil
from pathlib import Path

def main():
    # Load manifest
    manifest_path = Path(__file__).parent.parent / "capabilities.yml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    print("="*60)
    print("CAPABILITIES PARITY CHECK")
    print("="*60)
    
    errors = []

    # 1. Validate DevOps Analyzers
    declared_devops = manifest['coverage']['devops_formats']['items']
    print(f"\nChecking DevOps Analyzers (Declared: {len(declared_devops)})...")
    
    # Discovery from code
    import hefesto.analyzers.devops as devops_pkg
    discovered_mods = {m.name for m in pkgutil.iter_modules(devops_pkg.__path__) if m.name.endswith('_analyzer')}
    
    for item in declared_devops:
        module_path = item.get('analyzer_module')
        if not module_path:
            continue
            
        # Extract submodule name (e.g. 'dockerfile_analyzer' from 'hefesto...dockerfile_analyzer')
        mod_name = module_path.split('.')[-1]
        
        # Check discovery
        if mod_name not in discovered_mods:
             errors.append(f"Module {mod_name} declared but NOT DISCOVERED in package")
             print(f"  ❌ {item['display']} -> Missing file?")
             continue

        # Check importability
        try:
            importlib.import_module(module_path)
            print(f"  ✅ {item['display']} -> Importable")
        except ImportError as e:
            errors.append(f"Module {module_path} declared but FAILED TO IMPORT: {e}")
            print(f"  ❌ {item['display']} -> Import Error")

    # 2. Validate Counts
    declared_count = manifest['coverage']['devops_formats']['declared_count']
    if len(declared_devops) != declared_count:
         errors.append(f"Manifest Inconsistency: declared_count={declared_count} but found {len(declared_devops)} items")

    if len(discovered_mods) != declared_count:
         errors.append(f"Code/Manifest Mismatch: Code has {len(discovered_mods)} analyzers, Manifest declares {declared_count}")
         print(f"   (Code found: {sorted(list(discovered_mods))})")

    # Summary
    print("-" * 60)
    if errors:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors: print(f" - {e}")
        return 1
    
    print("SUCCESS: usage of capabilities.yml aligns with codebase.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
