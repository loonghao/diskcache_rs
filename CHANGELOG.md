## v0.2.4 (2025-07-21)

### Fix

- **deps**: update rust crate serde_json to v1.0.141

## v0.2.3 (2025-07-13)

### Fix

- configure proper permissions for release workflows
- resolve release changelog generation issues

## v0.2.2 (2025-07-13)

### Fix

- add comprehensive GitHub Actions permissions for version management
- improve commitizen workflow with debug and proper permissions

## v0.2.1 (2025-07-13)

### Fix

- resolve merge conflicts and correct version field configurations
- correct ruff target-version configuration

## v0.2.0 (2025-07-13)

### Feat

- replace release-plz with commitizen for better multi-language support
- implement release-plz for automated version management
- add release-please for automated version management
- make ABI3 support optional and enhance README with PyPI badges
- modernize development setup and add ABI3 support

### Fix

- resolve ruff linting issues
- remove unsupported --compatibility abi3 flag from GitHub Actions

## v0.1.0 (2025-07-13)

### Feat

- implement ultra-fast storage backends with superior performance
- replace Python pickle with high-performance Rust implementation
- implement high-performance pickle cache with expiration support
- add missing Cache methods for API compatibility
- add Docker network environment testing and fix unit tests
- add missing exists() and keys() methods to Python Cache wrapper
- add CI-friendly benchmark tests and fix gitignore
- implement complete diskcache API compatibility and official benchmarks
- implement drop-in replacement API for diskcache compatibility
- upgrade CI/CD to use PyPI Trusted Publishing and comprehensive platform support
- enhance CI/CD pipeline with comprehensive testing and PyPI publishing
- initial commit with diskcache_rs implementation

### Fix

- make CI and build workflows reusable for release workflow
- resolve final ruff CI linting issues
- resolve Windows timing precision issues across all performance tests
- resolve Windows timing precision issue in pickle performance tests
- resolve CI syntax error and code quality issues
- resolve Windows pytest and CI issues
- resolve Python 3.8 compatibility and ruff configuration issues
- resolve all code quality issues and formatting problems
- resolve CI build failures by adding maturin installation step
- improve __contains__ method implementation for better compatibility
- resolve CI test failures and clippy format issues
- resolve all clippy warnings and test import issues
- resolve Alpine Linux ARMv7 py3-venv package availability issue
- resolve bincode import issues in Rust compilation
- resolve Alpine Linux externally-managed-environment errors in CI
- improve CI benchmark testing and add comprehensive test suite
- resolve module naming conflicts and API compatibility issues
- resolve macOS build issues and add comprehensive benchmark tests
- resolve circular import issue in Python wrapper
- resolve cross-platform build issues and modernize CI/CD
- correct uv syntax and dependency versions for Python 3.8+ compatibility

### Refactor

- adopt pydantic-core style dependency management and fix Linux CI issues
- remove diskcache as runtime dependency, make it optional for benchmarks
- restructure tests to use pytest and split CI workflows
