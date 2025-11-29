// QA Invariants computation and validation
// Canonical formulas from QA_CANONICAL_INVARIANTS.md

use crate::qa_core::QABundle;
use ndarray::Array1;

/// Collection of QA invariants for a given tuple
#[derive(Debug, Clone)]
pub struct QAInvariants {
    // Primary invariants
    pub j: f64, // perigee: b * d
    pub k: f64, // apogee: d * a
    pub x: f64, // half focal distance: e * d

    // Secondary invariants
    pub w: f64, // X + K (equilateral triangle side)
    pub y: f64, // a² - d² (Eisenstein connection)
    pub z: f64, // e² + K

    // Triangle sides
    pub c: f64, // focal separation: 2 * X
    pub f: f64, // altitude: b * a
    pub g: f64, // hypotenuse: e² + d²
}

impl QAInvariants {
    /// Extract invariants from QA bundle
    pub fn from_bundle(bundle: &QABundle) -> Self {
        Self {
            j: bundle.j,
            k: bundle.k,
            x: bundle.x,
            w: bundle.w,
            y: bundle.y,
            z: bundle.z,
            c: bundle.c,
            f: bundle.f,
            g: bundle.g,
        }
    }

    /// Convert invariants to array for numerical operations
    pub fn to_array(&self) -> Array1<f64> {
        Array1::from_vec(vec![
            self.j, self.k, self.x, self.w, self.y, self.z, self.c, self.f, self.g,
        ])
    }

    /// Compute "harmonic index" - composite metric of QA coherence
    /// HI = E8_alignment × exp(-0.1 × loss)
    pub fn harmonic_index(&self, e8_alignment: f64, loss: f64) -> f64 {
        e8_alignment * (-0.1 * loss).exp()
    }
}

/// E8 root system utilities
pub struct E8Alignment;

impl E8Alignment {
    /// Compute cosine similarity between QA projection and E8 roots
    /// Returns alignment score in [0, 1]
    pub fn compute(qa_vector: &Array1<f64>, e8_roots: &[Array1<f64>]) -> f64 {
        if e8_roots.is_empty() {
            return 0.0;
        }

        let mut max_similarity = 0.0;

        for root in e8_roots {
            let similarity = Self::cosine_similarity(qa_vector, root);
            if similarity > max_similarity {
                max_similarity = similarity;
            }
        }

        // Normalize to [0, 1]
        (max_similarity + 1.0) / 2.0
    }

    /// Cosine similarity between two vectors
    fn cosine_similarity(a: &Array1<f64>, b: &Array1<f64>) -> f64 {
        if a.len() != b.len() {
            return 0.0;
        }

        let dot_product: f64 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f64 = a.iter().map(|x| x * x).sum::<f64>().sqrt();
        let norm_b: f64 = b.iter().map(|x| x * x).sum::<f64>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            return 0.0;
        }

        dot_product / (norm_a * norm_b)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::qa_core::QABundle;

    #[test]
    fn test_invariants_extraction() {
        let bundle = QABundle::new(1.0, 2.0);
        let inv = QAInvariants::from_bundle(&bundle);

        assert_eq!(inv.j, 3.0);
        assert_eq!(inv.k, 15.0);
        assert_eq!(inv.x, 6.0);
        assert_eq!(inv.w, 21.0);
        assert_eq!(inv.y, 16.0);
        assert_eq!(inv.z, 19.0);
    }

    #[test]
    fn test_cosine_similarity() {
        let a = Array1::from_vec(vec![1.0, 0.0, 0.0]);
        let b = Array1::from_vec(vec![1.0, 0.0, 0.0]);
        let sim = E8Alignment::cosine_similarity(&a, &b);
        assert!((sim - 1.0).abs() < 1e-6);

        let c = Array1::from_vec(vec![1.0, 0.0, 0.0]);
        let d = Array1::from_vec(vec![0.0, 1.0, 0.0]);
        let sim2 = E8Alignment::cosine_similarity(&c, &d);
        assert!(sim2.abs() < 1e-6); // Orthogonal vectors
    }

    #[test]
    fn test_harmonic_index() {
        let bundle = QABundle::new(1.0, 2.0);
        let inv = QAInvariants::from_bundle(&bundle);

        let hi = inv.harmonic_index(0.8, 0.5);
        // HI = 0.8 × exp(-0.1 × 0.5) = 0.8 × exp(-0.05) ≈ 0.761
        assert!((hi - 0.761).abs() < 0.01);
    }
}
