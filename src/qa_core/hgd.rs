// Harmonic Gradient Descent (HGD) prototype kernel
// Simple, torch-free optimizer for QA tuples guided by mod-24 and mod-9 cycles

use ndarray::{Array1, Array2};

use super::{digital_root, mod24};

/// Simple quadratic objective: L(w) = 0.5 * sum_i lambda_i * (w_i - w*_i)^2
/// Gradient: g_i = lambda_i * (w_i - w*_i)
pub struct QuadObjective {
    /// Target minimizer w*
    pub w_star: Array1<f64>,
    /// Positive diagonal curvature (lambdas)
    pub lambdas: Array1<f64>,
}

impl QuadObjective {
    pub fn new(w_star: Array1<f64>, lambdas: Array1<f64>) -> Self {
        assert_eq!(w_star.len(), lambdas.len());
        Self { w_star, lambdas }
    }

    pub fn loss(&self, w: &Array1<f64>) -> f64 {
        let diff = w - &self.w_star;
        let mut acc = 0.0;
        for i in 0..diff.len() {
            acc += 0.5 * self.lambdas[i] * diff[i] * diff[i];
        }
        acc
    }

    pub fn grad(&self, w: &Array1<f64>) -> Array1<f64> {
        let diff = w - &self.w_star;
        let mut g = diff.clone();
        for i in 0..g.len() {
            g[i] = self.lambdas[i] * diff[i];
        }
        g
    }
}

#[derive(Clone, Copy, Debug)]
pub struct SGDConfig {
    pub lr: f64,
    pub max_steps: usize,
    pub tol: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct HGDConfig {
    pub base_lr: f64,
    pub max_steps: usize,
    pub tol: f64,
    /// Whether to use mod-9 digital-root gating
    pub use_mod9: bool,
    /// Whether to use mod-24 phase guidance
    pub use_mod24: bool,
    /// Scalar gain applied to the harmonic mask to avoid under-stepping
    pub mask_gain: f64,
    /// Minimum mask value after gain (pre-clamp)
    pub mask_floor: f64,
}

#[derive(Debug, Clone)]
pub struct OptimStats {
    pub steps: usize,
    pub loss_start: f64,
    pub loss_end: f64,
    /// Very rough proxy count of arithmetic ops (adds+muls) for comparison only
    pub compute_units: u64,
}

/// Classical SGD loop on the quadratic objective.
pub fn simulate_sgd(obj: &QuadObjective, w0: &Array1<f64>, cfg: SGDConfig) -> (Array1<f64>, OptimStats) {
    let mut w = w0.clone();
    let loss0 = obj.loss(&w);
    let mut compute: u64 = 0; // rough accounting
    let d = w.len() as u64;
    for step in 0..cfg.max_steps {
        // grad: ~ (2 ops per dim)
        let g = obj.grad(&w);
        compute += 2 * d; // approximate
        // update: w -= lr * g  (~2 ops per dim)
        for i in 0..w.len() {
            w[i] -= cfg.lr * g[i];
        }
        compute += 2 * d;
        let loss = obj.loss(&w);
        // loss: ~2 ops per dim
        compute += 2 * d;
        if loss <= cfg.tol {
            return (
                w,
                OptimStats {
                    steps: step + 1,
                    loss_start: loss0,
                    loss_end: loss,
                    compute_units: compute,
                },
            );
        }
    }
    let loss = obj.loss(&w);
    compute += 2 * d;
    (
        w,
        OptimStats {
            steps: cfg.max_steps,
            loss_start: loss0,
            loss_end: loss,
            compute_units: compute,
        },
    )
}

/// Harmonic mask in [0, 1] that attenuates gradient components based on resonance
/// Simplified version combining mod-24 and mod-9 cues from the QA design.
fn harmonic_mask(val: f64, idx: usize, use_mod9: bool, use_mod24: bool, gain: f64, floor: f64) -> f64 {
    let mut m = 1.0;
    if use_mod24 {
        // Phase by index to emulate positional resonance
        // Favor phases near 0, 6, 12, 18 (quarters of 24)
        let phase = mod24((idx as f64 + 1.0) * 1.0);
        let dist = ((phase - 0.0).abs())
            .min((phase - 6.0).abs())
            .min((phase - 12.0).abs())
            .min((phase - 18.0).abs());
        // Map distance [0, 6] → weight [1, ~0.2]
        let w = 1.0 - (dist / 6.0) * 0.8;
        m *= w.max(0.2);
    }
    if use_mod9 {
        // digital root gating: prefer residues {1,3,6,9}
        // Scale input to emphasize magnitude patterning
        let scaled = (val * 1e3).round() as i64;
        let dr = digital_root(scaled);
        let w = match dr {
            1 | 3 | 6 | 9 => 1.0,
            2 | 4 | 5 | 7 | 8 => 0.5,
            _ => 0.5,
        };
        m *= w;
    }
    // Apply gain and floor, then clamp to a sane upper bound to avoid blowups
    let boosted = (m * gain).max(floor);
    boosted.min(2.0)
}

/// HGD update: w_{t+1} = w_t - lr * (mask ⊙ grad)
fn hgd_update(w: &mut Array1<f64>, g: &Array1<f64>, base_lr: f64, use_mod9: bool, use_mod24: bool) {
    for i in 0..w.len() {
        let m = harmonic_mask(g[i], i, use_mod9, use_mod24, 1.0, 0.0);
        w[i] -= base_lr * m * g[i];
    }
}

/// HGD simulation on the quadratic objective.
pub fn simulate_hgd(obj: &QuadObjective, w0: &Array1<f64>, cfg: HGDConfig) -> (Array1<f64>, OptimStats) {
    let mut w = w0.clone();
    let loss0 = obj.loss(&w);
    let mut compute: u64 = 0;
    let d = w.len() as u64;
    for step in 0..cfg.max_steps {
        let g = obj.grad(&w);
        compute += 2 * d; // grad approx
        // mask + update (~ 3 ops + gating per dim). Count modestly higher cost than SGD.
        for i in 0..w.len() {
            // mask uses a couple of ops; count ~6 per dim lumped
            let m = harmonic_mask(g[i], i, cfg.use_mod9, cfg.use_mod24, cfg.mask_gain, cfg.mask_floor);
            w[i] -= cfg.base_lr * m * g[i];
        }
        compute += 6 * d;
        let loss = obj.loss(&w);
        compute += 2 * d; // loss approx
        if loss <= cfg.tol {
            return (
                w,
                OptimStats {
                    steps: step + 1,
                    loss_start: loss0,
                    loss_end: loss,
                    compute_units: compute,
                },
            );
        }
    }
    let loss = obj.loss(&w);
    compute += 2 * d;
    (
        w,
        OptimStats {
            steps: cfg.max_steps,
            loss_start: loss0,
            loss_end: loss,
            compute_units: compute,
        },
    )
}

/// One SGD step on the quadratic objective (exposed for microbenchmarks)
pub fn sgd_step(obj: &QuadObjective, w: &mut Array1<f64>, lr: f64) {
    let g = obj.grad(w);
    for i in 0..w.len() {
        w[i] -= lr * g[i];
    }
}

/// One HGD step on the quadratic objective (exposed for microbenchmarks)
pub fn hgd_step(obj: &QuadObjective, w: &mut Array1<f64>, base_lr: f64, use_mod9: bool, use_mod24: bool) {
    let g = obj.grad(w);
    for i in 0..w.len() {
        let m = harmonic_mask(g[i], i, use_mod9, use_mod24, 1.0, 0.0);
        w[i] -= base_lr * m * g[i];
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::array;

    #[test]
    fn test_quadratic_minimization_sgd_vs_hgd() {
        let w_star = array![1.0, -2.0, 0.5, 3.0, -1.0, 2.5, 0.0, -0.5];
        let lambdas = array![1.0, 0.5, 2.0, 1.5, 0.1, 3.0, 0.8, 0.2];
        let obj = QuadObjective::new(w_star.clone(), lambdas);
        let w0 = Array1::zeros(w_star.len());

        let (w_sgd, s_sgd) = simulate_sgd(
            &obj,
            &w0,
            SGDConfig {
                lr: 0.2,
                max_steps: 500,
                tol: 1e-8,
            },
        );
        let (w_hgd, s_hgd) = simulate_hgd(
            &obj,
            &w0,
            HGDConfig {
                base_lr: 0.2,
                max_steps: 500,
                tol: 1e-8,
                use_mod9: true,
                use_mod24: true,
                mask_gain: 1.5,
                mask_floor: 0.2,
            },
        );

        // Both should converge close to optimum
        assert!(obj.loss(&w_sgd) < 1e-5);
        assert!(obj.loss(&w_hgd) < 1e-5);

        // Both solutions near optimum (loss-based)
        assert!(obj.loss(&w_sgd) < 1e-6);
        assert!(obj.loss(&w_hgd) < 1e-6);
    }
}
