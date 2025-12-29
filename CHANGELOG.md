## v0.4.1 (2025-11-22)

### Fix

- sync Cargo.toml version with .cz.toml and update CHANGELOG for v0.4.0

## [0.4.5](https://github.com/loonghao/diskcache_rs/compare/diskcache_rs-v0.4.4...diskcache_rs-v0.4.5) (2025-12-29)


### Bug Fixes

* **deps:** update rust crate rusqlite to 0.38 ([22f31e5](https://github.com/loonghao/diskcache_rs/commit/22f31e5615806a512e9813e0a14e0f5d916bbad8))

## [0.4.4](https://github.com/loonghao/diskcache_rs/compare/diskcache_rs-v0.4.3...diskcache_rs-v0.4.4) (2025-11-22)


### Features

* support special characters in cache keys and auto-deserialization ([e56ad93](https://github.com/loonghao/diskcache_rs/commit/e56ad939b1c95456929d46887441c8d8610f1476))


### Bug Fixes

* resolve hashFiles path issue in GitHub Actions for macOS ([08abc64](https://github.com/loonghao/diskcache_rs/commit/08abc6442b2c7208b26038f28be07ab31dbccbe7))

## [0.4.3](https://github.com/loonghao/diskcache_rs/compare/diskcache_rs-v0.4.2...diskcache_rs-v0.4.3) (2025-11-22)


### Features

* implement advanced diskcache features (memoize, transact, iterkeys, peekitem) ([e11747d](https://github.com/loonghao/diskcache_rs/commit/e11747d5d6368e4ac96c850bb1ad748c0a87ec4a))
* improve API compatibility with python-diskcache ([b2b32fc](https://github.com/loonghao/diskcache_rs/commit/b2b32fc2918baa2593a75e7c6158487bfabb3e44))


### Bug Fixes

* critical persistence bug and improve version detection ([7de8f23](https://github.com/loonghao/diskcache_rs/commit/7de8f2361f9e6f47bc632dde9c6ab91f0716eb68))
* improve version fallback to read from Cargo.toml in development mode ([2aa633c](https://github.com/loonghao/diskcache_rs/commit/2aa633c6bd43b80216f2c8758fb21c88fb5ca984))
* remove emoji characters to fix Windows encoding issue ([59fda00](https://github.com/loonghao/diskcache_rs/commit/59fda00c3c213a2d020eb0210ae7a8fbd782ab76))


### Code Refactoring

* simplify version detection logic ([ab60b25](https://github.com/loonghao/diskcache_rs/commit/ab60b250b05f1e3e9ab9fcb730a48805eda4f46f))

## [0.4.2](https://github.com/loonghao/diskcache_rs/compare/diskcache_rs-v0.4.1...diskcache_rs-v0.4.2) (2025-11-22)


### Features

* add CI-friendly benchmark tests and fix gitignore ([41e5b0d](https://github.com/loonghao/diskcache_rs/commit/41e5b0d95f8bbb6ef28b6e80c59a849a4285571d))
* add configurable disk write threshold and NFS file locking support ([926b7ae](https://github.com/loonghao/diskcache_rs/commit/926b7aebf2f47644a5588b2787d4fa6cca3c0de1))
* add Docker network environment testing and fix unit tests ([e093503](https://github.com/loonghao/diskcache_rs/commit/e09350356f78f8dacda7c86448990198a3418987))
* add missing Cache methods for API compatibility ([a680e6c](https://github.com/loonghao/diskcache_rs/commit/a680e6ca14a7de891b3e3319d559f16fe50c1d2e))
* add missing exists() and keys() methods to Python Cache wrapper ([5d2ac2e](https://github.com/loonghao/diskcache_rs/commit/5d2ac2ed89a9a9318468d4e429bd787d5b7be6fb))
* add pre-commit hooks and fix dead code warnings ([7888637](https://github.com/loonghao/diskcache_rs/commit/78886373b08f7421da1ab381f33f4ece71db99c2))
* add release-please for automated version management ([3094a9b](https://github.com/loonghao/diskcache_rs/commit/3094a9bbb55c749d18b591909a1d829ce85e63d8))
* enhance CI/CD pipeline with comprehensive testing and PyPI publishing ([ae1f9fc](https://github.com/loonghao/diskcache_rs/commit/ae1f9fc2340c3a0491c73eaf44b1a5d2f25bf9db))
* implement complete diskcache API compatibility and official benchmarks ([8b17be2](https://github.com/loonghao/diskcache_rs/commit/8b17be228269b20c6a9a8abc6fcceaf836fb7f84))
* implement comprehensive Python type stub generation and packaging ([5638ce1](https://github.com/loonghao/diskcache_rs/commit/5638ce1b710f9008ed976ca5a06ec2e5fa64b0ee))
* implement drop-in replacement API for diskcache compatibility ([1fd9b87](https://github.com/loonghao/diskcache_rs/commit/1fd9b87fec8037c6741c9d5713db420458fe1ac2))
* implement high-performance pickle cache with expiration support ([a2e0195](https://github.com/loonghao/diskcache_rs/commit/a2e01952946d99ab255c0238cc2f0fafe07ae18b))
* implement release-plz for automated version management ([686b766](https://github.com/loonghao/diskcache_rs/commit/686b76627d0f0462c528418968965564b167923a))
* implement ultra-fast storage backends with superior performance ([0e98a88](https://github.com/loonghao/diskcache_rs/commit/0e98a88b2f890d6c64aec5fbdd4ed8cb13ad39c3))
* initial commit with diskcache_rs implementation ([3e925f6](https://github.com/loonghao/diskcache_rs/commit/3e925f69e5bae861ceaa80d203564290802de838))
* integrate pyo3-stub-gen for automatic Python type stub generation ([c4979b8](https://github.com/loonghao/diskcache_rs/commit/c4979b8afc33f87d78ee1cbe523626ee4688f69d))
* major performance optimization and code simplification ([b4bc816](https://github.com/loonghao/diskcache_rs/commit/b4bc816db3bfbeb4d8df05e0f5f1a5941ab163f8))
* make ABI3 support optional and enhance README with PyPI badges ([1647e29](https://github.com/loonghao/diskcache_rs/commit/1647e2917d02d4739279af0dff40ab1716e6a8d7))
* migrate from JSON to redb for persistent index storage ([704da2e](https://github.com/loonghao/diskcache_rs/commit/704da2e40fd434d4d54db100926ab1967194e711))
* modernize development setup and add ABI3 support ([14e5fae](https://github.com/loonghao/diskcache_rs/commit/14e5faebfa13191cecb4af0d1a2d1e58f26ba9fc))
* reduce disk write threshold from 4KB to 256 bytes ([1401387](https://github.com/loonghao/diskcache_rs/commit/14013876e7bd6cdfa142bfbc3fddebd2a5de597d))
* replace Python pickle with high-performance Rust implementation ([55bb204](https://github.com/loonghao/diskcache_rs/commit/55bb20491a9c2ad6efd6d5b20fc706443d407b6a))
* replace release-plz with commitizen for better multi-language support ([bbf036f](https://github.com/loonghao/diskcache_rs/commit/bbf036f0314375a18b5cce1c2af6144b12d1daac))
* simplify version bump workflow with commitizen-action ([e5fd037](https://github.com/loonghao/diskcache_rs/commit/e5fd0370e146926a013b3b75af46538b3c03ac22))
* upgrade CI/CD to use PyPI Trusted Publishing and comprehensive platform support ([3bf0d24](https://github.com/loonghao/diskcache_rs/commit/3bf0d241bb22e952437c725152a539f58bd91e6c))


### Bug Fixes

* add comprehensive GitHub Actions permissions for version management ([9877602](https://github.com/loonghao/diskcache_rs/commit/9877602b6de4bf3eb97bac892db1017f7c4c4074))
* add disk_write_threshold and use_file_locking support to PyCache ([5627965](https://github.com/loonghao/diskcache_rs/commit/56279656681603b4112e4e7a873ec3a8ed439f45))
* completely remove tokio dependency and async runtime ([9b16926](https://github.com/loonghao/diskcache_rs/commit/9b169268acc27218d184065ecfd614a78467ff1c))
* configure proper permissions for release workflows ([ab26244](https://github.com/loonghao/diskcache_rs/commit/ab26244421df399268cc17fca60abfd432a13ab6))
* correct fs4 FileExt import path ([a2dfcc3](https://github.com/loonghao/diskcache_rs/commit/a2dfcc3d7b74be4baeb8f0840cbc5de8acbdc274))
* correct pyo3-stubgen command syntax ([5526085](https://github.com/loonghao/diskcache_rs/commit/552608595707689b5e15db865617e778e012c35b))
* correct ruff target-version configuration ([17c826e](https://github.com/loonghao/diskcache_rs/commit/17c826ecfc1906896f23ae25204bfb422cde3234))
* correct uv syntax and dependency versions for Python 3.8+ compatibility ([2d7d89a](https://github.com/loonghao/diskcache_rs/commit/2d7d89a07bbbc69046a647a4dde31b826bab5952))
* **deps:** update rust crate lz4_flex to 0.12 ([7711aa3](https://github.com/loonghao/diskcache_rs/commit/7711aa3cfbf510030875e104040725f41d232269))
* **deps:** update rust crate memmap2 to v0.9.7 ([41d2bad](https://github.com/loonghao/diskcache_rs/commit/41d2bad392e89d4e175ef780dd05a2faed491fa0))
* **deps:** update rust crate serde_json to v1.0.141 ([b53f162](https://github.com/loonghao/diskcache_rs/commit/b53f162eb724bf16b874985867c330cfa6ef21e5))
* ensure cache is closed before checking redb file in tests ([6e0bbf7](https://github.com/loonghao/diskcache_rs/commit/6e0bbf740c7b1b3c7b34589f0492164442309aca))
* improve __contains__ method implementation for better compatibility ([f1d38c1](https://github.com/loonghao/diskcache_rs/commit/f1d38c15f7c80dcf36507570762eca7761bae5c3))
* improve CI benchmark testing and add comprehensive test suite ([b403134](https://github.com/loonghao/diskcache_rs/commit/b403134ff4a437a2e6dc6fdc7d2c64221a3be75b))
* improve commitizen configuration and bump-version workflow ([c3958ac](https://github.com/loonghao/diskcache_rs/commit/c3958acc843acd969f23fe8288e31cb4fd4d4e5b))
* improve commitizen workflow with debug and proper permissions ([ea54177](https://github.com/loonghao/diskcache_rs/commit/ea541771ad58ee2586b66a0bf5f5c7f6db190787))
* make CI and build workflows reusable for release workflow ([d5912b1](https://github.com/loonghao/diskcache_rs/commit/d5912b146467a6aca537d7ad50e83dae6962b2aa))
* make vacuum() synchronous to ensure disk writes complete ([7fa9cb3](https://github.com/loonghao/diskcache_rs/commit/7fa9cb379e36acd088f2e7260d88a88e3da7f729))
* persist cache index to disk to prevent data loss on restart ([00ddb35](https://github.com/loonghao/diskcache_rs/commit/00ddb351a90d5d790c9501bee81c264a9cbe3ea3))
* remove commitizen to avoid conflict with release-please ([90e1178](https://github.com/loonghao/diskcache_rs/commit/90e1178f552def1d5be31642f9e59da9c7abf302))
* remove unsupported --compatibility abi3 flag from GitHub Actions ([d401675](https://github.com/loonghao/diskcache_rs/commit/d4016753676fe920b19e0270dd9db51480815d87))
* replace std::io::Error::new with std::io::Error::other for clippy ([63017cc](https://github.com/loonghao/diskcache_rs/commit/63017cc668bc466125b48d5951ee24c0d4be2d66))
* replace tokio async runtime with standard threads ([92883bd](https://github.com/loonghao/diskcache_rs/commit/92883bd1f1d1e3ce2c8a4fee258612fbed33118e))
* resolve all clippy warnings and test import issues ([d59909a](https://github.com/loonghao/diskcache_rs/commit/d59909af729da02736fccd36b57dbe0bac6a7314))
* resolve all code quality issues and formatting problems ([cdbafc9](https://github.com/loonghao/diskcache_rs/commit/cdbafc9ab88c72dfca28710d06f3df2164ec20c0))
* resolve Alpine Linux ARMv7 py3-venv package availability issue ([e065518](https://github.com/loonghao/diskcache_rs/commit/e065518e98ca5c8c3934ae32c4fb10e81743d2a0))
* resolve Alpine Linux externally-managed-environment errors in CI ([2963aea](https://github.com/loonghao/diskcache_rs/commit/2963aea6913cb98b03199e17becf5f79b93b1dfd))
* resolve bincode import issues in Rust compilation ([2aa2fe1](https://github.com/loonghao/diskcache_rs/commit/2aa2fe1d0e4fee58820e92a865ca53330cd3a76d))
* resolve CI build failures by adding maturin installation step ([fcec531](https://github.com/loonghao/diskcache_rs/commit/fcec531ebc916adcc2c95b716630f7cbe1c752f1))
* resolve CI build issues and remove analysis doc ([054830b](https://github.com/loonghao/diskcache_rs/commit/054830b26355378a29871f051fececf050cadcfa))
* resolve CI syntax error and code quality issues ([23ff470](https://github.com/loonghao/diskcache_rs/commit/23ff4703662346cd8fe08a3329262f019858e34f))
* resolve CI test failures and clippy format issues ([2b07ac8](https://github.com/loonghao/diskcache_rs/commit/2b07ac882eb38d8fbfac4bb3aab9868687652709))
* resolve circular import issue in Python wrapper ([7cfa6bc](https://github.com/loonghao/diskcache_rs/commit/7cfa6bc6a79d9af780efe933c6f4a00d14d13eaf))
* resolve cross-platform build issues and modernize CI/CD ([db055a1](https://github.com/loonghao/diskcache_rs/commit/db055a1ed4c3befcc8f0c3170ea670bbd2894cae))
* resolve final ruff CI linting issues ([8c5ea9a](https://github.com/loonghao/diskcache_rs/commit/8c5ea9a8635dec39a0f13b2d466ed8fcfe15e028))
* resolve macOS build issues and add comprehensive benchmark tests ([419bc67](https://github.com/loonghao/diskcache_rs/commit/419bc678a9c05de25d1c613954b70e24b4c0718f))
* resolve merge conflicts and correct version field configurations ([edd0b34](https://github.com/loonghao/diskcache_rs/commit/edd0b34261960dcef71f8b59d486f1b92436c9fa))
* resolve module naming conflicts and API compatibility issues ([a09941d](https://github.com/loonghao/diskcache_rs/commit/a09941deada506911515bb7e2a2afb5df3f4a7eb))
* resolve Python 3.8 compatibility and ruff configuration issues ([585792b](https://github.com/loonghao/diskcache_rs/commit/585792bc1307730e907734c3d56807f9c3ba7b09))
* resolve release changelog generation issues ([7cb0690](https://github.com/loonghao/diskcache_rs/commit/7cb069043e916d72b78547e1bc06bf07ae947e6a))
* resolve ruff linting issues ([0ee2894](https://github.com/loonghao/diskcache_rs/commit/0ee28948f0d2cb1e64a05d4d956d9ed694133ad0))
* resolve version mismatch and optimize CI configuration ([d36af7b](https://github.com/loonghao/diskcache_rs/commit/d36af7b0515c0d34fe88f5d691a16cbbccc4b693))
* resolve Windows pytest and CI issues ([8946860](https://github.com/loonghao/diskcache_rs/commit/8946860a489a466042e428f72b438313d6a45a48))
* resolve Windows timing precision issue in pickle performance tests ([d6fecd4](https://github.com/loonghao/diskcache_rs/commit/d6fecd468ca9cb126f37626d9d41a0f0fb7f2ddd))
* resolve Windows timing precision issues across all performance tests ([964d0b1](https://github.com/loonghao/diskcache_rs/commit/964d0b18a069b7018259a0427bf757eb1cecc07e))
* support both old and new parameter names in RustCache ([314f3e2](https://github.com/loonghao/diskcache_rs/commit/314f3e2c8ef21c0677abcdd8d9faa5322a7f18a4))
* sync Cargo.toml version with .cz.toml and update CHANGELOG for v0.4.0 ([58ac4c7](https://github.com/loonghao/diskcache_rs/commit/58ac4c74c4dbf39c7ef9bdb1924a3b76af89d741))


### Performance Improvements

* auto-persist index every 100 writes and on drop ([e307d37](https://github.com/loonghao/diskcache_rs/commit/e307d3768ce0914f178fd449085994f5f8c5ebff))
* increase disk write threshold from 256B to 1KB for better performance ([6739da7](https://github.com/loonghao/diskcache_rs/commit/6739da7e48be75862e891b28dcf673bec1ac9772))


### Code Refactoring

* adopt pydantic-core style dependency management and fix Linux CI issues ([493c60c](https://github.com/loonghao/diskcache_rs/commit/493c60c178e9d6566de97090687b55a4a7e2770c))
* remove diskcache as runtime dependency, make it optional for benchmarks ([d91671a](https://github.com/loonghao/diskcache_rs/commit/d91671a559db7c17a198f7eff68c95fdb5022330))
* remove pyo3-stub-gen dependency and auto-generation complexity ([92ecd9a](https://github.com/loonghao/diskcache_rs/commit/92ecd9aea0387dd3af9229f29bdb762b40eb48a0))
* restructure tests to use pytest and split CI workflows ([4635035](https://github.com/loonghao/diskcache_rs/commit/4635035fa16ab7f7239c763d462d0915ff113415))


### Documentation

* add commitizen release process documentation to README ([80ab3fe](https://github.com/loonghao/diskcache_rs/commit/80ab3fe19f7d8738092d609f1720fdf46f96bb10))
* add documentation for CacheConfig fields ([c6e1f3f](https://github.com/loonghao/diskcache_rs/commit/c6e1f3fe4fef643ab6df667eb79c1d5c2b87fe54))

## v0.4.0 (2025-11-22)

### Feat

- migrate from JSON to redb for persistent index storage

### Fix

- replace std::io::Error::new with std::io::Error::other for clippy
- ensure cache is closed before checking redb file in tests
- persist cache index to disk to prevent data loss on restart
- add disk_write_threshold and use_file_locking support to PyCache
- support both old and new parameter names in RustCache
- correct fs4 FileExt import path

### Perf

- auto-persist index every 100 writes and on drop

## v0.3.1 (2025-11-21)

### Fix

- **deps**: update rust crate lz4_flex to 0.12

## v0.3.0 (2025-11-21)

### Feat

- add pre-commit hooks and fix dead code warnings
- reduce disk write threshold from 4KB to 256 bytes

### Fix

- correct pyo3-stubgen command syntax
- make vacuum() synchronous to ensure disk writes complete
- resolve CI build issues and remove analysis doc
- resolve version mismatch and optimize CI configuration

### Perf

- increase disk write threshold from 256B to 1KB for better performance

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
