use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

mod cache;
mod storage;
mod serialization;
mod eviction;
mod error;
mod utils;
mod memory_cache;
mod migration;

pub use cache::Cache;
pub use error::{CacheError, CacheResult};
pub use migration::{DiskCacheMigrator, MigrationStats, detect_diskcache_format};

/// A Python module implemented in Rust.
#[pymodule]
fn diskcache_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<cache::PyCache>()?;
    m.add_function(wrap_pyfunction!(detect_diskcache_format_py, m)?)?;
    Ok(())
}

/// Python wrapper for detect_diskcache_format
#[pyfunction]
fn detect_diskcache_format_py(path: String) -> bool {
    migration::detect_diskcache_format(std::path::Path::new(&path))
}
