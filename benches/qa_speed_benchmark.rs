use criterion::{criterion_group, criterion_main, BatchSize, Criterion};
use ndarray::Array1;
use qa_lab_rs::qa_core::hgd::{hgd_step, sgd_step, QuadObjective};

fn build_obj(dim: usize) -> (QuadObjective, Array1<f64>) {
    let w_star = Array1::from_iter((0..dim).map(|i| ((i as f64) * 0.25).sin()));
    let lambdas = Array1::from_iter((0..dim).map(|i| 0.2 + 0.1 * ((i as f64) % 7.0)));
    (QuadObjective::new(w_star, lambdas), Array1::zeros(dim))
}

fn bench_steps(c: &mut Criterion) {
    // 1D
    c.bench_function("sgd_step_1d", |b| {
        b.iter_batched(
            || build_obj(1),
            |(obj, mut w)| sgd_step(&obj, &mut w, 0.2),
            BatchSize::SmallInput,
        )
    });
    c.bench_function("hgd_step_1d", |b| {
        b.iter_batched(
            || build_obj(1),
            |(obj, mut w)| hgd_step(&obj, &mut w, 0.2, true, true),
            BatchSize::SmallInput,
        )
    });

    // 10D
    c.bench_function("sgd_step_10d", |b| {
        b.iter_batched(
            || build_obj(10),
            |(obj, mut w)| sgd_step(&obj, &mut w, 0.2),
            BatchSize::SmallInput,
        )
    });
    c.bench_function("hgd_step_10d", |b| {
        b.iter_batched(
            || build_obj(10),
            |(obj, mut w)| hgd_step(&obj, &mut w, 0.2, true, true),
            BatchSize::SmallInput,
        )
    });
}

criterion_group!(benches, bench_steps);
criterion_main!(benches);

