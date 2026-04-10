use ndarray::Array1;
use std::path::PathBuf;

use crate::qa_core::QABundle;
use crate::swarm::bee::Task;
use crate::tools::{Tool, ToolOutput};

#[derive(Debug, Clone)]
pub struct QATool { pub base_dir: PathBuf }

impl QATool { pub fn new<P: Into<PathBuf>>(base_dir: Option<P>) -> Self {
    let base = base_dir.map(|p| p.into()).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    Self { base_dir: base }
} }

impl Tool for QATool {
    fn name(&self) -> &'static str { "qa_tool" }
    fn cost_estimate(&self, _task: &Task) -> f64 { 1.0 }

    fn invoke(&self, task: &Task) -> Result<ToolOutput, String> {
        // Simple invariant sweep artifact for demonstration: sample 24 tuples and export invariants
        let mut rows = Vec::new();
        for b in 1..=6 { for e in 1..=4 {
            let bundle = QABundle::new(b as f64, e as f64);
            let v: Array1<f64> = bundle.e8_projection();
            rows.push(serde_json::json!({
                "b": bundle.tuple.b, "e": bundle.tuple.e, "d": bundle.tuple.d, "a": bundle.tuple.a,
                "J": bundle.j, "K": bundle.k, "X": bundle.x, "W": bundle.w,
                "e8_proj": v.to_vec(),
            }));
        }}
        let out_dir = self.base_dir.join("artifacts").join("evals");
        std::fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
        let path = out_dir.join(format!("qa_orchestrator_{}.json", task.id));
        let payload = serde_json::json!({"task_id": task.id, "rows": rows, "count": rows.len()});
        std::fs::write(&path, serde_json::to_string_pretty(&payload).unwrap()).map_err(|e| e.to_string())?;
        Ok(ToolOutput { quality: 0.5, artifacts: vec![path], detail: serde_json::json!({"count": rows.len()}) })
    }
}

