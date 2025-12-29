#!/usr/bin/env python3
"""
Verify capabilities.yml against codebase reality.
"""
import sys
import yaml # PyYAML required
import importlib
import pkgutil
from pathlib import Path

def validate_schema(manifest):
    """Validate schema version and required fields."""
    errors = []
    
    # Check version
    version = manifest.get('schema_version')
    if version != 1:
        errors.append(f"Unsupported schema_version: {version} (expected 1)")
        return errors # Critical failure, return early
        
    # Check required paths
    required_keys = [
        ['coverage', 'devops_formats', 'items'],
        ['coverage', 'devops_formats', 'declared_count'],
        ['coverage', 'code_languages', 'items'],
        ['coverage', 'totals', 'declared_total_formats']
    ]
    
    for path in required_keys:
        current = manifest
        missing = False
        for key in path:
            if not isinstance(current, dict) or key not in current:
                errors.append(f"Missing required manifest key: {'.'.join(path)}")
                missing = True
                break
            current = current[key]
            
    return errors

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
         
         # Diff reporting
         declared_names = {item.get('analyzer_module', '').split('.')[-1] for item in declared_devops if item.get('analyzer_module')}
         missing_in_manifest = discovered_mods - declared_names
         missing_in_code = declared_names - discovered_mods
         
         if missing_in_manifest:
             print(f"   ⚠️ Found in code but MISSING in manifest: {missing_in_manifest}")
         if missing_in_code:
             print(f"   ⚠️ Declared in manifest but MISSING in code: {missing_in_code}")

    for item in declared_devops:
        display = item.get('display', 'Unknown')
        
        # Mandatory fields
        if not item.get('id'):
            errors.append(f"Item '{display}' missing 'id'")
        
        module_path = item.get('analyzer_module')
        if not module_path:
            errors.append(f"Item '{display}' missing required 'analyzer_module'")
            print(f"  ❌ {display} -> Missing definition")
            continue
            
        mod_name = module_path.split('.')[-1]
        
        if mod_name not in discovered_mods:
             errors.append(f"Module {mod_name} declared but NOT DISCOVERED in package")
             print(f"  ❌ {display} -> Missing file?")
             continue

        try:
            importlib.import_module(module_path)
            print(f"  ✅ {display} -> Importable")
        except ImportError as e:
            errors.append(f"Module {module_path} declared but FAILED TO IMPORT: {e}")
            print(f"  ❌ {display} -> Import Error")
            
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
    
    # 0. Schema Validation
    schema_errors = validate_schema(manifest)
    if schema_errors:
        print("CRITICAL SCHEMA ERRORS:")
        for e in schema_errors: print(f" - {e}")
        return 1
    
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
