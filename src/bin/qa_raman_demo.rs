// QA Raman Demo: Train a simple classifier on Raman spectra using SGD vs QA-HGD updates.
// Loads spectra from `qa_data/raman/<class>/**/*.txt`, builds fixed-grid features,
// trains a softmax linear classifier, and logs accuracy per epoch to CSV.

use ndarray::{Array1, Array2, Axis};
use qa_lab_rs::qa_core::{digital_root, mod24};
use std::collections::BTreeMap;
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

fn parse_spectrum(path: &Path) -> Option<(Vec<f64>, Vec<f64>)> {
    let f = fs::File::open(path).ok()?;
    let reader = BufReader::new(f);
    let mut xs = Vec::new();
    let mut ys = Vec::new();
    for line in reader.lines() {
        if let Ok(mut l) = line {
            let s = l.trim();
            if s.is_empty() { continue; }
            if s.starts_with('#') || s.starts_with("##") { continue; }
            // Try comma-separated first
            if s.contains(',') {
                let parts: Vec<_> = s.split(',').map(|t| t.trim()).collect();
                if parts.len() >= 2 {
                    if let (Ok(x), Ok(y)) = (parts[0].parse::<f64>(), parts[1].parse::<f64>()) {
                        xs.push(x);
                        ys.push(y);
                        continue;
                    }
                }
            }
            // Try whitespace-separated
            let parts: Vec<_> = s.split_whitespace().collect();
            if parts.len() >= 2 {
                if let (Ok(x), Ok(y)) = (parts[0].parse::<f64>(), parts[1].parse::<f64>()) {
                    xs.push(x);
                    ys.push(y);
                    continue;
                }
            }
        }
    }
    if xs.is_empty() { None } else { Some((xs, ys)) }
}

fn min_max(v: &[f64]) -> (f64, f64) {
    let mut mn = f64::INFINITY;
    let mut mx = f64::NEG_INFINITY;
    for &x in v {
        if x < mn { mn = x; }
        if x > mx { mx = x; }
    }
    (mn, mx)
}

fn interp_grid(x: &mut Vec<f64>, y: &mut Vec<f64>, gmin: f64, gmax: f64, n: usize) -> (Vec<f64>, Vec<f64>) {
    // Sort by x ascending
    let mut idx: Vec<usize> = (0..x.len()).collect();
    idx.sort_by(|&i, &j| x[i].partial_cmp(&x[j]).unwrap_or(std::cmp::Ordering::Equal));
    let mut sx = Vec::with_capacity(x.len());
    let mut sy = Vec::with_capacity(y.len());
    for i in idx { sx.push(x[i]); sy.push(y[i]); }
    // Normalize intensity to max=1 (if possible)
    let (_, my) = min_max(&sy);
    if my != 0.0 && my.is_finite() {
        for v in sy.iter_mut() { *v /= my; }
    }
    // Linear interpolation
    let mut out = vec![0.0; n];
    let step = if n > 1 { (gmax - gmin) / ((n - 1) as f64) } else { 0.0 };
    let mut grid_x = vec![0.0; n];
    for i in 0..n { grid_x[i] = gmin + (i as f64) * step; }
    if sx.len() < 2 { return (grid_x, out); }
    let mut j = 0usize;
    for i in 0..n {
        let gx = grid_x[i];
        while j + 1 < sx.len() && sx[j + 1] < gx { j += 1; }
        if j + 1 < sx.len() {
            let x0 = sx[j];
            let x1 = sx[j + 1];
            let y0 = sy[j];
            let y1 = sy[j + 1];
            if x1 > x0 {
                let t = ((gx - x0) / (x1 - x0)).clamp(0.0, 1.0);
                out[i] = y0 + t * (y1 - y0);
            } else {
                out[i] = y0;
            }
        } else {
            out[i] = sy[sx.len() - 1];
        }
    }
    (grid_x, out)
}

fn find_topk_peaks(y: &[f64], k: usize, window: usize, prom: f64) -> Vec<usize> {
    // Simple local maxima with optional prominence filter over a small window
    let n = y.len();
    let mut peaks: Vec<(usize, f64)> = Vec::new();
    for i in 1..(n.saturating_sub(1)) {
        if y[i] > y[i-1] && y[i] > y[i+1] {
            // compute a crude baseline as average of neighbors at +/- window (clamped)
            let l = i.saturating_sub(window);
            let r = (i + window).min(n - 1);
            let base = 0.5 * (y[l] + y[r]);
            let prominence = (y[i] - base).max(0.0);
            if prominence >= prom { peaks.push((i, y[i])); }
        }
    }
    peaks.sort_by(|a,b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    peaks.truncate(k);
    peaks.into_iter().map(|(i,_)| i).collect()
}

fn qa_from_peaks(grid_x: &[f64], grid_y: &[f64], idxs: &[usize]) -> Option<(f64,f64,f64,f64, Vec<f64>)> {
    if idxs.len() < 3 { return None; }
    // sort peaks by position
    let mut p: Vec<(f64,f64,usize)> = idxs.iter().map(|&i| (grid_x[i], grid_y[i], i)).collect();
    p.sort_by(|a,b| a.0.partial_cmp(&b.0).unwrap_or(std::cmp::Ordering::Equal));
    let (nu1, i1, idx1) = (p[0].0, p[0].1, p[0].2);
    let (nu2, i2, idx2) = (p[1].0, p[1].1, p[1].2);
    let (nu3, i3, idx3) = (p[2].0, p[2].1, p[2].2);
    let e = nu2 - nu1;
    let b = nu3 - nu2;
    if e <= 0.0 || b <= 0.0 { return None; }
    let d = b + e;
    let a = e + d;
    // normalized peak positions to [0,1] (assume grid within [0,4000])
    let nu_norm = |v: f64| -> f64 { (v / 4000.0).clamp(0.0, 1.0) };
    let extra = vec![i1, i2, i3, nu_norm(nu1), nu_norm(nu2), nu_norm(nu3)];
    Some((b,e,d,a, extra))
}

fn qa_invariants_block(b: f64, e: f64, d: f64, a: f64) -> Vec<f64> {
    let j = b * d;
    let k = d * a;
    let x = e * d;
    let c = 2.0 * x;
    let f = b * a;
    let g = e*e + d*d;
    vec![b,e,d,a,j,k,x,c,f,g]
}

fn build_features(grid_x: &[f64], grid_y: &[f64], feat_mode: &str) -> Vec<f64> {
    let mut out: Vec<f64> = Vec::new();
    let y_max = grid_y.iter().cloned().fold(0.0, f64::max);
    let norm_y: Vec<f64> = if y_max > 0.0 { grid_y.iter().map(|v| v / y_max).collect() } else { grid_y.to_vec() };
    let peaks = find_topk_peaks(&norm_y, 3, 2, 0.02);
    let mut qa_blk: Vec<f64> = vec![0.0; 16];
    if let Some((b,e,d,a, extra)) = qa_from_peaks(grid_x, &norm_y, &peaks) {
        let mut inv = qa_invariants_block(b,e,d,a);
        inv.extend(extra); // I1,I2,I3, nu1_norm,nu2_norm,nu3_norm
        qa_blk = inv;
    }
    match feat_mode {
        "grid" => norm_y,
        "qa" => qa_blk,
        _ => { // grid+qa
            out.extend(norm_y);
            out.extend(qa_blk);
            out
        }
    }
}

fn standardize_inplace(x: &mut Array2<f64>) {
    let (n, d) = (x.nrows(), x.ncols());
    for j in 0..d {
        let mut mean = 0.0;
        for i in 0..n { mean += x[[i,j]]; }
        mean /= n as f64;
        let mut var = 0.0;
        for i in 0..n { let v = x[[i,j]] - mean; var += v*v; }
        var /= (n as f64).max(1.0);
        let std = var.sqrt();
        if std > 0.0 {
            for i in 0..n { x[[i,j]] = (x[[i,j]] - mean) / std; }
        } else {
            for i in 0..n { x[[i,j]] = 0.0; }
        }
    }
}

fn gather_raman(root: &Path, grid_n: usize, gmin: f64, gmax: f64, max_per_class: Option<usize>, feat_mode: &str)
    -> (Array2<f64>, Vec<usize>, Vec<String>)
{
    let mut class_to_index: BTreeMap<String, usize> = BTreeMap::new();
    let mut samples: Vec<Vec<f64>> = Vec::new();
    let mut labels: Vec<usize> = Vec::new();

    if let Ok(entries) = fs::read_dir(root) {
        for ent in entries.flatten() {
            let path = ent.path();
            if !path.is_dir() { continue; }
            let class = path.file_name().unwrap().to_string_lossy().to_string();
            // Skip empty/meta folders
            if class == "." || class == ".." { continue; }
            let cidx = class_to_index.len();
            class_to_index.entry(class.clone()).or_insert(cidx);
            let mut count = 0usize;
            let mut walk = vec![path.clone()];
            while let Some(p) = walk.pop() {
                if p.is_dir() {
                    if let Ok(rd) = fs::read_dir(&p) {
                        for e in rd.flatten() { walk.push(e.path()); }
                    }
                } else {
                    if p.extension().and_then(|s| s.to_str()).unwrap_or("").to_ascii_lowercase() != "txt" { continue; }
                    let parsed = parse_spectrum(&p);
                    if let Some((mut xs, mut ys)) = parsed {
                        let (grid_x, grid_y) = interp_grid(&mut xs, &mut ys, gmin, gmax, grid_n);
                        let feat = build_features(&grid_x, &grid_y, feat_mode);
                        samples.push(feat);
                        labels.push(*class_to_index.get(&class).unwrap());
                        count += 1;
                        if let Some(m) = max_per_class { if count >= m { break; } }
                    }
                }
            }
        }
    }
    let n = samples.len();
    let d = samples.get(0).map(|v| v.len()).unwrap_or(0);
    let mut x = Array2::<f64>::zeros((n, d));
    for (i, v) in samples.into_iter().enumerate() {
        for j in 0..d { x[[i, j]] = v[j]; }
    }
    let mut classes: Vec<_> = class_to_index.into_iter().collect();
    classes.sort_by_key(|(_, idx)| *idx);
    let class_names: Vec<String> = classes.into_iter().map(|(k, _)| k).collect();
    (x, labels, class_names)
}

fn one_hot(y: &[usize], n_classes: usize) -> Array2<f64> {
    let mut yh = Array2::<f64>::zeros((y.len(), n_classes));
    for (i, &c) in y.iter().enumerate() { yh[[i, c]] = 1.0; }
    yh
}

fn softmax_rows(mut z: Array2<f64>) -> Array2<f64> {
    for mut row in z.axis_iter_mut(Axis(0)) {
        let maxv = row.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        let mut sum = 0.0; for v in row.iter_mut() { *v = (*v - maxv).exp(); sum += *v; }
        if sum > 0.0 { for v in row.iter_mut() { *v /= sum; } }
    }
    z
}

fn accuracy(x: &Array2<f64>, y: &[usize], w: &Array2<f64>, b: &Array1<f64>) -> f64 {
    let logits = x.dot(w) + b;
    let probs = softmax_rows(logits);
    let mut correct = 0usize;
    for (i, prob_row) in probs.axis_iter(Axis(0)).enumerate() {
        let (mut argm, mut best) = (0usize, f64::NEG_INFINITY);
        for (j, &p) in prob_row.iter().enumerate() { if p > best { best = p; argm = j; } }
        if argm == y[i] { correct += 1; }
    }
    correct as f64 / y.len() as f64
}

fn harmonic_mask(val: f64, idx: usize, use_mod9: bool, use_mod24: bool, gain: f64, floor: f64) -> f64 {
    let mut m = 1.0;
    if use_mod24 {
        let phase = mod24((idx as f64 + 1.0) * 1.0);
        let dist = ((phase - 0.0).abs())
            .min((phase - 6.0).abs())
            .min((phase - 12.0).abs())
            .min((phase - 18.0).abs());
        let w = 1.0 - (dist / 6.0) * 0.8;
        m *= w.max(0.2);
    }
    if use_mod9 {
        let scaled = (val * 1e3).round() as i64;
        let dr = digital_root(scaled);
        let w = match dr { 1 | 3 | 6 | 9 => 1.0, _ => 0.5 };
        m *= w;
    }
    let boosted = (m * gain).max(floor);
    boosted.min(2.0)
}

fn train_softmax(
    x: &Array2<f64>, y: &[usize], n_classes: usize,
    epochs: usize, batch: usize,
    lr_sgd: f64, lr_hgd: f64,
    use_hgd: bool, hgd_gain: f64, hgd_floor: f64,
    log_path: &Path,
) -> std::io::Result<()> {
    let n = x.nrows();
    let d = x.ncols();
    let mut w = Array2::<f64>::zeros((d, n_classes));
    let mut b = Array1::<f64>::zeros(n_classes);
    let yh = one_hot(y, n_classes);
    let mut idxs: Vec<usize> = (0..n).collect();
    let mut rng_state: u64 = 0xA5A5_0123_89AB_CDEF;
    let mut csv = fs::File::create(log_path)?;
    writeln!(csv, "epoch,method,loss,acc")?;
    for epoch in 1..=epochs {
        // shuffle
        for i in 0..idxs.len() {
            rng_state = rng_state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let j = (rng_state as usize) % idxs.len();
            idxs.swap(i, j);
        }
        let mut total_loss = 0.0;
        let mut offset = 0usize;
        while offset < n {
            let end = (offset + batch).min(n);
            let bs = end - offset;
            // batch indices
            let mut xb = Array2::<f64>::zeros((bs, d));
            let mut yb = Array2::<f64>::zeros((bs, n_classes));
            for (i, &idx) in idxs[offset..end].iter().enumerate() {
                xb.row_mut(i).assign(&x.row(idx));
                yb.row_mut(i).assign(&yh.row(idx));
            }
            // forward
            let logits = xb.dot(&w) + &b;
            let probs = softmax_rows(logits);
            // loss
            let mut batch_loss = 0.0;
            for i in 0..bs {
                for c in 0..n_classes {
                    let p = probs[[i, c]].clamp(1e-9, 1.0);
                    let t = yb[[i, c]];
                    if t > 0.0 { batch_loss -= t * p.ln(); }
                }
            }
            batch_loss /= bs as f64;
            total_loss += batch_loss;
            // gradient
            let diff = &probs - &yb; // (bs, C)
            let grad_w = xb.t().dot(&diff) / (bs as f64); // (d, C)
            let mut grad_b = Array1::<f64>::zeros(n_classes);
            for c in 0..n_classes { grad_b[c] = diff.column(c).sum() / (bs as f64); }
            // update
            if use_hgd {
                let mut k = 0usize;
                for i in 0..d {
                    for c in 0..n_classes {
                        let m = harmonic_mask(grad_w[[i, c]], k, true, true, hgd_gain, hgd_floor);
                        w[[i, c]] -= lr_hgd * m * grad_w[[i, c]];
                        k += 1;
                    }
                }
                for c in 0..n_classes {
                    let m = harmonic_mask(grad_b[c], d * n_classes + c, true, true, hgd_gain, hgd_floor);
                    b[c] -= lr_hgd * m * grad_b[c];
                }
            } else {
                for i in 0..d { for c in 0..n_classes { w[[i, c]] -= lr_sgd * grad_w[[i, c]]; } }
                for c in 0..n_classes { b[c] -= lr_sgd * grad_b[c]; }
            }
            offset = end;
        }
        let acc = accuracy(x, y, &w, &b);
        let method = if use_hgd { "HGD" } else { "SGD" };
        writeln!(csv, "{},{},{:.6},{:.6}", epoch, method, total_loss / ((n + batch - 1) / batch) as f64, acc)?;
    }
    Ok(())
}

fn main() {
    // CLI
    let mut root = PathBuf::from("qa_data/raman");
    let mut epochs: usize = 30;
    let mut batch: usize = 32;
    let mut grid_n: usize = 512;
    let mut gmin: f64 = 0.0;
    let mut gmax: f64 = 4000.0;
    let mut max_per_class: Option<usize> = None;
    let mut opt = String::from("hgd");
    let mut feat_mode = String::from("grid+qa");
    let mut out = PathBuf::from("target/qa_raman/raman_hgd.csv");
    let mut lr_sgd = 0.05f64;
    let mut lr_hgd = 0.1f64; // default 2x
    let mut hgd_gain = 1.8f64;
    let mut hgd_floor = 0.3f64;
    {
        let args: Vec<String> = std::env::args().collect();
        let mut i = 1;
        while i < args.len() {
            match args[i].as_str() {
                "--root" => { i+=1; root = PathBuf::from(&args[i]); }
                "--epochs" => { i+=1; epochs = args[i].parse().unwrap_or(epochs); }
                "--batch-size" => { i+=1; batch = args[i].parse().unwrap_or(batch); }
                "--grid-n" => { i+=1; grid_n = args[i].parse().unwrap_or(grid_n); }
                "--gmin" => { i+=1; gmin = args[i].parse().unwrap_or(gmin); }
                "--gmax" => { i+=1; gmax = args[i].parse().unwrap_or(gmax); }
                "--max-per-class" => { i+=1; let v: usize = args[i].parse().unwrap_or(0); max_per_class = if v>0 { Some(v) } else { None }; }
                "--opt" => { i+=1; opt = args[i].to_lowercase(); }
                "--feat-mode" => { i+=1; feat_mode = args[i].to_lowercase(); }
                "--log-csv" => { i+=1; out = PathBuf::from(&args[i]); }
                "--lr-sgd" => { i+=1; lr_sgd = args[i].parse().unwrap_or(lr_sgd); }
                "--lr-hgd" => { i+=1; lr_hgd = args[i].parse().unwrap_or(lr_hgd); }
                "--hgd-gain" => { i+=1; hgd_gain = args[i].parse().unwrap_or(hgd_gain); }
                "--hgd-floor" => { i+=1; hgd_floor = args[i].parse().unwrap_or(hgd_floor); }
                _ => {}
            }
            i += 1;
        }
    }
    fs::create_dir_all(out.parent().unwrap()).ok();
    println!("Loading Raman data from {}", root.display());
    let (mut x, y, classes) = gather_raman(&root, grid_n, gmin, gmax, max_per_class, &feat_mode);
    if x.nrows() == 0 {
        eprintln!("No spectra found under {}", root.display());
        std::process::exit(1);
    }
    println!("Loaded {} spectra across {} classes: {:?}", x.nrows(), classes.len(), classes);
    // Standardize features
    standardize_inplace(&mut x);
    let use_hgd = opt == "hgd";
    if let Err(e) = train_softmax(
        &x, &y, classes.len(), epochs, batch, lr_sgd, lr_hgd, use_hgd, hgd_gain, hgd_floor, &out,
    ) {
        eprintln!("Failed to train: {}", e);
        std::process::exit(1);
    }
    println!("Wrote {}", out.display());
}
