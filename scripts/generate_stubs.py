#!/usr/bin/env python3
"""
Script to generate Python type stub files (.pyi) for diskcache_rs.

This script uses pyo3-stub-gen to automatically generate type hints
for the Rust-implemented modules and creates comprehensive stubs
for the entire package.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Run a command and return its output."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=check, capture_output=True, text=True, cwd=cwd
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running command: {cmd}")
            print(f"Error output: {e.stderr}")
            sys.exit(1)
        return "", e.stderr, e.returncode


def main():
    """Generate type stub files for diskcache_rs."""

    # Get project root directory
    project_root = Path(__file__).parent.parent
    python_dir = project_root / "python" / "diskcache_rs"

    print("🔧 Building the extension module...")
    stdout, stderr, code = run_command("uvx maturin develop", cwd=project_root)
    if code != 0:
        print(f"❌ Failed to build extension: {stderr}")
        return False

    print("📝 Generating type stubs for Rust module...")

    # Try pyo3-stub-gen first
    stdout, stderr, code = run_command(
        "uv run pyo3-stub-gen --module diskcache_rs._diskcache_rs",
        cwd=project_root,
        check=False,
    )

    if code == 0:
        print("✅ Generated _diskcache_rs.pyi with pyo3-stub-gen")
    else:
        print("⚠️  pyo3-stub-gen failed, trying mypy stubgen...")
        stdout, stderr, code = run_command(
            f"uv run mypy stubgen diskcache_rs._diskcache_rs -o {python_dir.parent}",
            cwd=project_root,
            check=False,
        )
        if code == 0:
            print("✅ Generated stubs with mypy")
        else:
            print("❌ Failed to generate stubs for Rust module")
            print(f"Error: {stderr}")
            return False

    # Generate stubs for Python modules
    print("📝 Generating type stubs for Python modules...")

    python_modules = [
        "cache.py",
        "fast_cache.py",
        "pickle_cache.py",
        "core.py",
        "rust_pickle.py",
    ]

    for module in python_modules:
        module_path = python_dir / module
        if module_path.exists():
            stub_path = python_dir / f"{module.replace('.py', '.pyi')}"
            try:
                run_command(
                    f"uvx mypy stubgen {module_path} -o {python_dir}", cwd=project_root
                )
                print(f"✅ Generated {stub_path.name}")
            except:
                print(f"⚠️  Failed to generate stub for {module}")

    # Generate main __init__.pyi
    print("📝 Generating main __init__.pyi...")
    init_pyi_content = '''"""
Type stubs for diskcache_rs package.

This module provides type hints for the diskcache_rs Python package,
which is a high-performance disk cache implementation in Rust with Python bindings.
"""

from typing import Any, Dict, List, Optional, Union, Iterator, Tuple, Callable
from pathlib import Path

# Re-export main classes
from .cache import Cache, FanoutCache
from .fast_cache import FastCache, FastFanoutCache  
from .pickle_cache import PickleCache, cache_object, clear_cache, get_cached_object

# Import Rust functions if available
try:
    from ._diskcache_rs import rust_pickle_dumps, rust_pickle_loads
except ImportError:
    rust_pickle_dumps: Optional[Callable[[Any], bytes]] = None
    rust_pickle_loads: Optional[Callable[[bytes], Any]] = None

# Version information
__version__: str

# Backward compatibility
DiskCache = Cache

# All exported symbols
__all__: List[str]
'''

    init_pyi_path = python_dir / "__init__.pyi"
    with open(init_pyi_path, "w", encoding="utf-8") as f:
        f.write(init_pyi_content)

    print(f"✅ Generated {init_pyi_path.name}")

    print("\n🎉 Type stub generation completed!")
    print(f"📁 Stubs generated in: {python_dir}")

    # List generated files
    pyi_files = list(python_dir.glob("*.pyi"))
    if pyi_files:
        print("\n📋 Generated stub files:")
        for pyi_file in sorted(pyi_files):
            print(f"  - {pyi_file.name}")

    print("\n💡 To use type hints in your IDE:")
    print("   1. Make sure your IDE supports .pyi files")
    print("   2. Install the package in development mode: uvx maturin develop")
    print("   3. Your IDE should automatically pick up the type hints")


if __name__ == "__main__":
    main()
