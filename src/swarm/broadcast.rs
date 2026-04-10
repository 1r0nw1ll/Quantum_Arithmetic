use serde::{Deserialize, Serialize};

use crate::swarm::bee::{QualityEstimate, ScoutId};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BroadcastMessage {
    pub node: String,
    pub scout_id: ScoutId,
    pub estimate: QualityEstimate,
    pub quality: f64,
    pub timestamp_ms: i64,
}

pub trait BroadcastBus: Send + Sync {
    fn broadcast(&self, scout_id: ScoutId, estimate: QualityEstimate, quality: f64);
    fn sample_neighborhood(&self, max_items: usize) -> Vec<QualityEstimate>;
}

/// Minimal in-process broadcast bus (single-node)
use std::sync::{Arc, RwLock};

#[derive(Default, Clone)]
pub struct LocalBroadcastBus {
    ring: Arc<RwLock<Vec<QualityEstimate>>>,
}

impl BroadcastBus for LocalBroadcastBus {
    fn broadcast(&self, _scout_id: ScoutId, estimate: QualityEstimate, _quality: f64) {
        if let Ok(mut r) = self.ring.write() {
            r.push(estimate);
            if r.len() > 1024 { r.remove(0); }
        }
    }

    fn sample_neighborhood(&self, max_items: usize) -> Vec<QualityEstimate> {
        let mut out = Vec::new();
        if let Ok(r) = self.ring.read() {
            let n = r.len();
            let take = n.min(max_items);
            out.extend(r.iter().rev().take(take).cloned());
        }
        out
    }
}
