use rand::RngCore;
use std::path::PathBuf;
use std::sync::Arc;

use crate::swarm::bee::{QualityEstimate, ScoutBee, Task, TaskId, TaskOption};
use crate::tools::{Tool, ToolOutput};
use crate::tools::e8_tool::E8Tool;
use crate::tools::qa_tool::QATool;

#[derive(Debug, Clone)]
pub struct OrchestratorBee {
    id: u128,
    base_dir: PathBuf,
    e8: Arc<E8Tool>,
    qa: Arc<QATool>,
}

impl OrchestratorBee {
    pub fn new<P: Into<PathBuf>>(base_dir: Option<P>) -> Result<Self, String> {
        let base = base_dir.map(|p| p.into()).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")));
        let e8 = Arc::new(E8Tool::new::<PathBuf>(Some(base.clone()))?);
        let qa = Arc::new(QATool::new::<PathBuf>(Some(base.clone())));
        let mut r = rand::thread_rng();
        let id = (r.next_u64() as u128) ^ ((r.next_u64() as u128) << 64);
        Ok(Self { id, base_dir: base, e8, qa })
    }

    fn pick_pipeline<'a>(&'a self, task: &Task) -> Vec<&'a dyn Tool> {
        let title = task.title.to_lowercase();
        if title.contains("e8") || title.contains("alignment") || title.contains("benchmark") {
            vec![self.e8.as_ref()]
        } else if title.contains("qa ") || title.contains("invariant") || title.contains("tuple") {
            vec![self.qa.as_ref()]
        } else {
            // Heuristic: choose cheapest by cost estimate
            let ce_e8 = self.e8.cost_estimate(task);
            let ce_qa = self.qa.cost_estimate(task);
            if ce_qa <= ce_e8 { vec![self.qa.as_ref()] } else { vec![self.e8.as_ref()] }
        }
    }

    fn run_pipeline(&self, task: &Task, steps: Vec<&dyn Tool>) -> Result<ToolOutput, String> {
        // MVP: single-stage pipeline
        if let Some(tool) = steps.get(0) {
            tool.invoke(task)
        } else {
            Err("empty pipeline".into())
        }
    }
}

impl ScoutBee for OrchestratorBee {
    fn id(&self) -> u128 { self.id }

    fn scout(&self, task: &Task) -> Result<QualityEstimate, String> {
        let plan = self.pick_pipeline(task);
        let out = self.run_pipeline(task, plan)?;

        // Map to TaskOption based on presence of E8 keys
        let option = if out.detail.get("tuples").is_some() {
            TaskOption::E8Benchmark { artifact: out.artifacts.get(0).cloned(), mean_alignment: out.quality }
        } else {
            TaskOption::Json(serde_json::json!({ "orchestrator": true, "quality": out.quality }))
        };

        Ok(QualityEstimate {
            task_id: task.id.clone(),
            option,
            quality: out.quality,
            artifacts: out.artifacts,
        })
    }
}

