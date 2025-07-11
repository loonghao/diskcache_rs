# Release Guide

This document describes how to release diskcache_rs to PyPI.

## Prerequisites

1. **PyPI Account**: You need a PyPI account with permissions to publish to the `diskcache_rs` package.

2. **Trusted Publishing Setup**: Configure PyPI Trusted Publishing (recommended, no API tokens needed)

## Setting up PyPI Trusted Publishing (Recommended)

PyPI now supports Trusted Publishing, which is more secure than API tokens:

1. **Create PyPI Project** (if not exists):
   - Go to [PyPI](https://pypi.org/)
   - Create a new project named `diskcache_rs`

2. **Configure Trusted Publishing**:
   - Go to your project's PyPI page
   - Navigate to "Manage" → "Publishing"
   - Click "Add a new pending publisher"
   - Fill in the details:
     - **Owner**: `loonghao`
     - **Repository name**: `diskcache_rs`
     - **Workflow name**: `CI.yml`
     - **Environment name**: `pypi`

3. **GitHub Environment Setup**:
   - Go to your GitHub repository settings
   - Navigate to "Environments"
   - Create a new environment named `pypi`
   - Add protection rules if desired (e.g., required reviewers for releases)

## Alternative: API Token Setup (Legacy)

If you prefer using API tokens:

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/)
2. Navigate to "API tokens" section
3. Click "Add API token"
4. Set the token name (e.g., "diskcache_rs-github-actions")
5. Set the scope to "Entire account" or specific to the `diskcache_rs` project
6. Copy the generated token (starts with `pypi-`)

Then add to GitHub Secrets:
1. Go to your GitHub repository settings
2. Navigate to "Secrets and variables" → "Actions"
3. Click "New repository secret"
4. Name: `PYPI_API_TOKEN`
5. Value: Paste your PyPI token (including the `pypi-` prefix)

## Release Process

### Automatic Release (Recommended)

1. **Update Version**: Update the version in `Cargo.toml`:
   ```toml
   [package]
   version = "0.2.0"  # Increment as needed
   ```

2. **Create and Push Tag**:
   ```bash
   git add Cargo.toml
   git commit -m "chore: bump version to 0.2.0"
   git tag v0.2.0
   git push origin main
   git push origin v0.2.0
   ```

3. **Automatic Build and Release**: The GitHub Actions workflow will automatically:
   - Build wheels for all supported platforms (Linux, macOS, Windows)
   - Build for multiple architectures (x86_64, aarch64, etc.)
   - Run all tests and benchmarks
   - Generate artifact attestations
   - Publish to PyPI

### Manual Release

You can also trigger a manual release:

1. Go to the "Actions" tab in your GitHub repository
2. Select the "CI" workflow
3. Click "Run workflow"
4. Select the branch and click "Run workflow"

This will build and publish without requiring a tag.

## Supported Platforms

The CI automatically builds wheels for:

### Linux
- x86_64 (Intel/AMD 64-bit)
- x86 (32-bit)
- aarch64 (ARM 64-bit)
- armv7 (ARM 32-bit)
- s390x (IBM Z)
- ppc64le (PowerPC 64-bit LE)

### Linux (musl)
- x86_64
- x86
- aarch64
- armv7

### Windows
- x64 (64-bit)
- x86 (32-bit)

### macOS
- x86_64 (Intel)
- aarch64 (Apple Silicon)

## Version Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## Troubleshooting

### Build Failures

If the build fails:
1. Check the GitHub Actions logs
2. Ensure all tests pass locally
3. Verify Rust code compiles with `cargo build --release`
4. Test Python bindings with `uvx maturin develop`

### PyPI Upload Failures

Common issues:
1. **Invalid token**: Verify the `PYPI_API_TOKEN` secret is correct
2. **Version already exists**: PyPI doesn't allow re-uploading the same version
3. **Package name conflict**: Ensure the package name is available

### Platform-specific Issues

- **Windows**: Ensure Windows-specific dependencies are properly configured
- **macOS**: Apple Silicon builds require macOS 14 runners
- **Linux**: Cross-compilation handled by maturin-action

## Post-Release

After a successful release:

1. **Verify Installation**: Test installation from PyPI:
   ```bash
   pip install diskcache_rs==0.2.0
   ```

2. **Update Documentation**: Update README.md with new version info if needed

3. **Create GitHub Release**: Optionally create a GitHub release with changelog

## Security

- **Trusted Publishing** (recommended): No secrets needed, uses OpenID Connect
- Never commit PyPI tokens to the repository
- Use GitHub Secrets for all sensitive information (if using API tokens)
- Regularly rotate PyPI API tokens (if using legacy method)
- Use scoped tokens when possible (project-specific rather than account-wide)
- Trusted Publishing provides better security through short-lived tokens
