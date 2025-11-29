// QA Speedup Benchmark (Simulated)
// Compare classical SGD vs Harmonic Gradient Descent (HGD) on a quadratic harmonic surface.

use ndarray::{array, Array1};
use qa_lab_rs::qa_core::hgd::{simulate_hgd, simulate_sgd, HGDConfig, QuadObjective, SGDConfig};
use serde::{Serialize, Deserialize};
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

#[derive(Clone, Debug)]
struct CliCfg {
    dim: usize,
    lr: f64,
    lr_sgd: Option<f64>,
    lr_hgd: Option<f64>,
    tol: f64,
    max_steps: usize,
    use_mod9: bool,
    use_mod24: bool,
    repeats: usize,
    seed: u64,
    out_dir: PathBuf,
    hgd_gain: f64,
    hgd_floor: f64,
}

#[derive(Serialize, Deserialize, Clone)]
struct BenchRow {
    method: String,
    dim: usize,
    lr: f64,
    tol: f64,
    max_steps: usize,
    use_mod9: bool,
    use_mod24: bool,
    seed: u64,
    steps_to_tol: usize,
    end_loss: f64,
    compute_units: u64,
}

fn parse_cli() -> CliCfg {
    let args: Vec<String> = env::args().collect();
    let mut cfg = CliCfg {
        dim: 16,
        lr: 0.2,
        lr_sgd: None,
        lr_hgd: None,
        tol: 1e-10,
        max_steps: 2000,
        use_mod9: true,
        use_mod24: true,
        repeats: 1,
        seed: 0,
        out_dir: PathBuf::from("target/qa_benchmarks"),
        hgd_gain: 1.5,
        hgd_floor: 0.2,
    };
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--dim" => {
                i += 1;
                cfg.dim = args[i].parse().unwrap_or(cfg.dim);
            }
            "--lr" => {
                i += 1;
                cfg.lr = args[i].parse().unwrap_or(cfg.lr);
            }
            "--lr-sgd" => {
                i += 1;
                cfg.lr_sgd = args[i].parse().ok();
            }
            "--lr-hgd" => {
                i += 1;
                cfg.lr_hgd = args[i].parse().ok();
            }
            "--tol" => {
                i += 1;
                cfg.tol = args[i].parse().unwrap_or(cfg.tol);
            }
            "--max-steps" => {
                i += 1;
                cfg.max_steps = args[i].parse().unwrap_or(cfg.max_steps);
            }
            "--no-mod9" => cfg.use_mod9 = false,
            "--no-mod24" => cfg.use_mod24 = false,
            "--repeats" => {
                i += 1;
                cfg.repeats = args[i].parse().unwrap_or(cfg.repeats);
            }
            "--seed" => {
                i += 1;
                cfg.seed = args[i].parse().unwrap_or(cfg.seed);
            }
            "--out" => {
                i += 1;
                cfg.out_dir = PathBuf::from(&args[i]);
            }
            "--hgd-gain" => {
                i += 1;
                cfg.hgd_gain = args[i].parse().unwrap_or(cfg.hgd_gain);
            }
            "--hgd-floor" => {
                i += 1;
                cfg.hgd_floor = args[i].parse().unwrap_or(cfg.hgd_floor);
            }
            _ => {}
        }
        i += 1;
    }
    cfg
}

fn synth_obj(dim: usize, seed: u64) -> QuadObjective {
    // lightweight deterministic generator
    fn lcg(mut x: u64) -> impl FnMut() -> u64 {
        move || {
            x = x.wrapping_mul(6364136223846793005).wrapping_add(1);
            x
        }
    }
    let mut rng = lcg(0x9E3779B97F4A7C15 ^ seed);
    let w_star: Array1<f64> = Array1::from_iter((0..dim).map(|i| {
        let r = (rng() >> 12) as f64 / (1u64 << 52) as f64; // ~[0,1)
        ((i as f64) * 0.25 + r).sin()
    }));
    let lambdas: Array1<f64> = Array1::from_iter((0..dim).map(|i| {
        let r = (rng() >> 12) as f64 / (1u64 << 52) as f64;
        0.2 + 0.1 * ((i as f64) % 7.0) + 0.05 * r
    }));
    QuadObjective::new(w_star, lambdas)
}

fn ensure_out(path: &PathBuf) {
    let _ = fs::create_dir_all(path);
}

fn write_csv(path: &PathBuf, rows: &[BenchRow]) {
    let csv_path = path.join("summary.csv");
    let mut need_header = true;
    if csv_path.exists() {
        need_header = false;
    }
    let mut f = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&csv_path)
        .expect("open csv");
    if need_header {
        writeln!(
            f,
            "method,dim,lr,tol,max_steps,use_mod9,use_mod24,seed,steps_to_tol,end_loss,compute_units"
        )
        .ok();
    }
    for r in rows {
        writeln!(
            f,
            "{},{},{},{:.3e},{},{},{},{},{},{:.6e},{}",
            r.method,
            r.dim,
            r.lr,
            r.tol,
            r.max_steps,
            r.use_mod9,
            r.use_mod24,
            r.seed,
            r.steps_to_tol,
            r.end_loss,
            r.compute_units
        )
        .ok();
    }
}

fn write_json(path: &PathBuf, rows: &[BenchRow]) {
    let json_path = path.join("summary.json");
    let mut data: Vec<BenchRow> = if json_path.exists() {
        let s = fs::read_to_string(&json_path).unwrap_or_else(|_| "[]".to_string());
        serde_json::from_str(&s).unwrap_or_default()
    } else {
        Vec::new()
    };
    data.extend_from_slice(rows);
    let s = serde_json::to_string_pretty(&data).expect("json ser");
    fs::write(&json_path, s).ok();
}

fn main() {
    let cfg = parse_cli();
    println!("QA Speedup Benchmark (Rust) - SGD vs HGD\n");
    println!(
        "Params: dim={}, lr_sgd={}, lr_hgd={}, tol={:.3e}, max_steps={}, mod9={}, mod24={}, repeats={}, seed={}, hgd_gain={}, hgd_floor={}",
        cfg.dim, cfg.lr_sgd.unwrap_or(cfg.lr), cfg.lr_hgd.unwrap_or(cfg.lr), cfg.tol, cfg.max_steps, cfg.use_mod9, cfg.use_mod24, cfg.repeats, cfg.seed, cfg.hgd_gain, cfg.hgd_floor
    );

    ensure_out(&cfg.out_dir);
    let mut rows: Vec<BenchRow> = Vec::new();

    for r in 0..cfg.repeats {
        let seed = cfg.seed + r as u64;
        let obj = synth_obj(cfg.dim, seed);
        let w0 = ndarray::Array1::zeros(cfg.dim);

        let sgd_cfg = SGDConfig {
            lr: cfg.lr_sgd.unwrap_or(cfg.lr),
            max_steps: cfg.max_steps,
            tol: cfg.tol,
        };
        let hgd_cfg = HGDConfig {
            base_lr: cfg.lr_hgd.unwrap_or(cfg.lr),
            max_steps: cfg.max_steps,
            tol: cfg.tol,
            use_mod9: cfg.use_mod9,
            use_mod24: cfg.use_mod24,
            mask_gain: cfg.hgd_gain,
            mask_floor: cfg.hgd_floor,
        };

        let (_w_sgd, s_sgd) = simulate_sgd(&obj, &w0, sgd_cfg);
        let (_w_hgd, s_hgd) = simulate_hgd(&obj, &w0, hgd_cfg);

        rows.push(BenchRow {
            method: "SGD".to_string(),
            dim: cfg.dim,
            lr: cfg.lr,
            tol: cfg.tol,
            max_steps: cfg.max_steps,
            use_mod9: cfg.use_mod9,
            use_mod24: cfg.use_mod24,
            seed,
            steps_to_tol: s_sgd.steps,
            end_loss: s_sgd.loss_end,
            compute_units: s_sgd.compute_units,
        });
        rows.push(BenchRow {
            method: "HGD".to_string(),
            dim: cfg.dim,
            lr: cfg.lr,
            tol: cfg.tol,
            max_steps: cfg.max_steps,
            use_mod9: cfg.use_mod9,
            use_mod24: cfg.use_mod24,
            seed,
            steps_to_tol: s_hgd.steps,
            end_loss: s_hgd.loss_end,
            compute_units: s_hgd.compute_units,
        });
    }

    // Console summary (last run as example)
    if let (Some(sgd), Some(hgd)) = (rows.iter().rev().find(|r| r.method == "SGD"), rows.iter().rev().find(|r| r.method == "HGD")) {
        println!("\nResults (last repeat):");
        println!(
            "  SGD: steps = {:>5}, end loss = {:.3e}, compute ≈ {} ops",
            sgd.steps_to_tol, sgd.end_loss, sgd.compute_units
        );
        println!(
            "  HGD: steps = {:>5}, end loss = {:.3e}, compute ≈ {} ops",
            hgd.steps_to_tol, hgd.end_loss, hgd.compute_units
        );
        let step_speedup = (sgd.steps_to_tol as f64) / (hgd.steps_to_tol as f64);
        let compute_ratio = (sgd.compute_units as f64) / (hgd.compute_units as f64);
        println!("\nDerived:");
        println!("  Step speedup (SGD/HGD): {:.2}×", step_speedup);
        println!("  Compute ratio (SGD/HGD): {:.2}×", compute_ratio);
    }

    // Persist results
    write_csv(&cfg.out_dir, &rows);
    write_json(&cfg.out_dir, &rows);

    println!("\nWrote: {}", cfg.out_dir.join("summary.csv").display());
    println!("       {}", cfg.out_dir.join("summary.json").display());
}
