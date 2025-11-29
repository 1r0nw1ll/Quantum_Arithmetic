// QA-JEPA Demo (torch-free)

use ndarray::{Array1, Array2};
use qa_lab_rs::qa_core::jepa::QAJEPA;
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

fn parse_arg<T: std::str::FromStr>(args: &[String], key: &str, default: T) -> T {
    if let Some(i) = args.iter().position(|a| a == key) {
        if let Some(v) = args.get(i + 1) {
            return v.parse::<T>().ok().unwrap_or(default);
        }
    }
    default
}

fn synth_data(n: usize, dim_x: usize) -> Vec<Array1<f64>> {
    // simple deterministic signals
    let mut out = Vec::with_capacity(n);
    for t in 0..n {
        let mut x = Array1::<f64>::zeros(dim_x);
        for i in 0..dim_x {
            let w = 0.1 * (1 + i as i32) as f64;
            x[i] = ((t as f64) * w * 0.05).sin();
        }
        out.push(x);
    }
    out
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let dim_x = parse_arg(&args, "--dim-x", 16usize);
    let dim_z = parse_arg(&args, "--dim-z", 12usize);
    let epochs = parse_arg(&args, "--epochs", 30usize);
    let lr = parse_arg(&args, "--lr", 0.05f64);
    let opt = args
        .windows(2)
        .find(|w| w[0] == "--opt")
        .map(|w| w[1].clone())
        .unwrap_or_else(|| "hgd".to_string());
    let batch_size = parse_arg(&args, "--batch-size", 32usize);
    let log_csv = args
        .windows(2)
        .find(|w| w[0] == "--log-csv")
        .map(|w| PathBuf::from(&w[1]))
        .unwrap_or_else(|| PathBuf::from(format!("target/qa_jepa/jepa_{}.csv", opt)));

    let mut model = QAJEPA::new(dim_x, dim_z);
    let data = synth_data(256, dim_x);

    println!("QA-JEPA Demo  dim_x={}, dim_z={}, epochs={}, lr={}, opt={}, batch_size={}", dim_x, dim_z, epochs, lr, opt, batch_size);

    if let Some(parent) = log_csv.parent() { let _ = fs::create_dir_all(parent); }
    let newfile = !log_csv.exists();
    let mut f = fs::OpenOptions::new().create(true).append(true).open(&log_csv).expect("open csv");
    if newfile {
        writeln!(f, "epoch,method,dim_x,dim_z,batch_size,avg_energy").ok();
    }

    let n = data.len();
    let n_batches = (n + batch_size - 1) / batch_size;
    for e in 0..epochs {
        let mut sum_energy = 0.0;
        for b in 0..n_batches {
            let start = b * batch_size;
            let end = ((b + 1) * batch_size).min(n);
            if start >= end { break; }
            // accumulate gradient over batch
            let mut g_acc = Array2::<f64>::zeros((dim_z, dim_z));
            for x in &data[start..end] {
                let z = model.encode(x);
                let z_hat = model.predict(&z);
                sum_energy += model.energy(&z, &z_hat);
                let g = model.grad_w_pred(&z, &z_hat);
                // g_acc += g
                for i in 0..dim_z {
                    for j in 0..dim_z {
                        g_acc[(i, j)] += g[(i, j)];
                    }
                }
            }
            let bs = (end - start) as f64;
            for i in 0..dim_z {
                for j in 0..dim_z {
                    g_acc[(i, j)] /= bs;
                }
            }
            match opt.as_str() {
                "sgd" => model.sgd_step_pred(&g_acc, lr),
                _ => model.hgd_step_pred(&g_acc, lr),
            }
        }
        let avg = sum_energy / (n as f64);
        if e % 5 == 0 || e + 1 == epochs {
            println!("epoch {:>3}: avg_energy {:.6}", e + 1, avg);
        }
        writeln!(f, "{},{},{},{},{},{}", e + 1, opt, dim_x, dim_z, batch_size, avg).ok();
    }
}
