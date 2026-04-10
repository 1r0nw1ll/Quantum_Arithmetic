//! Swarm hive-mind core (Rust)
//! Minimal scaffolding for Scout bees, Broadcast bus, and HiveMind.

pub mod bee;
pub mod hive_mind;
pub mod environment;
pub mod broadcast;

pub use bee::{QualityEstimate, ScoutBee, Task, TaskId, TaskOption};
pub use hive_mind::HiveMind;
pub use environment::{TaskPool, TaskSampleStrategy};
pub use broadcast::{BroadcastBus, BroadcastMessage};

