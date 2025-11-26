mod gf256;
mod rs;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

use rs::{build_generator, encode as rs_encode, decode as rs_decode};

#[pyfunction]
fn encode<'py>(py: Python<'py>, nsym: usize, nsize: usize, message: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let k = nsize.saturating_sub(nsym);
    if message.len() != k {
        return Err(PyRuntimeError::new_err(format!(
            "message length {} does not match expected k={} for (n={}, nsym={})",
            message.len(), k, nsize, nsym
        )));
    }
    
    let generator = build_generator(nsym);
    let codeword = rs_encode(message, nsym, &generator);
    
    Ok(PyBytes::new(py, &codeword))
}

#[pyfunction]
fn decode<'py>(py: Python<'py>, nsym: usize, nsize: usize, codeword: &[u8]) -> PyResult<(Bound<'py, PyBytes>, Vec<usize>)> {
    if codeword.len() != nsize {
        return Err(PyRuntimeError::new_err(format!(
            "codeword length {} does not match expected n={}",
            codeword.len(), nsize
        )));
    }
    
    match rs_decode(codeword, nsym) {
        Ok((decoded, positions)) => {
            Ok((PyBytes::new(py, &decoded), positions))
        }
        Err(e) => Err(PyRuntimeError::new_err(e)),
    }
}

#[pymodule]
fn _rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode, m)?)?;
    m.add_function(wrap_pyfunction!(decode, m)?)?;
    Ok(())
}
