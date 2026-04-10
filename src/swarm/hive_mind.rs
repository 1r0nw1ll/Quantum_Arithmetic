use std::sync::Arc;

use crate::swarm::bee::{QualityEstimate, ScoutBee, Task};
use crate::swarm::broadcast::BroadcastBus;
use crate::swarm::environment::{TaskPool, TaskSampleStrategy};

pub struct HiveMind<B: BroadcastBus> {
    pub scouts: Vec<Arc<dyn ScoutBee>>, // logical scouts
    pub policy: Vec<f64>,               // population vector π
    pub broadcast_bus: Arc<B>,
    pub task_pool: TaskPool,
}

impl<B: BroadcastBus> HiveMind<B> {
    pub fn new(scouts: Vec<Arc<dyn ScoutBee>>, broadcast_bus: Arc<B>, task_pool: TaskPool) -> Self {
        let n = scouts.len().max(1);
        Self {
            scouts,
            policy: vec![1.0 / n as f64; n],
            broadcast_bus,
            task_pool,
        }
    }

    fn policy_value(&self) -> f64 {
        // Simple normalization constant; non-zero by construction
        self.policy.iter().cloned().sum::<f64>().max(1e-9)
    }

    /// Maynard–Cross Learning update (simplified form)
    fn mcl_update(&mut self, scout_index: usize, quality: f64) {
        let alpha = 1.0 / self.scouts.len().max(1) as f64;
        let v_pi = self.policy_value();
        for (i, pi) in self.policy.iter_mut().enumerate() {
            if i == scout_index {
                *pi += alpha * (quality / v_pi) * (1.0 - *pi);
            } else {
                *pi += alpha * (quality / v_pi) * (-*pi);
            }
            *pi = pi.clamp(0.0, 1.0);
        }
        // Normalize to sum=1
        let s = self.policy.iter().sum::<f64>().max(1e-12);
        for pi in &mut self.policy { *pi /= s; }
    }

    fn sample_task_for_scout(&self) -> Option<Task> {
        self.task_pool.sample_task(TaskSampleStrategy::Random)
    }

    pub fn step(&mut self) {
        if self.task_pool.is_empty() || self.scouts.is_empty() {
            return;
        }

        // Sequential scouting over all scouts for a sampled task each
        let mut pending: Vec<(usize, QualityEstimate)> = Vec::new();
        for (idx, s) in self.scouts.iter().enumerate() {
            if let Some(task) = self.sample_task_for_scout() {
                if let Ok(est) = s.scout(&task) {
                    pending.push((idx, est));
                }
            }
        }
        for (idx, est) in pending.into_iter() {
            let sid = self.scouts[idx].id();
            self.broadcast_bus.broadcast(sid, est.clone(), est.quality);
            self.mcl_update(idx, est.quality);
        }
    }
}
