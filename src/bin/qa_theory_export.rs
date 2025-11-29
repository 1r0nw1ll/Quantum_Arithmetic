// Overleaf-ready theory exporter
// Reads benchmark JSON and emits a LaTeX snippet with measured speedups and equations.

use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize)]
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

fn read_rows(path: &str) -> Vec<BenchRow> {
    let s = fs::read_to_string(path).expect("read summary.json");
    serde_json::from_str(&s).expect("parse summary.json")
}

fn avg(vals: &[f64]) -> f64 {
    if vals.is_empty() { return 0.0; }
    vals.iter().sum::<f64>() / (vals.len() as f64)
}

fn main() {
    let in_json = PathBuf::from("target/qa_benchmarks/summary.json");
    let template = PathBuf::from("docs/templates/qa_training_compute_template.tex");
    let out_tex = PathBuf::from("docs/qa_training_compute_section.tex");

    if !in_json.exists() {
        eprintln!("No benchmark JSON found at {}. Run qa_speed_benchmark first.", in_json.display());
        std::process::exit(1);
    }

    let rows = read_rows(in_json.to_str().unwrap());
    if rows.is_empty() {
        eprintln!("No rows in benchmark JSON.");
        std::process::exit(1);
    }

    // Group by (dim, lr, tol, use_mod9, use_mod24)
    let mut groups: HashMap<(usize, i64, i64, bool, bool), Vec<BenchRow>> = HashMap::new();
    for r in rows.into_iter() {
        let key = (r.dim, (r.lr * 1e9) as i64, (r.tol.log10() * 10.0) as i64, r.use_mod9, r.use_mod24);
        groups.entry(key).or_default().push(r);
    }
    // Clone so we can reuse below
    let groups_vec: Vec<_> = groups.iter().map(|(k,v)| (*k, v.clone())).collect();
    // Canonical: prefer dim=16, lr≈0.2 group if present; else fall back to largest group
    let mut chosen: Option<((usize,i64,i64,bool,bool), Vec<BenchRow>)> = None;
    for (k, v) in &groups_vec {
        if k.0 == 16 && ((k.1 as f64)/1e9 - 0.2).abs() < 1e-6 { chosen = Some((*k, v.clone())); break; }
    }
    let (key, grp) = match chosen { Some(x) => x, None => {
        let (k,v) = groups_vec.into_iter().max_by_key(|(_,v)| v.len()).unwrap(); (k,v)
    }};
    let dim = key.0;
    let lr = (key.1 as f64) / 1e9;
    // reconstruct tol approx from log bucket
    let tol = 10f64.powf((key.2 as f64) / 10.0);

    let mut sgd_steps = Vec::new();
    let mut hgd_steps = Vec::new();
    let mut sgd_comp = Vec::new();
    let mut hgd_comp = Vec::new();
    for r in grp.iter() {
        if r.method == "SGD" {
            sgd_steps.push(r.steps_to_tol as f64);
            sgd_comp.push(r.compute_units as f64);
        } else if r.method == "HGD" {
            hgd_steps.push(r.steps_to_tol as f64);
            hgd_comp.push(r.compute_units as f64);
        }
    }
    let sgd_steps_m = avg(&sgd_steps);
    let hgd_steps_m = avg(&hgd_steps);
    let sgd_comp_m = avg(&sgd_comp);
    let hgd_comp_m = avg(&hgd_comp);
    let step_speedup = if hgd_steps_m > 0.0 { sgd_steps_m / hgd_steps_m } else { 0.0 };
    let compute_ratio = if hgd_comp_m > 0.0 { sgd_comp_m / hgd_comp_m } else { 0.0 };

    // Sweep summary over all (dim, lr) groups: win if mean_sgd_steps > mean_hgd_steps
    let mut sweep_wins = 0usize;
    let mut sweep_total = 0usize;
    let mut sweep_speedups: Vec<f64> = Vec::new();
    let mut sweep_comp_ratios: Vec<f64> = Vec::new();
    for (k, rows_k) in groups {
        // method partitions
        let mut s_steps = Vec::new();
        let mut h_steps = Vec::new();
        let mut s_comp = Vec::new();
        let mut h_comp = Vec::new();
        for r in rows_k.iter() {
            if r.method == "SGD" {
                s_steps.push(r.steps_to_tol as f64);
                s_comp.push(r.compute_units as f64);
            } else if r.method == "HGD" {
                h_steps.push(r.steps_to_tol as f64);
                h_comp.push(r.compute_units as f64);
            }
        }
        if !s_steps.is_empty() && !h_steps.is_empty() {
            sweep_total += 1;
            let ms = avg(&s_steps);
            let mh = avg(&h_steps);
            let cs = avg(&s_comp);
            let ch = avg(&h_comp);
            let sp = if mh > 0.0 { ms / mh } else { 0.0 };
            let cr = if ch > 0.0 { cs / ch } else { 0.0 };
            if sp > 1.0 { sweep_wins += 1; }
            sweep_speedups.push(sp);
            sweep_comp_ratios.push(cr);
        }
    }
    let sweep_mean_speedup = avg(&sweep_speedups);
    let sweep_mean_compute = avg(&sweep_comp_ratios);

    let tpl = fs::read_to_string(&template).expect("read template");
    let filled = tpl
        .replace("{{dim}}", &format!("{}", dim))
        .replace("{{tol}}", &format!("{:.1e}", tol))
        .replace("{{lr}}", &format!("{:.3}", lr))
        .replace("{{sgd_steps}}", &format!("{:.1}", sgd_steps_m))
        .replace("{{hgd_steps}}", &format!("{:.1}", hgd_steps_m))
        .replace("{{step_speedup}}", &format!("{:.2}", step_speedup))
        .replace("{{compute_ratio}}", &format!("{:.2}", compute_ratio))
        .replace("{{wins}}", &format!("{}", sweep_wins))
        .replace("{{total}}", &format!("{}", sweep_total))
        .replace("{{mean_step_speedup}}", &format!("{:.2}", sweep_mean_speedup))
        .replace("{{mean_compute_ratio}}", &format!("{:.2}", sweep_mean_compute));

    if let Some(parent) = out_tex.parent() { let _ = fs::create_dir_all(parent); }
    fs::write(&out_tex, filled).expect("write output tex");
    println!("Wrote: {}", out_tex.display());
}
