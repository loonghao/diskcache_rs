use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod cache;
mod error;
mod eviction;
mod memory_cache;
mod migration;
mod pickle_cache;
mod serialization;
mod storage;
mod utils;

pub use cache::DiskCache;
pub use error::{CacheError, CacheResult};
pub use migration::{detect_diskcache_format, DiskCacheMigrator, MigrationStats};

/// A Python module implemented in Rust.
#[pymodule]
fn _diskcache_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Add the main cache class
    m.add_class::<cache::PyCache>()?;

    // Add compatibility aliases for drop-in replacement
    m.add_class::<cache::RustCache>()?;
    m.add_class::<cache::RustFanoutCache>()?;

    // Add pickle cache class
    m.add_class::<pickle_cache::PickleCache>()?;

    // Add utility functions
    m.add_function(wrap_pyfunction!(detect_diskcache_format_py, m)?)?;

    // Add high-performance pickle functions
    m.add_function(wrap_pyfunction!(crate::pickle_cache::rust_pickle_dumps, m)?)?;
    m.add_function(wrap_pyfunction!(crate::pickle_cache::rust_pickle_loads, m)?)?;

    Ok(())
}

/// Python wrapper for detect_diskcache_format
#[pyfunction]
fn detect_diskcache_format_py(path: String) -> bool {
    migration::detect_diskcache_format(std::path::Path::new(&path))
}
