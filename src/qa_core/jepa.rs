// QA-JEPA prototype: simple energy model (torch-free)

use ndarray::{Array1, Array2};

#[derive(Clone, Debug)]
pub struct QAJEPA {
    pub dim_x: usize,
    pub dim_z: usize,
    pub w_enc: Array2<f64>, // (dim_z, dim_x)
    pub w_pred: Array2<f64>, // (dim_z, dim_z)
}

impl QAJEPA {
    pub fn new(dim_x: usize, dim_z: usize) -> Self {
        let mut w_enc_full = Array2::<f64>::zeros((dim_z, dim_x));
        // place identity block
        let min = dim_x.min(dim_z);
        for i in 0..min {
            w_enc_full[(i, i)] = 1.0;
        }
        let mut w_pred = Array2::<f64>::zeros((dim_z, dim_z));
        for i in 0..dim_z {
            w_pred[(i, i)] = 1.0;
        }
        Self { dim_x, dim_z, w_enc: w_enc_full, w_pred }
    }

    pub fn encode(&self, x: &Array1<f64>) -> Array1<f64> {
        let mut z = Array1::<f64>::zeros(self.dim_z);
        // z = W_enc x
        for i in 0..self.dim_z {
            let mut acc = 0.0;
            for j in 0..self.dim_x {
                acc += self.w_enc[(i, j)] * x[j];
            }
            z[i] = acc;
        }
        z
    }

    pub fn predict(&self, z: &Array1<f64>) -> Array1<f64> {
        let mut zh = Array1::<f64>::zeros(self.dim_z);
        for i in 0..self.dim_z {
            let mut acc = 0.0;
            for j in 0..self.dim_z {
                acc += self.w_pred[(i, j)] * z[j];
            }
            zh[i] = acc;
        }
        zh
    }

    /// Energy E = 0.5 ||z - z_hat||^2
    pub fn energy(&self, z: &Array1<f64>, z_hat: &Array1<f64>) -> f64 {
        let mut e = 0.0;
        for i in 0..self.dim_z {
            let d = z[i] - z_hat[i];
            e += 0.5 * d * d;
        }
        e
    }

    /// Gradient of E wrt W_pred: dE = (z_hat - z) z^T
    pub fn grad_w_pred(&self, z: &Array1<f64>, z_hat: &Array1<f64>) -> Array2<f64> {
        let mut g = Array2::<f64>::zeros((self.dim_z, self.dim_z));
        for i in 0..self.dim_z {
            let di = z_hat[i] - z[i];
            for j in 0..self.dim_z {
                g[(i, j)] = di * z[j];
            }
        }
        g
    }

    pub fn sgd_step_pred(&mut self, g: &Array2<f64>, lr: f64) {
        for i in 0..self.dim_z {
            for j in 0..self.dim_z {
                self.w_pred[(i, j)] -= lr * g[(i, j)];
            }
        }
    }

    fn harmonic_gate(val: f64, idx: usize) -> f64 {
        // simple attenuation by periodic index and magnitude
        let phase = (idx as f64 % 24.0) / 24.0;
        let rail = 0.4 + 0.6 * (1.0 - (phase - 0.5).abs() * 2.0).clamp(0.0, 1.0);
        let mag = (val.abs() + 1e-9).ln_1p().recip().clamp(0.2, 1.0);
        rail * mag
    }

    pub fn hgd_step_pred(&mut self, g: &Array2<f64>, lr: f64) {
        for i in 0..self.dim_z {
            for j in 0..self.dim_z {
                let idx = i * self.dim_z + j;
                let m = Self::harmonic_gate(g[(i, j)], idx);
                self.w_pred[(i, j)] -= lr * m * g[(i, j)];
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn jepa_energy_decreases_over_epochs_hgd() {
        let dim_x = 8;
        let dim_z = 6;
        let mut model = QAJEPA::new(dim_x, dim_z);
        // simple dataset
        let mut data = Vec::new();
        for t in 0..64 {
            let mut x = Array1::<f64>::zeros(dim_x);
            for i in 0..dim_x {
                x[i] = ((t as f64) * 0.05 * (i as f64 + 1.0)).sin();
            }
            data.push(x);
        }
        // measure initial avg energy
        let mut e0 = 0.0;
        for x in &data {
            let z = model.encode(x);
            let zh = model.predict(&z);
            e0 += model.energy(&z, &zh);
        }
        e0 /= data.len() as f64;

        // run a few small HGD updates on predictor
        let lr = 0.02;
        for _ in 0..10 {
            let mut g = Array2::<f64>::zeros((dim_z, dim_z));
            for x in &data {
                let z = model.encode(x);
                let zh = model.predict(&z);
                let gi = model.grad_w_pred(&z, &zh);
                for i in 0..dim_z {
                    for j in 0..dim_z {
                        g[(i, j)] += gi[(i, j)] / (data.len() as f64);
                    }
                }
            }
            model.hgd_step_pred(&g, lr);
        }

        let mut e1 = 0.0;
        for x in &data {
            let z = model.encode(x);
            let zh = model.predict(&z);
            e1 += model.energy(&z, &zh);
        }
        e1 /= data.len() as f64;

        assert!(e1 <= e0, "JEPA energy should not increase after HGD training");
    }
}
