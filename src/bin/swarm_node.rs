use std::sync::Arc;

use qa_lab_rs::swarm::broadcast::LocalBroadcastBus;
use qa_lab_rs::swarm::environment::TaskPool;
use qa_lab_rs::swarm::hive_mind::HiveMind;
use qa_lab_rs::swarm::bee::Task;
use qa_lab_rs::agents::{e8_scout::E8ScoutBee, qa_scout::QAScoutBee, research_scout::ResearchScoutBee, orchestrator_scout::OrchestratorBee};

fn main() {
    println!("QA Swarm Node (prototype)");

    // Task pool demo
    let pool = TaskPool::with_tasks(vec![
        Task { id: "t1".into(), title: "E8 alignment benchmark".into(), description: "Compute E8 alignments".into() },
        Task { id: "t2".into(), title: "QA tuple computation".into(), description: "Compute QA tuples".into() },
    ]);

    let bus = Arc::new(LocalBroadcastBus::default());
    let e8 = E8ScoutBee::new::<std::path::PathBuf>(None).expect("load E8 roots");
    let orch = OrchestratorBee::new::<std::path::PathBuf>(None).expect("init orchestrator");
    let scouts: Vec<Arc<dyn qa_lab_rs::swarm::bee::ScoutBee>> = vec![
        Arc::new(e8),
        Arc::new(QAScoutBee::default()),
        Arc::new(ResearchScoutBee::default()),
        Arc::new(orch),
    ];

    let mut hive = HiveMind::new(scouts, bus, pool);

    // Run a few steps
    for _ in 0..5 { hive.step(); }

    println!("Swarm prototype completed 5 steps.");
}
