// QA-PCN prototype: small predictive coding-like network over a graph

use nalgebra::{DMatrix, SymmetricEigen};

#[derive(Clone, Debug)]
pub struct QAPCN {
    pub weights: Vec<f64>,                 // node states (could later be QA tuples)
    pub adjacency: Vec<(usize, usize, f64)>, // edge list (u, v, weight)
    pub theta: f64,                        // phase / monodromy parameter
    pub alpha: f64,                        // node penalty strength
    pub w_star: Vec<f64>,                  // target state
}

impl QAPCN {
    pub fn new(n_nodes: usize, adjacency: Vec<(usize, usize, f64)>, theta: f64, alpha: f64) -> Self {
        Self {
            weights: vec![0.0; n_nodes],
            adjacency,
            theta,
            alpha,
            w_star: vec![0.0; n_nodes],
        }
    }

    pub fn set_target(&mut self, target: Vec<f64>) {
        assert_eq!(target.len(), self.weights.len());
        self.w_star = target;
    }

    /// Construct Laplacian L = D - A
    pub fn laplacian(&self) -> DMatrix<f64> {
        let n = self.weights.len();
        let mut a = DMatrix::<f64>::zeros(n, n);
        for &(u, v, w) in &self.adjacency {
            a[(u, v)] += w;
            a[(v, u)] += w;
        }
        let mut d = DMatrix::<f64>::zeros(n, n);
        for i in 0..n {
            let mut sum = 0.0;
            for j in 0..n {
                sum += a[(i, j)];
            }
            d[(i, i)] = sum;
        }
        d - a
    }

    pub fn laplacian_eigenvalues(&self) -> Vec<f64> {
        let l = self.laplacian();
        let eig = SymmetricEigen::new(l);
        let mut vals = eig.eigenvalues.data.as_vec().clone();
        vals.sort_by(|a, b| a.partial_cmp(b).unwrap());
        vals
    }

    /// Energy: E = 0.5 * (w - w*)^T (alpha I + L) (w - w*)
    pub fn energy(&self) -> f64 {
        let n = self.weights.len();
        let l = self.laplacian();
        let mut e = 0.0;
        for i in 0..n {
            for j in 0..n {
                let m = if i == j { self.alpha } else { 0.0 } + l[(i, j)];
                let di = self.weights[i] - self.w_star[i];
                let dj = self.weights[j] - self.w_star[j];
                e += 0.5 * di * m * dj;
            }
        }
        e
    }

    fn grad(&self) -> Vec<f64> {
        // g = (alpha I + L)(w - w*)
        let n = self.weights.len();
        let l = self.laplacian();
        let mut g = vec![0.0; n];
        for i in 0..n {
            let mut acc = 0.0;
            for j in 0..n {
                let m = if i == j { self.alpha } else { 0.0 } + l[(i, j)];
                acc += m * (self.weights[j] - self.w_star[j]);
            }
            g[i] = acc;
        }
        g
    }

    #[inline]
    fn harmonic_gate(val: f64, idx: usize, theta: f64) -> f64 {
        // Simplified gate: combine cos(theta) with an index-based periodic attenuation
        let phase = (idx as f64 % 24.0) / 24.0; // [0,1)
        let rail = 0.2 + 0.8 * (1.0 - (phase - 0.25).abs().min((phase - 0.75).abs()) * 4.0).clamp(0.0, 1.0);
        let ang = theta.cos().abs();
        let mag = (val.abs() + 1e-9).ln_1p().recip(); // smaller for large |val|
        (rail * ang * mag).clamp(0.1, 1.0)
    }

    pub fn step_sgd(&mut self, lr: f64) {
        let g = self.grad();
        for i in 0..self.weights.len() {
            self.weights[i] -= lr * g[i];
        }
    }

    pub fn step_hgd(&mut self, lr: f64) {
        let g = self.grad();
        for i in 0..self.weights.len() {
            let m = Self::harmonic_gate(g[i], i, self.theta);
            self.weights[i] -= lr * m * g[i];
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pcn_energy_decreases_with_hgd() {
        let n = 6;
        // ring graph
        let mut edges = Vec::new();
        for i in 0..n { edges.push((i, (i+1)%n, 1.0)); }
        let mut pcn = QAPCN::new(n, edges, 0.0, 0.1);
        pcn.set_target(vec![1.0; n]);
        let e0 = pcn.energy();
        for _ in 0..50 { pcn.step_hgd(0.1); }
        let e1 = pcn.energy();
        assert!(e1 <= e0, "PCN energy should not increase after HGD steps");
    }
}
