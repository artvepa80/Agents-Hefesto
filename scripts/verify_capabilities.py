#!/usr/bin/env python3
"""
Verify capabilities.yml against codebase reality.
"""
import sys
import yaml # PyYAML required
import importlib
import pkgutil
from pathlib import Path

def validate_devops_analyzers(manifest):
    """Validate DevOps analyzers existence and importability."""
    errors = []
    declared_devops = manifest['coverage']['devops_formats']['items']
    declared_count = manifest['coverage']['devops_formats']['declared_count']
    
    print(f"\n1. Checking DevOps Analyzers (Declared: {declared_count})...")
    
    # Discovery from code
    import hefesto.analyzers.devops as devops_pkg
    discovered_mods = {m.name for m in pkgutil.iter_modules(devops_pkg.__path__) if m.name.endswith('_analyzer')}
    
    # Check consistency count
    if len(declared_devops) != declared_count:
         errors.append(f"Manifest Inconsistency: declared_count={declared_count} but found {len(declared_devops)} items")

    if len(discovered_mods) != declared_count:
         errors.append(f"Code/Manifest Mismatch: Code has {len(discovered_mods)} analyzers, Manifest declares {declared_count}")
         print(f"   (Code found: {sorted(list(discovered_mods))})")

    for item in declared_devops:
        module_path = item.get('analyzer_module')
        if not module_path:
            continue
            
        mod_name = module_path.split('.')[-1]
        
        if mod_name not in discovered_mods:
             errors.append(f"Module {mod_name} declared but NOT DISCOVERED in package")
             print(f"  ❌ {item['display']} -> Missing file?")
             continue

        try:
            importlib.import_module(module_path)
            print(f"  ✅ {item['display']} -> Importable")
        except ImportError as e:
            errors.append(f"Module {module_path} declared but FAILED TO IMPORT: {e}")
            print(f"  ❌ {item['display']} -> Import Error")
            
    return errors

def validate_code_languages(manifest):
    """Validate Code Languages consistency."""
    errors = []
    code_decl = manifest['coverage']['code_languages']
    items_count = len(code_decl['items'])
    declared_count = code_decl['declared_count']
    
    print(f"\n2. Checking Code Languages (Declared: {declared_count})...")
    
    if items_count != declared_count:
        errors.append(f"Code Languages Inconsistency: declared_count={declared_count} but found {items_count} items")
        print(f"  ❌ Count Mismatch")
    else:
        print(f"  ✅ Internal count consistent")
        
    return errors

def validate_totals(manifest):
    """Validate calculated totals."""
    errors = []
    print(f"\n3. Checking Totals...")
    
    code_count = manifest['coverage']['code_languages']['declared_count']
    devops_count = manifest['coverage']['devops_formats']['declared_count']
    total_declared = manifest['coverage']['totals']['declared_total_formats']
    
    computed_total = code_count + devops_count
    
    if total_declared != computed_total:
        errors.append(f"Total Formats Mismatch: Declared {total_declared} != Computed {computed_total} ({code_count} + {devops_count})")
        print(f"  ❌ Total Mismatch: {total_declared} vs {computed_total}")
    else:
        print(f"  ✅ Total consistent: {total_declared} formats")
        
    return errors

def main():
    manifest_path = Path(__file__).parent.parent / "capabilities.yml"
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    print("="*60)
    print(f"CAPABILITIES PARITY CHECK (Schema v{manifest.get('schema_version', '?')})")
    print("="*60)
    
    all_errors = []
    
    all_errors.extend(validate_devops_analyzers(manifest))
    all_errors.extend(validate_code_languages(manifest))
    all_errors.extend(validate_totals(manifest))

    # Summary
    print("-" * 60)
    if all_errors:
        print(f"FAILED with {len(all_errors)} errors:")
        for e in all_errors: print(f" - {e}")
        return 1
    
    print("SUCCESS: capabilities.yml matches codebase reality.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
