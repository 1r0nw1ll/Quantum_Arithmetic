// ML operations using pure Rust (no PyTorch dependency)
use ndarray::{Array1, Array2};
use rand::Rng;
use rand::SeedableRng;
use rand::rngs::SmallRng;

/// ML helper for basic operations without torch
pub struct MLHelper;

impl MLHelper {
    /// Compute cosine similarity between two vectors
    pub fn cosine_similarity(a: &Array1<f64>, b: &Array1<f64>) -> f64 {
        if a.len() != b.len() {
            return 0.0;
        }

        let dot: f64 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f64 = a.iter().map(|x| x * x).sum::<f64>().sqrt();
        let norm_b: f64 = b.iter().map(|x| x * x).sum::<f64>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            0.0
        } else {
            dot / (norm_a * norm_b)
        }
    }

    /// Simple k-means clustering (placeholder for linfa integration)
    pub fn simple_kmeans(data: &Array2<f64>, k: usize, max_iters: usize) -> Vec<usize> {
        let n_samples = data.nrows();
        let n_features = data.ncols();

        if n_samples == 0 || k == 0 {
            return vec![];
        }

        // Initialize centroids randomly
        // Use a fixed seed for deterministic behavior in tests and reproducible runs
        let mut rng = SmallRng::seed_from_u64(42);
        let mut centroids = Array2::<f64>::zeros((k, n_features));
        for i in 0..k {
            let idx = rng.gen_range(0..n_samples);
            centroids.row_mut(i).assign(&data.row(idx));
        }

        let mut labels = vec![0; n_samples];

        // K-means iterations
        for _ in 0..max_iters {
            // Assign points to nearest centroid
            for i in 0..n_samples {
                let point = data.row(i);
                let mut min_dist = f64::MAX;
                let mut best_cluster = 0;

                for j in 0..k {
                    let centroid = centroids.row(j);
                    let dist: f64 = point
                        .iter()
                        .zip(centroid.iter())
                        .map(|(a, b)| (a - b).powi(2))
                        .sum::<f64>()
                        .sqrt();

                    if dist < min_dist {
                        min_dist = dist;
                        best_cluster = j;
                    }
                }
                labels[i] = best_cluster;
            }

            // Update centroids
            for j in 0..k {
                let cluster_points: Vec<_> = labels
                    .iter()
                    .enumerate()
                    .filter(|(_, &label)| label == j)
                    .map(|(idx, _)| idx)
                    .collect();

                if !cluster_points.is_empty() {
                    for feat in 0..n_features {
                        let sum: f64 = cluster_points.iter().map(|&idx| data[[idx, feat]]).sum();
                        centroids[[j, feat]] = sum / cluster_points.len() as f64;
                    }
                }
            }
        }

        labels
    }

    /// Normalize array to [0, 1] range
    pub fn normalize(arr: &Array1<f64>) -> Array1<f64> {
        let min = arr.iter().cloned().fold(f64::INFINITY, f64::min);
        let max = arr.iter().cloned().fold(f64::NEG_INFINITY, f64::max);

        if (max - min).abs() < 1e-10 {
            return Array1::zeros(arr.len());
        }

        arr.mapv(|x| (x - min) / (max - min))
    }

    /// Compute mean of array
    pub fn mean(arr: &Array1<f64>) -> f64 {
        if arr.is_empty() {
            return 0.0;
        }
        arr.sum() / arr.len() as f64
    }

    /// Compute standard deviation
    pub fn std_dev(arr: &Array1<f64>) -> f64 {
        if arr.len() < 2 {
            return 0.0;
        }

        let mean = Self::mean(arr);
        let variance: f64 =
            arr.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (arr.len() - 1) as f64;

        variance.sqrt()
    }

    /// Generate random QA tuple following closure laws
    pub fn random_qa_tuple() -> (f64, f64, f64, f64) {
        let mut rng = rand::thread_rng();
        let b = rng.gen_range(1.0..10.0);
        let e = rng.gen_range(1.0..10.0);
        let d = b + e;
        let a = e + d;
        (b, e, d, a)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::array;

    #[test]
    fn test_cosine_similarity() {
        let a = array![1.0, 0.0, 0.0];
        let b = array![1.0, 0.0, 0.0];
        let sim = MLHelper::cosine_similarity(&a, &b);
        assert!((sim - 1.0).abs() < 1e-6);

        let c = array![1.0, 0.0, 0.0];
        let d = array![0.0, 1.0, 0.0];
        let sim2 = MLHelper::cosine_similarity(&c, &d);
        assert!(sim2.abs() < 1e-6);
    }

    #[test]
    fn test_normalize() {
        let arr = array![1.0, 2.0, 3.0, 4.0, 5.0];
        let normalized = MLHelper::normalize(&arr);
        assert!((normalized[0] - 0.0).abs() < 1e-6);
        assert!((normalized[4] - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_mean() {
        let arr = array![1.0, 2.0, 3.0, 4.0, 5.0];
        let mean = MLHelper::mean(&arr);
        assert!((mean - 3.0).abs() < 1e-6);
    }

    #[test]
    fn test_std_dev() {
        let arr = array![1.0, 2.0, 3.0, 4.0, 5.0];
        let std = MLHelper::std_dev(&arr);
        assert!(std > 0.0);
    }

    #[test]
    fn test_random_qa_tuple() {
        let (b, e, d, a) = MLHelper::random_qa_tuple();
        // Verify closure laws
        assert!((d - (b + e)).abs() < 1e-6);
        assert!((a - (e + d)).abs() < 1e-6);
    }

    #[test]
    fn test_simple_kmeans() {
        let data = Array2::from_shape_vec(
            (6, 2),
            vec![1.0, 1.0, 1.5, 1.5, 5.0, 5.0, 5.5, 5.5, 9.0, 9.0, 9.5, 9.5],
        )
        .unwrap();

        let labels = MLHelper::simple_kmeans(&data, 3, 10);
        assert_eq!(labels.len(), 6);

        // Points 0,1 should be in same cluster
        // Points 2,3 should be in same cluster
        // Points 4,5 should be in same cluster
        assert_eq!(labels[0], labels[1]);
        assert_eq!(labels[2], labels[3]);
        assert_eq!(labels[4], labels[5]);
    }
}
