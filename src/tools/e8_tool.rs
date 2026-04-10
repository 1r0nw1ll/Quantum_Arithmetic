use ndarray::{Array2, Axis};
use serde::Serialize;
use std::path::{Path, PathBuf};

use crate::swarm::bee::Task;
use crate::tools::{Tool, ToolOutput};

fn load_e8_roots(path: &Path) -> Result<Array2<f64>, String> {
    // Minimal .npy reader for little-endian float64, shape (M, 8)
    let bytes = std::fs::read(path)
        .map_err(|e| format!("failed to read {:?}: {}", path, e))?;
    if bytes.len() < 16 { return Err("file too small".into()); }
    if &bytes[0..6] != b"\x93NUMPY" { return Err("invalid npy magic".into()); }
    let major = bytes[6];
    let _minor = bytes[7];
    let (hdr_len, offset) = if major == 1 { let l = u16::from_le_bytes([bytes[8], bytes[9]]) as usize; (l, 10) } else { let l = u32::from_le_bytes([bytes[8], bytes[9], bytes[10], bytes[11]]) as usize; (l, 12) };
    if bytes.len() < offset + hdr_len { return Err("truncated header".into()); }
    let hdr = std::str::from_utf8(&bytes[offset..offset + hdr_len]).map_err(|e| format!("header utf8 error: {}", e))?;
    if !(hdr.contains("'descr': '<f8'") || hdr.contains("'descr': 'f8'")) { return Err("unsupported dtype (expected <f8)".into()); }
    let shape_start = hdr.find('(').ok_or_else(|| "no shape start".to_string())?;
    let shape_end = hdr[shape_start..].find(')').ok_or_else(|| "no shape end".to_string())? + shape_start;
    let inside = &hdr[shape_start + 1..shape_end];
    let dims: Vec<usize> = inside.split(',').filter_map(|s| { let t = s.trim(); if t.is_empty() { None } else { t.parse::<usize>().ok() } }).collect();
    if dims.len() != 2 { return Err("expected 2D array in roots file".into()); }
    let (m, n) = (dims[0], dims[1]);
    if n != 8 { return Err(format!("expected 8 columns, got {}", n)); }
    let data_off = offset + hdr_len;
    let expected = m * n * 8;
    if bytes.len() < data_off + expected { return Err("truncated data".into()); }
    let mut out = Array2::<f64>::zeros((m, n));
    let mut idx = 0;
    for i in 0..m {
        for j in 0..n {
            let b = &bytes[data_off + idx..data_off + idx + 8];
            out[(i, j)] = f64::from_le_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]]);
            idx += 8;
        }
    }
    Ok(out)
}

fn qa_mod24(v: i32) -> i32 { ((v - 1).rem_euclid(24)) + 1 }

fn project_to_8d(b: i32, e: i32, d: i32, a: i32) -> [f64; 8] {
    [b as f64, e as f64, d as f64, a as f64, 0.0, 0.0, 0.0, 0.0]
}

fn unit8(v: [f64; 8]) -> [f64; 8] {
    let mut n = 0.0f64; for i in 0..8 { n += v[i] * v[i]; }
    if n == 0.0 { return v; }
    let inv = 1.0 / n.sqrt();
    let mut u = [0.0f64; 8]; for i in 0..8 { u[i] = v[i] * inv; }
    u
}

fn max_alignment(v: &[f64; 8], roots: &Array2<f64>) -> f64 {
    let mut best = 0.0f64;
    for row in roots.axis_iter(Axis(0)) {
        let r = row.as_slice().unwrap();
        let mut dot = 0.0f64; for i in 0..8 { dot += v[i] * r[i]; }
        let ad = dot.abs(); if ad > best { best = ad; }
    }
    best
}

#[derive(Debug, Clone)]
pub struct E8Tool { pub base_dir: PathBuf, pub roots: Array2<f64> }

impl E8Tool {
    pub fn new<P: Into<PathBuf>>(base_dir: Option<P>) -> Result<Self, String> {
        let base = base_dir.map(|p| p.into()).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")));
        let rp = base.join("data").join("e8_roots_unit.npy");
        let roots = load_e8_roots(&rp)?;
        Ok(Self { base_dir: base, roots })
    }
}

#[derive(Serialize)]
struct Artifact<'a> {
    task_id: &'a str,
    total_tuples: usize,
    results: Vec<serde_json::Value>,
    statistics: serde_json::Value,
}

impl Tool for E8Tool {
    fn name(&self) -> &'static str { "e8_tool" }
    fn cost_estimate(&self, _task: &Task) -> f64 { 2.0 } // relative cost: heavier than QA tool

    fn invoke(&self, task: &Task) -> Result<ToolOutput, String> {
        let mut results = Vec::with_capacity(24*24);
        let mut aligns = Vec::with_capacity(24*24);
        for b in 1..=24 { for e in 1..=24 {
            let d = qa_mod24(b + e); let a = qa_mod24(e + d);
            let u = unit8(project_to_8d(b, e, d, a));
            let m = max_alignment(&u, &self.roots);
            aligns.push(m);
            results.push(serde_json::json!({"b":b,"e":e,"d":d,"a":a,"e8_alignment":m}));
        }}
        let n = aligns.len() as f64;
        let mean = aligns.iter().copied().sum::<f64>() / n;
        let max = aligns.iter().copied().fold(0.0/0.0, f64::max);
        let min = aligns.iter().copied().fold(1.0/0.0, f64::min);
        let std = { let mu = mean; (aligns.iter().map(|&x| (x-mu)*(x-mu)).sum::<f64>()/n).sqrt() };

        let art = Artifact { task_id: &task.id, total_tuples: aligns.len(), results, statistics: serde_json::json!({
            "mean_alignment": mean, "max_alignment": max, "min_alignment": min, "std_alignment": std
        }) };
        let out_dir = self.base_dir.join("artifacts").join("evals");
        std::fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
        let path = out_dir.join(format!("e8_orchestrator_{}.json", task.id));
        let s = serde_json::to_string_pretty(&art).map_err(|e| e.to_string())?;
        std::fs::write(&path, s).map_err(|e| e.to_string())?;

        Ok(ToolOutput { quality: mean, artifacts: vec![path], detail: serde_json::json!({"tuples": 576}) })
    }
}

