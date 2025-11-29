// Data collection utilities - pure Rust, no torch dependency
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataSource {
    pub url: String,
    pub source_type: String,
    pub relevance_score: f64,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectedData {
    pub source: DataSource,
    pub content: String,
    pub timestamp: String,
    pub qa_tuples: Vec<(f64, f64, f64, f64)>,
}

/// Data collector that works without PyTorch
pub struct DataCollector {
    pub sources: Vec<DataSource>,
}

impl DataCollector {
    pub fn new() -> Self {
        Self {
            sources: Vec::new(),
        }
    }

    /// Add a data source for collection
    pub fn add_source(&mut self, url: String, source_type: String, relevance: f64) {
        let mut metadata = HashMap::new();
        metadata.insert("status".to_string(), "pending".to_string());

        self.sources.push(DataSource {
            url,
            source_type,
            relevance_score: relevance,
            metadata,
        });
    }

    /// Simulate data collection (placeholder - real implementation would fetch URLs)
    pub fn collect(&self) -> Vec<CollectedData> {
        let mut results = Vec::new();

        for source in &self.sources {
            // Placeholder: In real implementation, would fetch from URL
            let data = CollectedData {
                source: source.clone(),
                content: format!("Simulated data from {}", source.url),
                timestamp: chrono::Utc::now().to_rfc3339(),
                qa_tuples: vec![(1.0, 2.0, 3.0, 5.0)], // Example QA tuple
            };
            results.push(data);
        }

        results
    }

    /// Extract QA tuples from raw data (simple pattern matching)
    pub fn extract_qa_patterns(text: &str) -> Vec<(f64, f64, f64, f64)> {
        let mut tuples = Vec::new();

        // Simple pattern: look for sequences of 4 numbers
        // In real implementation, would use NLP or regex patterns
        let words: Vec<&str> = text.split_whitespace().collect();

        for window in words.windows(4) {
            if let (Ok(b), Ok(e), Ok(d), Ok(a)) = (
                window[0].parse::<f64>(),
                window[1].parse::<f64>(),
                window[2].parse::<f64>(),
                window[3].parse::<f64>(),
            ) {
                // Validate QA closure: d = b + e, a = e + d
                if (d - (b + e)).abs() < 0.01 && (a - (e + d)).abs() < 0.01 {
                    tuples.push((b, e, d, a));
                }
            }
        }

        tuples
    }
}

impl Default for DataCollector {
    fn default() -> Self {
        Self::new()
    }
}

// Add chrono dependency for timestamps
use chrono;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_data_collector_creation() {
        let collector = DataCollector::new();
        assert_eq!(collector.sources.len(), 0);
    }

    #[test]
    fn test_add_source() {
        let mut collector = DataCollector::new();
        collector.add_source("https://example.com".to_string(), "arxiv".to_string(), 0.9);
        assert_eq!(collector.sources.len(), 1);
        assert_eq!(collector.sources[0].relevance_score, 0.9);
    }

    #[test]
    fn test_extract_qa_patterns() {
        let text = "The sequence 1.0 2.0 3.0 5.0 demonstrates closure";
        let patterns = DataCollector::extract_qa_patterns(text);
        assert_eq!(patterns.len(), 1);
        assert_eq!(patterns[0], (1.0, 2.0, 3.0, 5.0));
    }

    #[test]
    fn test_invalid_qa_pattern() {
        let text = "Numbers 1.0 2.0 4.0 5.0 don't follow closure";
        let patterns = DataCollector::extract_qa_patterns(text);
        assert_eq!(patterns.len(), 0); // Should reject invalid closure
    }
}
