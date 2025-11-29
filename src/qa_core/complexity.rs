// Complexity estimators for attention vs QA-Fourier style transforms

#[derive(Clone, Copy, Debug)]
pub struct AttnParams {
    pub n_tokens: usize,
    pub d_model: usize,
    pub n_heads: usize,
}

#[derive(Clone, Copy, Debug)]
pub struct QAFourierParams {
    pub n_tokens: usize,
    pub d_model: usize,
}

/// Dense attention: O(N^2 d) dot-products + softmax + mixing
pub fn ops_dense_attention(p: AttnParams) -> u128 {
    let n = p.n_tokens as u128;
    let d = p.d_model as u128;
    let h = p.n_heads as u128;
    // very rough: QK^T (n^2 d) + AV (n^2 d)
    2 * n * n * d * h
}

/// FlashAttention-like: bandwidth-optimized, closer to O(N d) per head for blocks
pub fn ops_flash_attention(p: AttnParams, block: usize) -> u128 {
    let n = p.n_tokens as u128;
    let d = p.d_model as u128;
    let h = p.n_heads as u128;
    let b = block.max(1) as u128;
    // rough scaling: (N/B) blocks × (B d) × N per head
    (n / b) * (b * d) * (n / b) * h
}

/// QA-Fourier: O(N log N) per feature using integer ops
pub fn ops_qa_fourier(p: QAFourierParams) -> u128 {
    let n = p.n_tokens as u128;
    let d = p.d_model as u128;
    let logn = ((p.n_tokens as f64).log2().ceil() as u128).max(1);
    n * logn * d
}

