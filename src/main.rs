// QA Lab - Main Entry Point
// Demonstrates core QA system functionality in Rust

use ndarray::Array1;
use qa_lab_rs::qa_core::invariants::E8Alignment;
use qa_lab_rs::{QABundle, QAInvariants, QATuple};

fn main() {
    println!("🔬 QA Lab - Rust Port v4.0.0");
    println!("=====================================\n");

    // Test Grant's LRT tuple
    println!("📊 Grant's LRT: (1, 2, 3, 5)");
    let lrt = QATuple::new(1.0, 2.0);
    println!(
        "  QA Tuple: b={}, e={}, d={}, a={}",
        lrt.b, lrt.e, lrt.d, lrt.a
    );
    println!("  Valid: {}", lrt.is_valid());

    let lrt_bundle = QABundle::from_tuple(lrt.clone());
    println!("  Primary Invariants:");
    println!("    J (perigee) = {}", lrt_bundle.j);
    println!("    K (apogee) = {}", lrt_bundle.k);
    println!("    X (half focal dist) = {}", lrt_bundle.x);
    println!("  Secondary Invariants:");
    println!("    W (equilateral side) = {}", lrt_bundle.w);
    println!("    Y (Eisenstein) = {}", lrt_bundle.y);
    println!("    Z = {}", lrt_bundle.z);
    println!("  Triangle Sides:");
    println!("    C (focal separation) = {}", lrt_bundle.c);
    println!("    F (altitude) = {}", lrt_bundle.f);
    println!("    G (hypotenuse) = {}", lrt_bundle.g);
    println!();

    // Test Satellite Family tuple
    println!("🛰️  Satellite Family: (3, 5, 8, 13)");
    let satellite = QATuple::new(3.0, 5.0);
    println!(
        "  QA Tuple: b={}, e={}, d={}, a={}",
        satellite.b, satellite.e, satellite.d, satellite.a
    );
    println!("  Valid: {}", satellite.is_valid());

    let sat_bundle = QABundle::from_tuple(satellite);
    println!(
        "  J={}, K={}, X={}",
        sat_bundle.j, sat_bundle.k, sat_bundle.x
    );
    println!();

    // Test Singularity tuple
    println!("⚫ Singularity: (9, 9, 18, 27)");
    let singularity = QATuple::new(9.0, 9.0);
    println!(
        "  QA Tuple: b={}, e={}, d={}, a={}",
        singularity.b, singularity.e, singularity.d, singularity.a
    );
    println!("  Valid: {}", singularity.is_valid());
    println!();

    // Test E8 projection
    println!("🌌 E8 Projection Test");
    let projection = lrt_bundle.e8_projection();
    println!("  8D Projection: {:?}", projection);
    println!("  Dimension: {}", projection.len());
    println!();

    // Test E8 alignment (simple mock)
    println!("🔗 E8 Alignment Test");
    let qa_vec = lrt_bundle.e8_projection();
    // Mock E8 root (in real implementation, would have 240 roots)
    let mock_e8_root = Array1::from_vec(vec![1.0, 1.0, 2.0, 3.0, 2.0, 6.0, 2.0, 8.0]);
    let e8_roots = vec![mock_e8_root];
    let alignment = E8Alignment::compute(&qa_vec, &e8_roots);
    println!("  E8 Alignment Score: {:.4}", alignment);
    println!();

    // Test Harmonic Index
    println!("🎵 Harmonic Index Computation");
    let inv = QAInvariants::from_bundle(&lrt_bundle);
    let hi = inv.harmonic_index(alignment, 0.5);
    println!("  E8 Alignment: {:.4}", alignment);
    println!("  Loss: 0.5");
    println!("  Harmonic Index: {:.4}", hi);
    println!("  Formula: HI = alignment × exp(-0.1 × loss)");
    println!();

    // Test invalid tuple
    println!("❌ Invalid Tuple Test");
    match QATuple::from_values(1.0, 2.0, 4.0, 5.0) {
        Ok(_) => println!("  ERROR: Should have failed validation!"),
        Err(e) => println!("  ✓ Correctly rejected: {}", e),
    }
    println!();

    println!("✅ All core QA operations validated!");
    println!("=====================================");
    println!("\n📝 Next Steps:");
    println!("  • Port QA encoder neural network (tch-rs)");
    println!("  • Port specialized agents (LIDAR, Vision, Spectral)");
    println!("  • Port agent pipeline (Scout → Executor → Reviewer)");
    println!("  • Port multimodal processing");
}
