use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use thiserror::Error;

/// Custom error types for the cache
#[derive(Error, Debug)]
pub enum CacheError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Serialization error: {0}")]
    Serialization(String),

    #[error("Deserialization error: {0}")]
    Deserialization(String),

    #[error("Key not found: {0}")]
    KeyNotFound(String),

    #[error("Cache is full")]
    CacheFull,

    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("Network file system error: {0}")]
    NetworkFileSystem(String),

    #[error("Lock error: {0}")]
    Lock(String),

    #[error("Corruption detected: {0}")]
    Corruption(String),

    #[error("Operation timeout")]
    Timeout,

    #[error("Unknown error: {0}")]
    Unknown(String),
}

impl From<CacheError> for PyErr {
    fn from(err: CacheError) -> PyErr {
        PyException::new_err(err.to_string())
    }
}

pub type CacheResult<T> = Result<T, CacheError>;
