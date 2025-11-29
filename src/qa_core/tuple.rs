// QA Tuple data structures
// Represents the fundamental (b, e, d, a) tuple with closure laws

use ndarray::Array1;

/// Core QA tuple with closure constraints:
/// - d = b + e (first closure law)
/// - a = e + d (second closure law)
#[derive(Debug, Clone, PartialEq)]
pub struct QATuple {
    pub b: f64,
    pub e: f64,
    pub d: f64,
    pub a: f64,
}

impl QATuple {
    /// Create a new QA tuple, enforcing closure constraints
    pub fn new(b: f64, e: f64) -> Self {
        let d = b + e;
        let a = e + d;
        Self { b, e, d, a }
    }

    /// Create from explicit values (validates constraints)
    pub fn from_values(b: f64, e: f64, d: f64, a: f64) -> Result<Self, String> {
        let expected_d = b + e;
        let expected_a = e + d;

        const EPSILON: f64 = 1e-6;

        if (d - expected_d).abs() > EPSILON {
            return Err(format!(
                "Closure constraint violated: d = {} but expected {} (b + e)",
                d, expected_d
            ));
        }

        if (a - expected_a).abs() > EPSILON {
            return Err(format!(
                "Closure constraint violated: a = {} but expected {} (e + d)",
                a, expected_a
            ));
        }

        Ok(Self { b, e, d, a })
    }

    /// Validate closure constraints
    pub fn is_valid(&self) -> bool {
        const EPSILON: f64 = 1e-6;
        let d_valid = (self.d - (self.b + self.e)).abs() < EPSILON;
        let a_valid = (self.a - (self.e + self.d)).abs() < EPSILON;
        d_valid && a_valid
    }

    /// Convert to array for numerical operations
    pub fn to_array(&self) -> Array1<f64> {
        Array1::from_vec(vec![self.b, self.e, self.d, self.a])
    }

    /// Create from array
    pub fn from_array(arr: &Array1<f64>) -> Result<Self, String> {
        if arr.len() != 4 {
            return Err(format!("Expected 4 elements, got {}", arr.len()));
        }
        Self::from_values(arr[0], arr[1], arr[2], arr[3])
    }
}

/// Extended QA bundle including invariants and triangle sides
#[derive(Debug, Clone)]
pub struct QABundle {
    /// Base tuple
    pub tuple: QATuple,

    /// Primary invariants
    pub j: f64, // perigee: b * d
    pub k: f64, // apogee: d * a
    pub x: f64, // half focal distance: e * d

    /// Secondary invariants
    pub w: f64, // X + K (equilateral triangle side)
    pub y: f64, // a² - d² (Eisenstein connection)
    pub z: f64, // e² + K

    /// Triangle sides
    pub c: f64, // focal separation: 2 * X
    pub f: f64, // altitude: b * a
    pub g: f64, // hypotenuse: e² + d²
}

impl QABundle {
    /// Create bundle from QA tuple, computing all invariants
    pub fn from_tuple(tuple: QATuple) -> Self {
        let b = tuple.b;
        let e = tuple.e;
        let d = tuple.d;
        let a = tuple.a;

        // Primary invariants (validated formulas from QA_CANONICAL_INVARIANTS.md)
        let j = b * d; // perigee
        let k = d * a; // apogee
        let x = e * d; // half focal distance

        // Secondary invariants
        let w = x + k; // equilateral triangle side
        let y = a.powi(2) - d.powi(2); // Eisenstein connection
        let z = e.powi(2) + k;

        // Triangle sides
        let c = 2.0 * x; // focal separation
        let f = b * a; // altitude
        let g = e.powi(2) + d.powi(2); // hypotenuse

        Self {
            tuple,
            j,
            k,
            x,
            w,
            y,
            z,
            c,
            f,
            g,
        }
    }

    /// Create from base (b, e) pair
    pub fn new(b: f64, e: f64) -> Self {
        Self::from_tuple(QATuple::new(b, e))
    }

    /// Get E8 projection vector (8D representation for alignment)
    /// Projects 4D QA tuple into 8D space for E8 root system alignment
    pub fn e8_projection(&self) -> Array1<f64> {
        let t = &self.tuple;
        Array1::from_vec(vec![t.b, t.e, t.d, t.a, self.j, self.k, self.x, self.w])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_qa_tuple_closure() {
        // Test Grant's LRT: (1, 2, 3, 5)
        let tuple = QATuple::new(1.0, 2.0);
        assert_eq!(tuple.d, 3.0);
        assert_eq!(tuple.a, 5.0);
        assert!(tuple.is_valid());
    }

    #[test]
    fn test_qa_tuple_satellite() {
        // Test Satellite Family: (3, 5, 8, 13)
        let tuple = QATuple::new(3.0, 5.0);
        assert_eq!(tuple.d, 8.0);
        assert_eq!(tuple.a, 13.0);
        assert!(tuple.is_valid());
    }

    #[test]
    fn test_qa_tuple_singularity() {
        // Test Singularity: (9, 9, 18, 27)
        let tuple = QATuple::new(9.0, 9.0);
        assert_eq!(tuple.d, 18.0);
        assert_eq!(tuple.a, 27.0);
        assert!(tuple.is_valid());
    }

    #[test]
    fn test_qa_bundle_invariants() {
        // Test invariant computation for (1, 2, 3, 5)
        let bundle = QABundle::new(1.0, 2.0);

        // Primary invariants
        assert_eq!(bundle.j, 3.0); // 1 * 3
        assert_eq!(bundle.k, 15.0); // 3 * 5
        assert_eq!(bundle.x, 6.0); // 2 * 3

        // Secondary invariants
        assert_eq!(bundle.w, 21.0); // 6 + 15
        assert_eq!(bundle.y, 16.0); // 5² - 3² = 25 - 9
        assert_eq!(bundle.z, 19.0); // 2² + 15 = 4 + 15

        // Triangle sides
        assert_eq!(bundle.c, 12.0); // 2 * 6
        assert_eq!(bundle.f, 5.0); // 1 * 5
        assert_eq!(bundle.g, 13.0); // 2² + 3² = 4 + 9
    }

    #[test]
    fn test_invalid_tuple() {
        // Should fail - doesn't satisfy closure
        let result = QATuple::from_values(1.0, 2.0, 4.0, 5.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_e8_projection() {
        let bundle = QABundle::new(1.0, 2.0);
        let proj = bundle.e8_projection();
        assert_eq!(proj.len(), 8);
        assert_eq!(proj[0], 1.0); // b
        assert_eq!(proj[1], 2.0); // e
        assert_eq!(proj[2], 3.0); // d
        assert_eq!(proj[3], 5.0); // a
        assert_eq!(proj[4], 3.0); // J
        assert_eq!(proj[5], 15.0); // K
        assert_eq!(proj[6], 6.0); // X
        assert_eq!(proj[7], 21.0); // W
    }
}
