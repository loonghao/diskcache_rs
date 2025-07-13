# justfile for diskcache_rs development
# Run `just --list` to see all available commands

# Set shell for Windows compatibility
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set shell := ["sh", "-c"]

# Default recipe to display help
default:
    @just --list

# Install dependencies
install:
    @echo "📦 Installing dependencies..."
    uv sync --group dev

# Build the extension module
build:
    @echo "🔧 Building extension module..."
    uvx maturin develop

# Build with release optimizations
build-release:
    @echo "🚀 Building release version..."
    uvx maturin develop --release

# Run tests
test:
    @echo "🧪 Running tests..."
    uv run python -m pytest tests/ -v

# Run tests with coverage
test-cov:
    @echo "🧪 Running tests with coverage..."
    uv run python -m pytest tests/ -v --cov=diskcache_rs --cov-report=html

# Generate Python type stub files using pyo3-stubgen
stubs:
    @echo "📝 Generating type stubs with pyo3-stubgen..."
    uvx maturin develop
    uv run pyo3-stubgen diskcache_rs._diskcache_rs python/diskcache_rs/
    @echo "✅ Type stubs generated successfully"

# Format code
format:
    @echo "🎨 Formatting Rust code..."
    cargo fmt --all
    @echo "🎨 Formatting Python code..."
    uv run ruff format .

# Run linting
lint:
    @echo "🔍 Linting Rust code..."
    cargo clippy -- -D warnings
    @echo "🔍 Linting Python code..."
    uv run ruff check .

# Fix linting issues automatically
fix:
    @echo "🔧 Fixing linting issues..."
    cargo clippy --fix --allow-dirty --allow-staged
    uv run ruff check --fix .

# Run all checks (format, lint, test)
check: format lint test
    @echo "✅ All checks passed!"

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    cargo clean
    @echo "Cleaning Python artifacts..."
    python -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) for p in ['target', 'dist', 'python/diskcache_rs/__pycache__']]"

# Setup development environment
dev: install build stubs
    @echo "🚀 Development environment ready!"
    @echo "💡 Try: just test"

# Build release wheels for all platforms
release:
    @echo "📦 Building release wheels..."
    uvx maturin build --release

# Build ABI3 wheels (compatible with Python 3.8+)
release-abi3:
    @echo "📦 Building ABI3 wheels..."
    uvx maturin build --release --features abi3

# Build and publish to PyPI (requires authentication)
publish: release
    @echo "🚀 Publishing to PyPI..."
    uvx maturin publish

# Run benchmarks
bench:
    @echo "⚡ Running benchmarks..."
    uv run python -m pytest tests/ -v -k benchmark

# Update dependencies
update:
    @echo "⬆️  Updating dependencies..."
    uv sync --upgrade

# Show project info
info:
    @echo "📊 Project Information:"
    @echo "  Rust version: $(rustc --version)"
    @echo "  Python version: $(python --version)"
    @echo "  UV version: $(uv --version)"
    @echo "  Maturin version: $(uvx maturin --version)"

# Run security audit
audit:
    @echo "🔒 Running security audit..."
    cargo audit

# Run specific test file
test-file FILE:
    @echo "🧪 Running tests in {{FILE}}..."
    uv run python -m pytest {{FILE}} -v

# Sync version between Cargo.toml and pyproject.toml
sync-version:
    @echo "🔄 Syncing version between Cargo.toml and pyproject.toml..."
    python scripts/sync_version.py

# Commitizen commands
commit:
    @echo "📝 Creating conventional commit..."
    uvx --from commitizen cz commit

bump:
    @echo "🚀 Bumping version with commitizen..."
    uvx --from commitizen cz bump

changelog:
    @echo "📋 Generating changelog..."
    uvx --from commitizen cz changelog

# Check version consistency
check-version:
    @echo "🔍 Checking version consistency..."
    uvx --from commitizen cz check --rev-range HEAD~1..HEAD

# Verify stub files are included in wheel
verify-stubs:
    @echo "🔍 Verifying stub files in wheel..."
    uvx maturin build --release
    python -m zipfile -l target/wheels/*.whl | grep "\.pyi"
    @echo "✅ Stub files verified in wheel package"