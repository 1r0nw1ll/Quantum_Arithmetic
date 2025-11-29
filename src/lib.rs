// QA Lab - Rust Port
// Core library for Quantum Arithmetic research framework

pub mod agent_helpers;
pub mod qa_core;

pub use agent_helpers::{DataCollector, MLHelper};
pub use qa_core::{QABundle, QAInvariants, QATuple};

// PyO3 Python extension module to expose core invariants to Python.
// This allows the existing Python QA lab to call into the Rust implementation.
#[allow(unused_imports)]
#[cfg(feature = "portable_simd")]
use core::simd::Simd;
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use rayon::prelude::*;
use std::collections::HashSet;
use std::sync::{Arc, Mutex, OnceLock};

#[inline]
fn dot8_scalar(a: &[f64], b: &[f64]) -> f64 {
    debug_assert!(a.len() >= 8 && b.len() >= 8);
    let mut s = 0.0f64;
    // Unrolled for fixed 8D vectors
    s += a[0] * b[0];
    s += a[1] * b[1];
    s += a[2] * b[2];
    s += a[3] * b[3];
    s += a[4] * b[4];
    s += a[5] * b[5];
    s += a[6] * b[6];
    s += a[7] * b[7];
    s
}

#[inline]
fn dot8(a: &[f64], b: &[f64]) -> f64 {
    #[cfg(all(target_arch = "x86_64"))]
    {
        if is_x86_feature_detected!("avx2") {
            unsafe {
                use core::arch::x86_64::*;
                // Load 8 doubles as two 256-bit vectors
                let a0 = _mm256_loadu_pd(a.as_ptr());
                let b0 = _mm256_loadu_pd(b.as_ptr());
                let a1 = _mm256_loadu_pd(a.as_ptr().add(4));
                let b1 = _mm256_loadu_pd(b.as_ptr().add(4));
                let m0 = _mm256_mul_pd(a0, b0);
                let m1 = _mm256_mul_pd(a1, b1);
                let sum = _mm256_add_pd(m0, m1);
                // Horizontal sum
                let mut tmp = [0.0f64; 4];
                _mm256_storeu_pd(tmp.as_mut_ptr(), sum);
                return tmp.iter().sum();
            }
        }
    }
    // Fallback
    dot8_scalar(a, b)
}

#[inline]
fn norm8(a: &[f64]) -> f64 {
    dot8(a, a).sqrt()
}

#[inline]
fn transpose_roots_cols(r: &ndarray::ArrayView2<'_, f64>) -> [Vec<f64>; 8] {
    let m = r.nrows();
    let ncols = r.ncols();
    assert!(ncols >= 8, "roots must have at least 8 columns");
    let mut c0 = vec![0.0f64; m];
    let mut c1 = vec![0.0f64; m];
    let mut c2 = vec![0.0f64; m];
    let mut c3 = vec![0.0f64; m];
    let mut c4 = vec![0.0f64; m];
    let mut c5 = vec![0.0f64; m];
    let mut c6 = vec![0.0f64; m];
    let mut c7 = vec![0.0f64; m];
    for j in 0..m {
        let row = r.row(j);
        c0[j] = row[0];
        c1[j] = row[1];
        c2[j] = row[2];
        c3[j] = row[3];
        c4[j] = row[4];
        c5[j] = row[5];
        c6[j] = row[6];
        c7[j] = row[7];
    }
    [c0, c1, c2, c3, c4, c5, c6, c7]
}

#[derive(Clone)]
struct ColsCache {
    addr: usize,
    m: usize,
    ncols: usize,
    cols: Arc<[Vec<f64>; 8]>,
}

static ROOT_COLS_CACHE: OnceLock<Mutex<ColsCache>> = OnceLock::new();

fn get_root_cols_cached(r: &ndarray::ArrayView2<'_, f64>) -> Arc<[Vec<f64>; 8]> {
    let addr = r.as_ptr() as usize;
    let m = r.nrows();
    let ncols = r.ncols();
    if let Some(lock) = ROOT_COLS_CACHE.get() {
        if let Ok(cache) = lock.lock() {
            if cache.addr == addr && cache.m == m && cache.ncols == ncols {
                return cache.cols.clone();
            }
        }
    }
    let cols_arr = transpose_roots_cols(r);
    let cols_arc: Arc<[Vec<f64>; 8]> = Arc::new(cols_arr);
    let cache = ColsCache {
        addr,
        m,
        ncols,
        cols: cols_arc.clone(),
    };
    let lock = ROOT_COLS_CACHE.get_or_init(|| Mutex::new(cache.clone()));
    if let Ok(mut c) = lock.lock() {
        *c = cache;
    }
    cols_arc
}

#[derive(Clone)]
struct NormsCache {
    addr: usize,
    m: usize,
    ncols: usize,
    norms: Arc<Vec<f64>>,
}

static ROOT_NORMS_CACHE: OnceLock<Mutex<NormsCache>> = OnceLock::new();

fn get_root_norms_cached(r: &ndarray::ArrayView2<'_, f64>) -> Arc<Vec<f64>> {
    let addr = r.as_ptr() as usize;
    let m = r.nrows();
    let ncols = r.ncols();
    if let Some(lock) = ROOT_NORMS_CACHE.get() {
        if let Ok(cache) = lock.lock() {
            if cache.addr == addr && cache.m == m && cache.ncols == ncols {
                return cache.norms.clone();
            }
        }
    }
    // Compute norms
    let mut norms = Vec::with_capacity(m);
    for j in 0..m {
        let row = r.row(j);
        let b = unsafe { std::slice::from_raw_parts(row.as_ptr(), ncols) };
        norms.push(norm8(b));
    }
    let arc = Arc::new(norms);
    let cache = NormsCache {
        addr,
        m,
        ncols,
        norms: arc.clone(),
    };
    let lock = ROOT_NORMS_CACHE.get_or_init(|| Mutex::new(cache.clone()));
    if let Ok(mut c) = lock.lock() {
        *c = cache;
    }
    arc
}

#[pyfunction]
fn compute_bundle_py(b: f64, e: f64, d: f64, a: f64) -> PyResult<PyObject> {
    let j = b * d;
    let k = d * a;
    let x = e * d;
    let w = x + k;
    let y = a * a - d * d;
    let z = e * e + k;
    let c = 2.0 * x;
    let f = b * a;
    let g = e * e + d * d;

    Python::with_gil(|py| {
        let dict = PyDict::new_bound(py);
        dict.set_item("b", b)?;
        dict.set_item("e", e)?;
        dict.set_item("d", d)?;
        dict.set_item("a", a)?;
        dict.set_item("J", j)?;
        dict.set_item("K", k)?;
        dict.set_item("X", x)?;
        dict.set_item("W", w)?;
        dict.set_item("Y", y)?;
        dict.set_item("Z", z)?;
        dict.set_item("C", c)?;
        dict.set_item("F", f)?;
        dict.set_item("G", g)?;
        Ok(dict.into())
    })
}

#[pyfunction]
fn ping() -> &'static str {
    "qa_lab_rs:ok"
}

#[pyfunction]
fn cosine_similarity_py(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    use ndarray::Array1;
    let a_arr = Array1::from_vec(a);
    let b_arr = Array1::from_vec(b);
    Ok(MLHelper::cosine_similarity(&a_arr, &b_arr))
}

#[pyfunction]
fn normalize_py(arr: Vec<f64>) -> PyResult<Vec<f64>> {
    use ndarray::Array1;
    let arr_nd = Array1::from_vec(arr);
    let normalized = MLHelper::normalize(&arr_nd);
    Ok(normalized.to_vec())
}

#[pyfunction]
fn random_qa_tuple_py() -> PyResult<(f64, f64, f64, f64)> {
    Ok(MLHelper::random_qa_tuple())
}

#[pyfunction]
fn extract_qa_patterns_py(text: String) -> PyResult<Vec<(f64, f64, f64, f64)>> {
    Ok(DataCollector::extract_qa_patterns(&text))
}

#[pyfunction]
fn compute_bundle_batch_py(
    b_vec: Vec<f64>,
    e_vec: Vec<f64>,
    d_vec: Vec<f64>,
    a_vec: Vec<f64>,
) -> PyResult<Vec<PyObject>> {
    let len = b_vec.len();
    if e_vec.len() != len || d_vec.len() != len || a_vec.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "All input vectors must have the same length",
        ));
    }

    Python::with_gil(|py| {
        let mut results = Vec::with_capacity(len);
        for i in 0..len {
            let b = b_vec[i];
            let e = e_vec[i];
            let d = d_vec[i];
            let a = a_vec[i];

            let j = b * d;
            let k = d * a;
            let x = e * d;
            let w = x + k;
            let y = a * a - d * d;
            let z = e * e + k;
            let c = 2.0 * x;
            let f = b * a;
            let g = e * e + d * d;

            let dict = PyDict::new_bound(py);
            dict.set_item("b", b)?;
            dict.set_item("e", e)?;
            dict.set_item("d", d)?;
            dict.set_item("a", a)?;
            dict.set_item("J", j)?;
            dict.set_item("K", k)?;
            dict.set_item("X", x)?;
            dict.set_item("W", w)?;
            dict.set_item("Y", y)?;
            dict.set_item("Z", z)?;
            dict.set_item("C", c)?;
            dict.set_item("F", f)?;
            dict.set_item("G", g)?;
            results.push(dict.into());
        }
        Ok(results)
    })
}

/// High-performance batch computation returning NumPy arrays.
/// Accepts 1D float64 NumPy arrays (same length) and returns a dict of NumPy arrays.
#[pyfunction]
fn compute_bundle_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyDict>> {
    let b_slice = b.as_slice()?;
    let e_slice = e.as_slice()?;
    let d_slice = d.as_slice()?;
    let a_slice = a.as_slice()?;

    let len = b_slice.len();
    if e_slice.len() != len || d_slice.len() != len || a_slice.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "All input arrays must have the same length",
        ));
    }
    // Compute outputs in parallel without intermediate tuple buffers
    let jv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| b_slice[i] * d_slice[i])
            .collect()
    });
    let kv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| d_slice[i] * a_slice[i])
            .collect()
    });
    let xv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| e_slice[i] * d_slice[i])
            .collect()
    });
    let wv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| (e_slice[i] * d_slice[i]) + (d_slice[i] * a_slice[i]))
            .collect()
    });
    let yv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| a_slice[i] * a_slice[i] - d_slice[i] * d_slice[i])
            .collect()
    });
    let zv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| e_slice[i] * e_slice[i] + (d_slice[i] * a_slice[i]))
            .collect()
    });
    let cv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| 2.0 * e_slice[i] * d_slice[i])
            .collect()
    });
    let fv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| b_slice[i] * a_slice[i])
            .collect()
    });
    let gv: Vec<f64> = py.allow_threads(|| {
        (0..len)
            .into_par_iter()
            .map(|i| e_slice[i] * e_slice[i] + d_slice[i] * d_slice[i])
            .collect()
    });

    // Build Python dict of NumPy arrays
    let dict = PyDict::new_bound(py);
    dict.set_item("J", PyArray1::from_vec_bound(py, jv))?;
    dict.set_item("K", PyArray1::from_vec_bound(py, kv))?;
    dict.set_item("X", PyArray1::from_vec_bound(py, xv))?;
    dict.set_item("W", PyArray1::from_vec_bound(py, wv))?;
    dict.set_item("Y", PyArray1::from_vec_bound(py, yv))?;
    dict.set_item("Z", PyArray1::from_vec_bound(py, zv))?;
    dict.set_item("C", PyArray1::from_vec_bound(py, cv))?;
    dict.set_item("F", PyArray1::from_vec_bound(py, fv))?;
    dict.set_item("G", PyArray1::from_vec_bound(py, gv))?;
    Ok(dict.unbind())
}

/// High-performance batch computation assuming QA closure:
/// d = b + e and a = e + d = b + 2e. Accepts NumPy arrays b,e and returns dict of NumPy arrays.
#[pyfunction]
fn compute_bundle_batch_numpy_closure_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyDict>> {
    let b_slice = b.as_slice()?;
    let e_slice = e.as_slice()?;
    let len = b_slice.len();
    if e_slice.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "Input arrays must have the same length",
        ));
    }

    // Raw pointers to avoid cloning before releasing GIL
    let b_addr = b_slice.as_ptr() as usize;
    let e_addr = e_slice.as_ptr() as usize;

    // Compute in parallel: use closure formulas to reduce memory ops
    let results: Vec<(f64, f64, f64, f64, f64, f64, f64, f64, f64)> = py.allow_threads(move || {
        let b_in = unsafe { std::slice::from_raw_parts(b_addr as *const f64, len) };
        let e_in = unsafe { std::slice::from_raw_parts(e_addr as *const f64, len) };
        (0..len)
            .into_par_iter()
            .map(|i| {
                let b = b_in[i];
                let e = e_in[i];
                // d = b + e; a = b + 2e
                // Invariants simplified under closure
                let be = b * e;
                let e2 = e * e;
                let b2 = b * b;

                let j = b2 + be; // b*d
                let k = b2 + 3.0 * be + 2.0 * e2; // d*a
                let x = be + e2; // e*d
                let w = x + k; // X + K
                let y = 2.0 * be + 3.0 * e2; // a^2 - d^2
                let z = b2 + 3.0 * be + 3.0 * e2; // e^2 + K
                let c = 2.0 * x; // 2X
                let f = b2 + 2.0 * be; // b*a
                let g = b2 + 2.0 * be + 2.0 * e2; // e^2 + d^2
                (j, k, x, w, y, z, c, f, g)
            })
            .collect()
    });

    // Split into arrays
    let mut jv = Vec::with_capacity(len);
    let mut kv = Vec::with_capacity(len);
    let mut xv = Vec::with_capacity(len);
    let mut wv = Vec::with_capacity(len);
    let mut yv = Vec::with_capacity(len);
    let mut zv = Vec::with_capacity(len);
    let mut cv = Vec::with_capacity(len);
    let mut fv = Vec::with_capacity(len);
    let mut gv = Vec::with_capacity(len);
    for (j, k, x, w, y, z, c, f, g) in results.into_iter() {
        jv.push(j);
        kv.push(k);
        xv.push(x);
        wv.push(w);
        yv.push(y);
        zv.push(z);
        cv.push(c);
        fv.push(f);
        gv.push(g);
    }

    let dict = PyDict::new_bound(py);
    dict.set_item("J", PyArray1::from_vec_bound(py, jv))?;
    dict.set_item("K", PyArray1::from_vec_bound(py, kv))?;
    dict.set_item("X", PyArray1::from_vec_bound(py, xv))?;
    dict.set_item("W", PyArray1::from_vec_bound(py, wv))?;
    dict.set_item("Y", PyArray1::from_vec_bound(py, yv))?;
    dict.set_item("Z", PyArray1::from_vec_bound(py, zv))?;
    dict.set_item("C", PyArray1::from_vec_bound(py, cv))?;
    dict.set_item("F", PyArray1::from_vec_bound(py, fv))?;
    dict.set_item("G", PyArray1::from_vec_bound(py, gv))?;
    Ok(dict.unbind())
}
#[pymodule]
fn qa_lab_rs(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Core QA operations
    m.add_function(wrap_pyfunction!(compute_bundle_py, m)?)?;
    m.add_function(wrap_pyfunction!(ping, m)?)?;

    // ML helper functions (torch-free!)
    m.add_function(wrap_pyfunction!(cosine_similarity_py, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_py, m)?)?;
    m.add_function(wrap_pyfunction!(random_qa_tuple_py, m)?)?;

    // Data collection helpers
    m.add_function(wrap_pyfunction!(extract_qa_patterns_py, m)?)?;
    m.add_function(wrap_pyfunction!(compute_bundle_batch_py, m)?)?;
    m.add_function(wrap_pyfunction!(compute_bundle_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(compute_bundle_batch_numpy_closure_py, m)?)?;
    m.add_function(wrap_pyfunction!(compute_e8_alignment_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(
        compute_e8_alignment_batch_numpy_prenorm_py,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(mod24_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(digital_root_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(closure_residual_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(inner_ellipse_residual_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(triangle_residual_batch_numpy_py, m)?)?;
    // QE and utility exports
    m.add_function(wrap_pyfunction!(qe_score_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(qe_score_with_inv_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(harmonic_index_batch_numpy_py, m)?)?;
    m.add_function(wrap_pyfunction!(stream_buffers_init_py, m)?)?;
    m.add_function(wrap_pyfunction!(stream_buffers_release_py, m)?)?;

    // Bell test kernels
    m.add_function(wrap_pyfunction!(compute_chsh_qa, m)?)?;
    m.add_function(wrap_pyfunction!(compute_i3322_qa, m)?)?;
    m.add_function(wrap_pyfunction!(bell_octahedron_qa, m)?)?;
    m.add_function(wrap_pyfunction!(bell_icosahedron_qa, m)?)?;
    m.add_function(wrap_pyfunction!(bell_dodecahedron_qa, m)?)?;

    // Optional SIMD-accelerated batch path (portable-simd). If unavailable on toolchain,
    // this function will be omitted at compile time.
    #[cfg(any())]
    {
        // placeholder to keep section in place if needed in future
    }

    Ok(())
}

/// Experimental: SIMD-accelerated general batch using core::simd::Simd if available.
/// Not exported until stabilized across toolchains.
#[cfg(feature = "portable_simd")]
#[allow(dead_code)]
fn compute_simd_batch(
    b: &[f64],
    e: &[f64],
    d: &[f64],
    a: &[f64],
) -> (
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
    Vec<f64>,
) {
    let len = b.len();
    let mut jv = vec![0.0; len];
    let mut kv = vec![0.0; len];
    let mut xv = vec![0.0; len];
    let mut wv = vec![0.0; len];
    let mut yv = vec![0.0; len];
    let mut zv = vec![0.0; len];
    let mut cv = vec![0.0; len];
    let mut fv = vec![0.0; len];
    let mut gv = vec![0.0; len];

    // Try vectorized path with 4 lanes; remainder handled scalar.
    let lanes = 4;
    let mut i = 0;
    while i + lanes <= len {
        // SAFETY: bounds checked by loop condition
        let b_v = Simd::<f64, 4>::from_slice(&b[i..i + lanes]);
        let e_v = Simd::<f64, 4>::from_slice(&e[i..i + lanes]);
        let d_v = Simd::<f64, 4>::from_slice(&d[i..i + lanes]);
        let a_v = Simd::<f64, 4>::from_slice(&a[i..i + lanes]);

        let j = b_v * d_v;
        let k = d_v * a_v;
        let x = e_v * d_v;
        let w = x + k;
        let y = a_v * a_v - d_v * d_v;
        let z = e_v * e_v + k;
        let c = x + x;
        let f = b_v * a_v;
        let g = e_v * e_v + d_v * d_v;

        j.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| jv[i + off] = val);
        k.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| kv[i + off] = val);
        x.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| xv[i + off] = val);
        w.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| wv[i + off] = val);
        y.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| yv[i + off] = val);
        z.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| zv[i + off] = val);
        c.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| cv[i + off] = val);
        f.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| fv[i + off] = val);
        g.as_array()
            .iter()
            .enumerate()
            .for_each(|(off, &val)| gv[i + off] = val);

        i += lanes;
    }
    while i < len {
        let b = b[i];
        let e = e[i];
        let d = d[i];
        let a = a[i];
        let j = b * d;
        let k = d * a;
        let x = e * d;
        jv[i] = j;
        kv[i] = k;
        xv[i] = x;
        wv[i] = x + k;
        yv[i] = a * a - d * d;
        zv[i] = e * e + k;
        cv[i] = 2.0 * x;
        fv[i] = b * a;
        gv[i] = e * e + d * d;
        i += 1;
    }

    (jv, kv, xv, wv, yv, zv, cv, fv, gv)
}
/// Compute E8 alignment for a batch of vectors against a set of roots.
/// vectors: shape (N, D) expected D=8; roots: shape (M, D)
#[pyfunction]
fn compute_e8_alignment_batch_numpy_py<'py>(
    py: Python<'py>,
    vectors: PyReadonlyArray2<'py, f64>,
    roots: PyReadonlyArray2<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let v = vectors.as_array();
    let r = roots.as_array();
    if v.ncols() != r.ncols() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "vectors and roots must have same feature dimension",
        ));
    }
    let n = v.nrows();
    let m = r.nrows();
    if n == 0 || m == 0 {
        let out = PyArray1::<f64>::zeros_bound(py, 0, false);
        return Ok(out.unbind());
    }

    // Cached root norms and pre-transposed columns for better cache locality
    let dcols = r.ncols();
    let norms_arc = get_root_norms_cached(&r);
    let cols_arc = get_root_cols_cached(&r);
    let res: Vec<f64> = py.allow_threads(|| {
        let norms = norms_arc; // Arc moved into closure
        let cols = cols_arc;
        (0..n)
            .into_par_iter()
            .map(|i| {
                let vec_i = v.row(i);
                let a = unsafe { std::slice::from_raw_parts(vec_i.as_ptr(), dcols) };
                let norm_v = norm8(a);
                if norm_v == 0.0 {
                    return 0.0;
                }
                let inv_nv = 1.0 / norm_v;
                let mut max_sim = -1.0f64;
                let mlen = m;
                let mut j = 0;
                // AVX2: 4 roots per iteration
                #[cfg(all(target_arch = "x86_64"))]
                unsafe {
                    if is_x86_feature_detected!("avx2") {
                        use core::arch::x86_64::*;
                        let a0 = _mm256_set1_pd(a[0]);
                        let a1 = _mm256_set1_pd(a[1]);
                        let a2 = _mm256_set1_pd(a[2]);
                        let a3 = _mm256_set1_pd(a[3]);
                        let a4 = _mm256_set1_pd(a[4]);
                        let a5 = _mm256_set1_pd(a[5]);
                        let a6 = _mm256_set1_pd(a[6]);
                        let a7 = _mm256_set1_pd(a[7]);
                        let inv = _mm256_set1_pd(inv_nv);
                        while j + 4 <= mlen {
                            let c0 = _mm256_loadu_pd(cols[0].as_ptr().add(j));
                            let c1 = _mm256_loadu_pd(cols[1].as_ptr().add(j));
                            let c2 = _mm256_loadu_pd(cols[2].as_ptr().add(j));
                            let c3 = _mm256_loadu_pd(cols[3].as_ptr().add(j));
                            let c4 = _mm256_loadu_pd(cols[4].as_ptr().add(j));
                            let c5 = _mm256_loadu_pd(cols[5].as_ptr().add(j));
                            let c6 = _mm256_loadu_pd(cols[6].as_ptr().add(j));
                            let c7 = _mm256_loadu_pd(cols[7].as_ptr().add(j));
                            let mut acc = _mm256_mul_pd(c0, a0);
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c1, a1));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c2, a2));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c3, a3));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c4, a4));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c5, a5));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c6, a6));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c7, a7));
                            let inv_r = _mm256_loadu_pd(norms.as_ptr().add(j));
                            // build 1/norm_r, handling zeros by leaving zero
                            let one = _mm256_set1_pd(1.0);
                            let eps = _mm256_set1_pd(1e-12);
                            let mask = _mm256_cmp_pd(inv_r, eps, _CMP_GT_OQ);
                            let inv_r_safe = _mm256_blendv_pd(
                                _mm256_set1_pd(0.0),
                                _mm256_div_pd(one, inv_r),
                                mask,
                            );
                            let acc_nv = _mm256_mul_pd(acc, inv);
                            let sims = _mm256_mul_pd(acc_nv, inv_r_safe);
                            let mut tmp = [0.0f64; 4];
                            _mm256_storeu_pd(tmp.as_mut_ptr(), sims);
                            for &val in &tmp {
                                if val > max_sim {
                                    max_sim = val;
                                }
                            }
                            j += 4;
                        }
                    }
                }
                while j < mlen {
                    let dot = a[0] * cols[0][j]
                        + a[1] * cols[1][j]
                        + a[2] * cols[2][j]
                        + a[3] * cols[3][j]
                        + a[4] * cols[4][j]
                        + a[5] * cols[5][j]
                        + a[6] * cols[6][j]
                        + a[7] * cols[7][j];
                    let nr = norms[j];
                    if nr > 1e-12 {
                        let sim = dot * inv_nv / nr;
                        if sim > max_sim {
                            max_sim = sim;
                        }
                    }
                    j += 1;
                }
                (max_sim + 1.0) / 2.0
            })
            .collect()
    });

    let out = PyArray1::from_vec_bound(py, res);
    Ok(out.unbind())
}

/// Compute E8 alignment with pre-normalized roots (unit norm). Faster: skips root norms.
#[pyfunction]
fn compute_e8_alignment_batch_numpy_prenorm_py<'py>(
    py: Python<'py>,
    vectors: PyReadonlyArray2<'py, f64>,
    roots_unit: PyReadonlyArray2<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let v = vectors.as_array();
    let r = roots_unit.as_array();
    if v.ncols() != r.ncols() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "vectors and roots must have same feature dimension",
        ));
    }
    let n = v.nrows();
    let m = r.nrows();
    if n == 0 || m == 0 {
        let out = PyArray1::<f64>::zeros_bound(py, 0, false);
        return Ok(out.unbind());
    }
    // Pre-transpose and cache root columns for reuse across calls
    let cols_arc = get_root_cols_cached(&r);
    let res: Vec<f64> = py.allow_threads(|| {
        let dcols = r.ncols();
        let cols = cols_arc; // move Arc into closure (cloned by Rayon as needed)
        (0..n)
            .into_par_iter()
            .map(|i| {
                let vec_i = v.row(i);
                let a = unsafe { std::slice::from_raw_parts(vec_i.as_ptr(), dcols) };
                let norm_v = norm8(a);
                if norm_v == 0.0 {
                    return 0.0;
                }
                let inv_nv = 1.0 / norm_v;
                let mut max_sim = -1.0f64;
                let mut j = 0;
                #[cfg(all(target_arch = "x86_64"))]
                unsafe {
                    if is_x86_feature_detected!("avx2") {
                        use core::arch::x86_64::*;
                        let a0 = _mm256_set1_pd(a[0]);
                        let a1 = _mm256_set1_pd(a[1]);
                        let a2 = _mm256_set1_pd(a[2]);
                        let a3 = _mm256_set1_pd(a[3]);
                        let a4 = _mm256_set1_pd(a[4]);
                        let a5 = _mm256_set1_pd(a[5]);
                        let a6 = _mm256_set1_pd(a[6]);
                        let a7 = _mm256_set1_pd(a[7]);
                        let inv = _mm256_set1_pd(inv_nv);
                        while j + 4 <= m {
                            let c0 = _mm256_loadu_pd(cols[0].as_ptr().add(j));
                            let c1 = _mm256_loadu_pd(cols[1].as_ptr().add(j));
                            let c2 = _mm256_loadu_pd(cols[2].as_ptr().add(j));
                            let c3 = _mm256_loadu_pd(cols[3].as_ptr().add(j));
                            let c4 = _mm256_loadu_pd(cols[4].as_ptr().add(j));
                            let c5 = _mm256_loadu_pd(cols[5].as_ptr().add(j));
                            let c6 = _mm256_loadu_pd(cols[6].as_ptr().add(j));
                            let c7 = _mm256_loadu_pd(cols[7].as_ptr().add(j));
                            let mut acc = _mm256_mul_pd(c0, a0);
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c1, a1));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c2, a2));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c3, a3));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c4, a4));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c5, a5));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c6, a6));
                            acc = _mm256_add_pd(acc, _mm256_mul_pd(c7, a7));
                            let accn = _mm256_mul_pd(acc, inv);
                            let mut tmp = [0.0f64; 4];
                            _mm256_storeu_pd(tmp.as_mut_ptr(), accn);
                            for &val in &tmp {
                                if val > max_sim {
                                    max_sim = val;
                                }
                            }
                            j += 4;
                        }
                    }
                }
                // Remainder / non-AVX2 path
                while j < m {
                    let dot = a[0] * cols[0][j]
                        + a[1] * cols[1][j]
                        + a[2] * cols[2][j]
                        + a[3] * cols[3][j]
                        + a[4] * cols[4][j]
                        + a[5] * cols[5][j]
                        + a[6] * cols[6][j]
                        + a[7] * cols[7][j];
                    let sim = dot * inv_nv;
                    if sim > max_sim {
                        max_sim = sim;
                    }
                    j += 1;
                }
                (max_sim + 1.0) / 2.0
            })
            .collect()
    });
    Ok(PyArray1::from_vec_bound(py, res).unbind())
}

// --- Bell test kernels (QA correlator) -------------------------------------------------------

#[inline]
fn qa_correlator(n: i64, s: i64, t: i64) -> f64 {
    // E_N(s,t) = cos(2π(s - t)/N)
    let n_f = n as f64;
    let delta = ((s - t) as f64) * std::f64::consts::TAU / n_f;
    delta.cos()
}

/// CHSH kernel: S = E(a0,b0) + E(a0,b1) + E(a1,b0) - E(a1,b1)
#[pyfunction]
fn compute_chsh_qa(n: i64, a0: i64, a1: i64, b0: i64, b1: i64) -> PyResult<f64> {
    if n <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n must be > 0"));
    }
    let e00 = qa_correlator(n, a0, b0);
    let e01 = qa_correlator(n, a0, b1);
    let e10 = qa_correlator(n, a1, b0);
    let e11 = qa_correlator(n, a1, b1);
    Ok(e00 + e01 + e10 - e11)
}

/// I3322 kernel (one common form):
/// I3322 = E11 + E12 + E21 + E22 - E13 - E23 - E31 - E32 - 2E33 - (A1 + A2 + B1 + B2)
/// where A_i, B_j are single-party expectations. We approximate A_i = cos(2π a_i / N), B_j = cos(2π b_j / N).
#[pyfunction]
fn compute_i3322_qa(n: i64, a1: i64, a2: i64, a3: i64, b1: i64, b2: i64, b3: i64) -> PyResult<f64> {
    if n <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n must be > 0"));
    }
    let e11 = qa_correlator(n, a1, b1);
    let e12 = qa_correlator(n, a1, b2);
    let e13 = qa_correlator(n, a1, b3);
    let e21 = qa_correlator(n, a2, b1);
    let e22 = qa_correlator(n, a2, b2);
    let e23 = qa_correlator(n, a2, b3);
    let e31 = qa_correlator(n, a3, b1);
    let e32 = qa_correlator(n, a3, b2);
    let e33 = qa_correlator(n, a3, b3);
    // Single-party expectations (QA proxy)
    let a1v = qa_correlator(n, a1, 0);
    let a2v = qa_correlator(n, a2, 0);
    let b1v = qa_correlator(n, b1, 0);
    let b2v = qa_correlator(n, b2, 0);
    let val = e11 + e12 + e21 + e22 - e13 - e23 - e31 - e32 - 2.0 * e33 - (a1v + a2v + b1v + b2v);
    Ok(val)
}

#[inline]
fn avg_abs_dot3(vecs: &[[f64; 3]]) -> f64 {
    if vecs.len() < 2 {
        return 0.0;
    }
    let mut acc = 0.0f64;
    let mut cnt = 0usize;
    for i in 0..vecs.len() {
        for j in (i + 1)..vecs.len() {
            let u = vecs[i];
            let v = vecs[j];
            let dot = u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
            acc += dot.abs();
            cnt += 1;
        }
    }
    if cnt == 0 {
        0.0
    } else {
        acc / (cnt as f64)
    }
}

fn unit(v: [f64; 3]) -> [f64; 3] {
    let n = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]).sqrt();
    if n == 0.0 {
        return [0.0, 0.0, 0.0];
    }
    [v[0] / n, v[1] / n, v[2] / n]
}

fn avg_abs_axb(a: &[[f64; 3]], b: &[[f64; 3]]) -> f64 {
    let mut acc = 0.0f64;
    let mut cnt = 0usize;
    for u in a.iter() {
        for v in b.iter() {
            let dot = u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
            acc += dot.abs();
            cnt += 1;
        }
    }
    if cnt == 0 {
        0.0
    } else {
        acc / (cnt as f64)
    }
}

fn icosahedron_vertices() -> Vec<[f64; 3]> {
    let phi = (1.0 + 5.0_f64.sqrt()) * 0.5;
    let base = vec![
        [0.0, 1.0, phi],
        [0.0, -1.0, phi],
        [0.0, 1.0, -phi],
        [0.0, -1.0, -phi],
        [1.0, phi, 0.0],
        [-1.0, phi, 0.0],
        [1.0, -phi, 0.0],
        [-1.0, -phi, 0.0],
        [phi, 0.0, 1.0],
        [phi, 0.0, -1.0],
        [-phi, 0.0, 1.0],
        [-phi, 0.0, -1.0],
    ];
    let mut vecs: Vec<[f64; 3]> = Vec::with_capacity(12);
    for v in base {
        vecs.push(unit(v));
    }
    vecs
}

fn dodecahedron_vertices() -> Vec<[f64; 3]> {
    let phi = (1.0 + 5.0_f64.sqrt()) * 0.5;
    let inv_phi = 1.0 / phi;
    let mut vecs: Vec<[f64; 3]> = Vec::with_capacity(20);
    // 8 cube corners
    for &sx in &[-1.0, 1.0] {
        for &sy in &[-1.0, 1.0] {
            for &sz in &[-1.0, 1.0] {
                vecs.push(unit([sx, sy, sz]));
            }
        }
    }
    // 12 additional vertices: permutations of (0, ±1/phi, ±phi)
    let mut add = |x: f64, y: f64, z: f64| {
        vecs.push(unit([x, y, z]));
    };
    for &s1 in &[-1.0, 1.0] {
        for &s2 in &[-1.0, 1.0] {
            add(0.0, s1 * inv_phi, s2 * phi);
            add(s1 * inv_phi, s2 * phi, 0.0);
            add(s1 * phi, 0.0, s2 * inv_phi);
        }
    }
    vecs
}

fn hemisplit(vecs: &[[f64; 3]]) -> (Vec<[f64; 3]>, Vec<[f64; 3]>) {
    let mut a = Vec::new();
    let mut b = Vec::new();
    for &v in vecs.iter() {
        if v[2] >= 0.0 {
            a.push(v);
        } else {
            b.push(v);
        }
    }
    if a.is_empty() || b.is_empty() {
        // fallback split by y
        a.clear();
        b.clear();
        for &v in vecs.iter() {
            if v[1] >= 0.0 {
                a.push(v);
            } else {
                b.push(v);
            }
        }
    }
    (a, b)
}

fn axis_normals() -> Vec<[f64; 3]> {
    vec![
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, -1.0],
    ]
}

fn best_bipartition(vecs: &[[f64; 3]], candidates: &[[f64; 3]]) -> f64 {
    let mut best = 0.0f64;
    for n in candidates.iter() {
        let mut a: Vec<[f64; 3]> = Vec::new();
        let mut b: Vec<[f64; 3]> = Vec::new();
        for &v in vecs.iter() {
            let dot = v[0] * n[0] + v[1] * n[1] + v[2] * n[2];
            if dot >= 0.0 {
                a.push(v);
            } else {
                b.push(v);
            }
        }
        if a.is_empty() || b.is_empty() {
            continue;
        }
        let score = avg_abs_axb(&a, &b);
        if score > best {
            best = score;
        }
    }
    best
}

/// Octahedron Bell kernel: use 6 axis directions ±x,±y,±z; returns avg |cos(theta)|
#[pyfunction]
fn bell_octahedron_qa(n: i64) -> PyResult<f64> {
    if n <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n must be > 0"));
    }
    let vecs: [[f64; 3]; 6] = [
        [1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, -1.0],
    ];
    // Face normals of octahedron = cube corners; use bipartition A (z>=0), B (z<0)
    let cube_corners = vec![
        unit([1.0, 1.0, 1.0]),
        unit([-1.0, 1.0, 1.0]),
        unit([1.0, -1.0, 1.0]),
        unit([-1.0, -1.0, 1.0]),
        unit([1.0, 1.0, -1.0]),
        unit([-1.0, 1.0, -1.0]),
        unit([1.0, -1.0, -1.0]),
        unit([-1.0, -1.0, -1.0]),
    ];
    let mut cand = axis_normals();
    cand.extend_from_slice(&cube_corners);
    Ok(best_bipartition(&cube_corners, &cand))
}

/// Icosahedron Bell kernel: 12 vertex directions of an icosahedron, normalized
#[pyfunction]
fn bell_icosahedron_qa(n: i64) -> PyResult<f64> {
    if n <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n must be > 0"));
    }
    // Use icosahedron face normals = dodecahedron vertices for bipartite A/B
    let faces = dodecahedron_vertices();
    let mut cand = axis_normals();
    cand.extend_from_slice(&faces);
    let verts = icosahedron_vertices();
    cand.extend_from_slice(&verts);
    Ok(best_bipartition(&faces, &cand))
}

/// Dodecahedron Bell kernel: 20 vertex directions of a dodecahedron, normalized
#[pyfunction]
fn bell_dodecahedron_qa(n: i64) -> PyResult<f64> {
    if n <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n must be > 0"));
    }
    // Use dodecahedron face normals = icosahedron vertices for bipartite A/B
    let faces = icosahedron_vertices();
    let mut cand = axis_normals();
    cand.extend_from_slice(&faces);
    let verts = dodecahedron_vertices();
    cand.extend_from_slice(&verts);
    Ok(best_bipartition(&faces, &cand))
}
/// mod24 over float64 array (positive wrap like fmod behavior)
#[pyfunction]
fn mod24_batch_numpy_py<'py>(
    py: Python<'py>,
    x: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let arr = x.as_slice()?;
    let out: Vec<f64> = arr
        .iter()
        .map(|&v| {
            let m = v % 24.0;
            if m < 0.0 {
                m + 24.0
            } else {
                m
            }
        })
        .collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}

/// digital root over float64 array treated as non-negative integers via truncation
#[pyfunction]
fn digital_root_batch_numpy_py<'py>(
    py: Python<'py>,
    x: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyArray1<i64>>> {
    let arr = x.as_slice()?;
    let out: Vec<i64> = arr
        .iter()
        .map(|&v| {
            let n = if v < 0.0 { 0 } else { v as i64 };
            crate::qa_core::digital_root(n)
        })
        .collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}

/// closure residual: sqrt((b+e-d)^2 + (e+d-a)^2) per element
#[pyfunction]
fn closure_residual_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let b = b.as_slice()?;
    let e = e.as_slice()?;
    let d = d.as_slice()?;
    let a = a.as_slice()?;
    let len = b.len();
    if e.len() != len || d.len() != len || a.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "All inputs must have same length",
        ));
    }
    let out: Vec<f64> = (0..len)
        .into_par_iter()
        .map(|i| {
            let r1 = b[i] + e[i] - d[i];
            let r2 = e[i] + d[i] - a[i];
            (r1 * r1 + r2 * r2).sqrt()
        })
        .collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}

/// inner ellipse residual: a^2 - (d^2 + 2de + e^2)
#[pyfunction]
fn inner_ellipse_residual_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let e = e.as_slice()?;
    let d = d.as_slice()?;
    let a = a.as_slice()?;
    let len = e.len();
    if d.len() != len || a.len() != len || b.as_slice()?.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "All inputs must have same length",
        ));
    }
    let out: Vec<f64> = (0..len)
        .into_par_iter()
        .map(|i| {
            let lhs = a[i] * a[i];
            let rhs = d[i] * d[i] + 2.0 * d[i] * e[i] + e[i] * e[i];
            lhs - rhs
        })
        .collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}

/// triangle residual: |C^2 + F^2 - G^2| with C=2ed, F=ba, G=e^2 + d^2
#[pyfunction]
fn triangle_residual_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
) -> PyResult<Py<PyArray1<f64>>> {
    let b = b.as_slice()?;
    let e = e.as_slice()?;
    let d = d.as_slice()?;
    let a = a.as_slice()?;
    let len = b.len();
    if e.len() != len || d.len() != len || a.len() != len {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "All inputs must have same length",
        ));
    }
    let out: Vec<f64> = (0..len)
        .into_par_iter()
        .map(|i| {
            let c = 2.0 * e[i] * d[i];
            let f = b[i] * a[i];
            let g = e[i] * e[i] + d[i] * d[i];
            (c * c + f * f - g * g).abs()
        })
        .collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}
/// QE scorer: computes composite QE score with lightweight features.
/// Fixed base weights: closure=1.0, dr_bonus=0.5, mod24_bonus=0.5, w_est=0.25, z_est=0.25
/// Tunable weights passed as args: w_curv, w_phi, w_phi_eb, w_family, w_ideal
#[pyfunction]
fn qe_score_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
    w_curv: f64,
    w_phi: f64,
    w_phi_eb: f64,
    w_family: f64,
    w_ideal: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    let b = b.as_slice()?;
    let e = e.as_slice()?;
    let d = d.as_slice()?;
    let a = a.as_slice()?;
    let n = b.len();
    if e.len() != n || d.len() != n || a.len() != n {
        return Err(pyo3::exceptions::PyValueError::new_err("All inputs must have same length"));
    }
    let eps = 1e-12f64;
    let phi = (1.0 + 5.0_f64.sqrt()) * 0.5;
    let ideal4 = {
        let mut v = [1.0f64, 1.0, 2.0, 3.0];
        let nrm = (v[0]*v[0] + v[1]*v[1] + v[2]*v[2] + v[3]*v[3]).sqrt() + eps;
        v[0]/=nrm; v[1]/=nrm; v[2]/=nrm; v[3]/=nrm; v
    };
    let mut closure_v = vec![0.0f64; n];
    let mut dr_bonus = vec![0.0f64; n];
    let mut mod24_bonus = vec![0.0f64; n];
    let mut w_est = vec![0.0f64; n];
    let mut z_est = vec![0.0f64; n];
    let mut curv_v = vec![0.0f64; n];
    let mut phi_err = vec![0.0f64; n];
    let mut phi_eb_err = vec![0.0f64; n];
    let mut family_v = vec![0.0f64; n];
    let mut ideal_v = vec![0.0f64; n];
    let mut sum_w = 0.0f64; let mut sum_z = 0.0f64;
    for i in 0..n {
        let r1 = b[i] + e[i] - d[i];
        let r2 = e[i] + d[i] - a[i];
        closure_v[i] = - (r1.abs() + r2.abs());
        let ai = if a[i] < 0.0 { 0 } else { a[i] as i64 };
        let dr = crate::qa_core::digital_root(ai);
        dr_bonus[i] = if dr == 1 || dr == 3 || dr == 9 { 1.0 } else { 0.0 };
        let mut md = d[i] % 24.0; if md < 0.0 { md += 24.0; }
        let md_i = md as i64;
        mod24_bonus[i] = match md_i { 1|5|7|11 => 1.0, _ => 0.0 };
        w_est[i] = d[i] * (e[i] + a[i]);
        z_est[i] = e[i]*e[i] + d[i]*a[i];
        sum_w += w_est[i]; sum_z += z_est[i];
    }
    let mu_w = sum_w / (n as f64);
    let mu_z = sum_z / (n as f64);
    for i in 0..n {
        if w_curv != 0.0 {
            let y_est = a[i]*a[i] - d[i]*d[i];
            let c_est = 2.0*e[i]*d[i];
            let f_est = b[i]*a[i] + eps;
            let curv_ratio = (y_est.abs()) / (z_est[i].abs() + eps);
            let curv_cf = (c_est / f_est).abs();
            curv_v[i] = curv_ratio.ln_1p() + curv_cf.ln_1p();
        }
        if w_phi != 0.0 || w_phi_eb != 0.0 || w_family != 0.0 {
            let denom_d = d[i].abs() + eps;
            let denom_b = b[i].abs() + eps;
            phi_err[i] = -((a[i] / denom_d) - phi).abs();
            phi_eb_err[i] = -((e[i] / denom_b) - phi).abs();
            family_v[i] = if phi_err[i] > phi_eb_err[i] { phi_err[i] } else { phi_eb_err[i] };
        }
        if w_ideal != 0.0 {
            let nrm = (b[i]*b[i] + e[i]*e[i] + d[i]*d[i] + a[i]*a[i]).sqrt() + eps;
            let bu = b[i] / nrm; let eu = e[i] / nrm; let du = d[i] / nrm; let au = a[i] / nrm;
            #[cfg(feature = "portable_simd")]
            let dot = {
                let v = core::simd::Simd::<f64, 4>::from_array([bu, eu, du, au]);
                let w = core::simd::Simd::<f64, 4>::from_array(ideal4);
                (v * w).reduce_sum()
            };
            #[cfg(not(feature = "portable_simd"))]
            let dot = bu*ideal4[0] + eu*ideal4[1] + du*ideal4[2] + au*ideal4[3];
            ideal_v[i] = dot.abs();
        }
    }
    let mut out = vec![0.0f64; n];
    for i in 0..n {
        let mut s = 0.0f64;
        s += closure_v[i];
        s += 0.5 * dr_bonus[i];
        s += 0.5 * mod24_bonus[i];
        s += 0.25 * (w_est[i] - mu_w);
        s += 0.25 * (z_est[i] - mu_z);
        if w_curv != 0.0 { s += w_curv * curv_v[i]; }
        if w_phi_eb != 0.0 { s += w_phi_eb * phi_eb_err[i]; }
        if w_phi != 0.0 { s += w_phi * phi_err[i]; }
        if w_family != 0.0 { s += w_family * family_v[i]; }
        if w_ideal != 0.0 { s += w_ideal * ideal_v[i]; }
        out[i] = s;
    }
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}

/// QE scorer variant using precomputed invariants W,Z,Y,C,F to avoid recompute.
#[pyfunction]
fn qe_score_with_inv_batch_numpy_py<'py>(
    py: Python<'py>,
    b: PyReadonlyArray1<'py, f64>,
    e: PyReadonlyArray1<'py, f64>,
    d: PyReadonlyArray1<'py, f64>,
    a: PyReadonlyArray1<'py, f64>,
    w_in: PyReadonlyArray1<'py, f64>,
    z_in: PyReadonlyArray1<'py, f64>,
    y_in: PyReadonlyArray1<'py, f64>,
    c_in: PyReadonlyArray1<'py, f64>,
    f_in: PyReadonlyArray1<'py, f64>,
    w_curv: f64, w_phi: f64, w_phi_eb: f64, w_family: f64, w_ideal: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    let b = b.as_slice()?; let e = e.as_slice()?; let d = d.as_slice()?; let a = a.as_slice()?;
    let wv = w_in.as_slice()?; let zv = z_in.as_slice()?; let yv = y_in.as_slice()?;
    let cv = c_in.as_slice()?; let fv = f_in.as_slice()?;
    let n = b.len();
    for arr in [&e, &d, &a, &wv, &zv, &yv, &cv, &fv] { if arr.len() != n { return Err(pyo3::exceptions::PyValueError::new_err("All inputs must have same length")); } }
    let eps = 1e-12f64;
    let phi = (1.0 + 5.0_f64.sqrt()) * 0.5;
    let ideal4 = {
        let mut v = [1.0f64, 1.0, 2.0, 3.0];
        let nrm = (v[0]*v[0] + v[1]*v[1] + v[2]*v[2] + v[3]*v[3]).sqrt() + eps;
        v[0]/=nrm; v[1]/=nrm; v[2]/=nrm; v[3]/=nrm; v
    };
    let mu_w: f64 = wv.iter().sum::<f64>() / (n as f64);
    let mu_z: f64 = zv.iter().sum::<f64>() / (n as f64);
    let out: Vec<f64> = (0..n).into_par_iter().map(|i| {
        let mut s = 0.0f64;
        // closure via b,e,d,a
        let r1 = b[i] + e[i] - d[i]; let r2 = e[i] + d[i] - a[i];
        s += - (r1.abs() + r2.abs());
        // digital-root bonus
        let ai = if a[i] < 0.0 { 0 } else { a[i] as i64 };
        let dr = crate::qa_core::digital_root(ai); if matches!(dr,1|3|9) { s += 0.5; }
        // mod24 bonus
        let mut md = d[i] % 24.0; if md < 0.0 { md += 24.0; }
        if matches!(md as i64, 1|5|7|11) { s += 0.5; }
        // mean-centered W,Z from provided arrays
        s += 0.25 * (wv[i] - mu_w); s += 0.25 * (zv[i] - mu_z);
        // curvature from Y,C,F
        if w_curv != 0.0 {
            let curv_ratio = (yv[i].abs()) / (zv[i].abs() + eps);
            let curv_cf = (cv[i] / (fv[i] + eps)).abs();
            s += w_curv * (curv_ratio.ln_1p() + curv_cf.ln_1p());
        }
        // φ and family
        if w_phi != 0.0 || w_phi_eb != 0.0 || w_family != 0.0 {
            let denom_d = d[i].abs() + eps; let denom_b = b[i].abs() + eps;
            let phi_e = -((a[i] / denom_d) - phi).abs();
            let phi_eb_e = -((e[i] / denom_b) - phi).abs();
            if w_phi_eb != 0.0 { s += w_phi_eb * phi_eb_e; }
            if w_phi != 0.0 { s += w_phi * phi_e; }
            if w_family != 0.0 { s += w_family * if phi_e > phi_eb_e { phi_e } else { phi_eb_e }; }
        }
        // ideal cosine
        if w_ideal != 0.0 {
            let nrm = (b[i]*b[i] + e[i]*e[i] + d[i]*d[i] + a[i]*a[i]).sqrt() + eps;
            let bu = b[i]/nrm; let eu = e[i]/nrm; let du = d[i]/nrm; let au = a[i]/nrm;
            #[cfg(feature = "portable_simd")]
            let dot = { let v = core::simd::Simd::<f64,4>::from_array([bu,eu,du,au]); let w = core::simd::Simd::<f64,4>::from_array(ideal4); (v*w).reduce_sum() };
            #[cfg(not(feature = "portable_simd"))]
            let dot = bu*ideal4[0] + eu*ideal4[1] + du*ideal4[2] + au*ideal4[3];
            s += w_ideal * dot.abs();
        }
        s
    }).collect();
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}
/// Harmonic loss / index (simple batch)
#[pyfunction]
fn harmonic_index_batch_numpy_py<'py>(
    py: Python<'py>,
    e8: PyReadonlyArray1<'py, f64>,
    loss: PyReadonlyArray1<'py, f64>,
    k: f64,
) -> PyResult<Py<PyArray1<f64>>> {
    let e8 = e8.as_array();
    let loss = loss.as_array();
    let n = e8.len();
    let mut out = Vec::with_capacity(n);
    for i in 0..n {
        out.push(e8[i] * (-(k * loss[i])).exp());
    }
    Ok(PyArray1::from_vec_bound(py, out).unbind())
}
/// Streaming buffers (stubs)
#[pyfunction]
fn stream_buffers_init_py(size: usize) -> PyResult<bool> {
    Ok(false)
}
#[pyfunction]
fn stream_buffers_release_py() -> PyResult<bool> {
    Ok(true)
}
