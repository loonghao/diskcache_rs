#!/usr/bin/env python3
"""
Sync version between Cargo.toml and pyproject.toml
"""

import re
import sys
from pathlib import Path


def get_cargo_version(cargo_path: Path) -> str:
    """Extract version from Cargo.toml"""
    content = cargo_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in Cargo.toml")
    return match.group(1)


def update_pyproject_version(pyproject_path: Path, version: str) -> bool:
    """Update version in pyproject.toml, return True if changed"""
    content = pyproject_path.read_text(encoding="utf-8")
    
    # Pattern to match version in [project] section
    pattern = r'(version\s*=\s*)"[^"]+"'
    new_content = re.sub(pattern, rf'\1"{version}"', content)
    
    if content != new_content:
        pyproject_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def main():
    """Main function"""
    root_dir = Path(__file__).parent.parent
    cargo_path = root_dir / "Cargo.toml"
    pyproject_path = root_dir / "pyproject.toml"
    
    if not cargo_path.exists():
        print("Error: Cargo.toml not found", file=sys.stderr)
        sys.exit(1)
    
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        cargo_version = get_cargo_version(cargo_path)
        print(f"Cargo.toml version: {cargo_version}")
        
        changed = update_pyproject_version(pyproject_path, cargo_version)
        if changed:
            print(f"Updated pyproject.toml version to: {cargo_version}")
        else:
            print("pyproject.toml version already up to date")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
