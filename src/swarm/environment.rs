use crate::swarm::bee::Task;
use rand::seq::SliceRandom;
use rand::thread_rng;
use std::sync::{Arc, RwLock};

#[derive(Debug, Clone, Copy)]
pub enum TaskSampleStrategy {
    Random,
    RoundRobin,
}

#[derive(Debug, Default)]
pub struct TaskPool {
    tasks: Arc<RwLock<Vec<Task>>>,
    rr_index: Arc<RwLock<usize>>,
}

impl TaskPool {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_tasks(tasks: Vec<Task>) -> Self {
        Self {
            tasks: Arc::new(RwLock::new(tasks)),
            rr_index: Arc::new(RwLock::new(0)),
        }
    }

    pub fn push(&self, task: Task) {
        if let Ok(mut t) = self.tasks.write() {
            t.push(task);
        }
    }

    pub fn len(&self) -> usize {
        self.tasks.read().map(|t| t.len()).unwrap_or(0)
    }

    pub fn is_empty(&self) -> bool { self.len() == 0 }

    pub fn sample_task(&self, strat: TaskSampleStrategy) -> Option<Task> {
        let mut rng = thread_rng();
        let mut guard = self.tasks.write().ok()?;
        match strat {
            TaskSampleStrategy::Random => guard.choose(&mut rng).cloned(),
            TaskSampleStrategy::RoundRobin => {
                if guard.is_empty() { return None; }
                let mut idx = self.rr_index.write().ok()?;
                let task = guard.get(*idx % guard.len()).cloned();
                *idx = (*idx + 1) % guard.len();
                task
            }
        }
    }
}

