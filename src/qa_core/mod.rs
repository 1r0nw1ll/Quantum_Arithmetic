// Core QA mathematical framework
// Port of qa_jepa_encoder.py core concepts to Rust

mod encoder;
pub mod hgd;
pub mod invariants; // Made public for E8Alignment access
pub mod pcn;
pub mod jepa;
pub mod complexity;
mod tuple;

pub use encoder::QAEncoder;
pub use invariants::QAInvariants;
pub use tuple::{QABundle, QATuple};
pub use hgd::*;

/// Modular arithmetic operations for QA system
pub fn mod24(x: f64) -> f64 {
    let result = x % 24.0;
    if result < 0.0 {
        result + 24.0
    } else {
        result
    }
}

/// Digital root computation (mod 9 reduction)
pub fn digital_root(x: i64) -> i64 {
    let mut n = x.abs();
    while n >= 10 {
        n = n
            .to_string()
            .chars()
            .filter_map(|c| c.to_digit(10))
            .sum::<u32>() as i64;
    }
    if n == 0 {
        9
    } else {
        n
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mod24() {
        assert_eq!(mod24(25.0), 1.0);
        assert_eq!(mod24(-1.0), 23.0);
        assert_eq!(mod24(24.0), 0.0);
    }

    #[test]
    fn test_digital_root() {
        assert_eq!(digital_root(1234), 1); // 1+2+3+4=10, 1+0=1
        assert_eq!(digital_root(999), 9); // 9+9+9=27, 2+7=9
        assert_eq!(digital_root(123), 6); // 1+2+3=6
    }
}
