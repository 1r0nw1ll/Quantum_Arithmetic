// QA-PCN Sheaf Demo
// Simulates a tiny QA-PCN with Laplacian smoothing and harmonic updates.

use qa_lab_rs::qa_core::pcn::QAPCN;
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

fn ring_graph(n: usize, w: f64) -> Vec<(usize, usize, f64)> {
    let mut edges = Vec::new();
    for i in 0..n {
        let j = (i + 1) % n;
        edges.push((i, j, w));
    }
    edges
}

fn parse_arg<T: std::str::FromStr>(args: &[String], key: &str, default: T) -> T {
    if let Some(i) = args.iter().position(|a| a == key) {
        if let Some(v) = args.get(i + 1) {
            return v.parse::<T>().ok().unwrap_or(default);
        }
    }
    default
}

fn parse_theta(args: &[String]) -> f64 {
    if let Some(i) = args.iter().position(|a| a == "--theta") {
        if let Some(v) = args.get(i + 1) {
            if v.eq_ignore_ascii_case("pi") {
                return std::f64::consts::PI;
            }
            if let Ok(val) = v.parse::<f64>() {
                return val;
            }
        }
    }
    0.0
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let n = parse_arg(&args, "--nodes", 8usize);
    let theta = parse_theta(&args);
    let steps = parse_arg(&args, "--steps", 500usize);
    let lr = parse_arg(&args, "--lr", 0.2f64);
    let alpha = parse_arg(&args, "--alpha", 0.1f64);
    let opt = args
        .windows(2)
        .find(|w| w[0] == "--opt")
        .map(|w| w[1].clone())
        .unwrap_or_else(|| "hgd".to_string());
    let csv_path = args
        .windows(2)
        .find(|w| w[0] == "--csv")
        .map(|w| PathBuf::from(&w[1]));

    let adj = ring_graph(n, 1.0);
    let mut pcn = QAPCN::new(n, adj, theta, alpha);
    pcn.set_target(vec![1.0; n]);

    let eigs = pcn.laplacian_eigenvalues();
    let lmin = eigs.first().cloned().unwrap_or(0.0);
    let lmax = eigs.last().cloned().unwrap_or(0.0);

    println!("QA-PCN Sheaf Demo\n---------------------");
    println!("nodes={}, theta={}, steps={}, lr={}, alpha={}, opt={}", n, theta, steps, lr, alpha, opt);
    println!("Laplacian eigenvalues: min={:.4}, max={:.4}", lmin, lmax);
    println!("start energy: {:.6}", pcn.energy());

    // CSV logging
    let mut file = None;
    if let Some(path) = csv_path {
        if let Some(parent) = path.parent() { let _ = fs::create_dir_all(parent); }
        let newfile = !path.exists();
        let mut f = fs::OpenOptions::new().create(true).append(true).open(&path).expect("open csv");
        if newfile {
            writeln!(f, "step,energy,lambda_min,lambda_max").ok();
        }
        // write step 0
        writeln!(f, "{},{:.6},{:.6},{:.6}", 0, pcn.energy(), lmin, lmax).ok();
        file = Some((path, f));
    }

    for s in 1..=steps {
        match opt.as_str() {
            "sgd" => pcn.step_sgd(lr),
            _ => pcn.step_hgd(lr),
        }
        if let Some((ref _p, ref mut f)) = file {
            writeln!(f, "{},{:.6},{:.6},{:.6}", s, pcn.energy(), lmin, lmax).ok();
        }
    }

    println!("end energy:   {:.6}", pcn.energy());
}
