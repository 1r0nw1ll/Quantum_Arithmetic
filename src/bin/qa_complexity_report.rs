// Complexity report for attention vs QA-Fourier

use qa_lab_rs::qa_core::complexity::{ops_dense_attention, ops_flash_attention, ops_qa_fourier, AttnParams, QAFourierParams};

fn main() {
    let ns = [128usize, 256, 512, 1024];
    let ds = [64usize, 128, 256];
    let heads = [4usize, 8];
    let block = 128usize;

    println!("Complexity Report (ops, rough order)");
    println!("N,d,heads,dense_attn,flash_attn(block={}),qa_fourier", block);
    for &n in &ns {
        for &d in &ds {
            for &h in &heads {
                let pa = AttnParams { n_tokens: n, d_model: d, n_heads: h };
                let pq = QAFourierParams { n_tokens: n, d_model: d };
                let a_dense = ops_dense_attention(pa);
                let a_flash = ops_flash_attention(pa, block);
                let a_qaf = ops_qa_fourier(pq);
                println!("{},{},{},{},{},{}", n, d, h, a_dense, a_flash, a_qaf);
            }
        }
    }
}

