use std::path::PathBuf;

use crate::swarm::bee::Task;

#[derive(Debug, Clone)]
pub struct ToolOutput {
    pub quality: f64,
    pub artifacts: Vec<PathBuf>,
    pub detail: serde_json::Value,
}

pub trait Tool: Send + Sync {
    fn name(&self) -> &'static str;
    /// Rough unitless cost estimate (relative). Lower is cheaper.
    fn cost_estimate(&self, _task: &Task) -> f64 { 1.0 }
    /// Invoke the tool for a task and produce an output with artifacts.
    fn invoke(&self, task: &Task) -> Result<ToolOutput, String>;
}

pub mod e8_tool;
pub mod qa_tool;

