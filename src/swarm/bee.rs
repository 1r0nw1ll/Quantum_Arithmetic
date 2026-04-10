use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::time::Duration;

use crate::swarm::broadcast::BroadcastBus;

pub type TaskId = String;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: TaskId,
    pub title: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", content = "data")]
pub enum TaskOption {
    /// Placeholder option: E8 benchmark result reference/path
    E8Benchmark { artifact: Option<PathBuf>, mean_alignment: f64 },
    /// Generic JSON output for other scouts
    Json(serde_json::Value),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QualityEstimate {
    pub task_id: TaskId,
    pub option: TaskOption,
    pub quality: f64,        // [0, 1]
    pub artifacts: Vec<PathBuf>,
}

pub type ScoutId = u128;

pub trait ScoutBee: Send + Sync {
    /// Unique logical id for the scout
    fn id(&self) -> ScoutId;

    /// Scout a task option and return a quality estimate [0,1]
    fn scout(&self, task: &Task) -> Result<QualityEstimate, String>;

    /// Broadcast frequency = quality (waggle dance)
    fn broadcast_frequency(&self, quality: f64) -> Duration {
        // Map [0,1] quality → [100ms, 1000ms] period (higher = faster)
        let ms = (1000.0 - 900.0 * quality.clamp(0.0, 1.0)) as u64;
        Duration::from_millis(ms.max(50))
    }

    /// Listen to broadcasts and potentially switch opinions
    fn listen_and_switch(&mut self, _broadcasts: &dyn BroadcastBus) {
        // Default no-op; concrete scouts may override to update internal state
    }
}
