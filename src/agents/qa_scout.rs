use rand::RngCore;

use crate::swarm::bee::{QualityEstimate, ScoutBee, Task, TaskOption};

#[derive(Debug, Clone)]
pub struct QAScoutBee { id: u128 }

impl Default for QAScoutBee { fn default() -> Self { let mut r=rand::thread_rng(); Self { id: (r.next_u64() as u128) ^ ((r.next_u64() as u128) << 64) } } }

impl ScoutBee for QAScoutBee {
    fn id(&self) -> u128 { self.id }

    fn scout(&self, task: &Task) -> Result<QualityEstimate, String> {
        let q = 0.5; // placeholder constant quality
        Ok(QualityEstimate {
            task_id: task.id.clone(),
            option: TaskOption::Json(serde_json::json!({"note": "qa_scout placeholder"})),
            quality: q,
            artifacts: vec![],
        })
    }
}
