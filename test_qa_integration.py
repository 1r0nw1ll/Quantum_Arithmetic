"""
test_qa_integration.py - Integration tests for QA lab modules

Validates:
1. All modules can be imported
2. QA tuple interfaces are consistent
3. Cross-module data flows work
4. Key invariants (J, K, X, G) computed consistently
"""

import sys
import traceback
from typing import Dict, List, Tuple, Any

# Test results
RESULTS: List[Dict[str, Any]] = []


def test(name: str):
    """Decorator for test functions."""
    def decorator(fn):
        def wrapper():
            try:
                result = fn()
                RESULTS.append({"name": name, "status": "PASS", "result": result})
                return True
            except Exception as e:
                RESULTS.append({"name": name, "status": "FAIL", "error": str(e)})
                traceback.print_exc()
                return False
        return wrapper
    return decorator


# ============ IMPORT TESTS ============

@test("Import qa_star_agent")
def test_import_star_agent():
    from qa_star_agent import QAStarAgent, QATuple, QATriangle
    return {"classes": ["QAStarAgent", "QATuple", "QATriangle"]}


@test("Import qa_wow_physics_loss")
def test_import_wow_physics():
    from qa_wow_physics_loss import QAWoWPhysicsLoss
    return {"classes": ["QAWoWPhysicsLoss"]}


@test("Import qa_raman_memory")
def test_import_raman():
    from qa_raman_memory import QARamanMemory, simulate_hankel_rotor
    return {"classes": ["QARamanMemory", "simulate_hankel_rotor"]}


@test("Import qa_co_scientist")
def test_import_coscientist():
    from qa_co_scientist import QACoScientist, Hypothesis
    return {"classes": ["QACoScientist", "Hypothesis"]}


@test("Import qa_neural_rg")
def test_import_neural_rg():
    from qa_neural_rg import QARGTracker, RGFlowState
    return {"classes": ["QARGTracker", "RGFlowState"]}


@test("Import qa_real_neural_maxent")
def test_import_maxent():
    from qa_real_neural_maxent import QAMaxEntModel, QANeuralMaxEnt
    return {"classes": ["QAMaxEntModel", "QANeuralMaxEnt"]}


@test("Import qa_hopfield_qann")
def test_import_hopfield():
    from qa_hopfield_qann import QAHopfieldNetwork, ModernQAHopfield
    return {"classes": ["QAHopfieldNetwork", "ModernQAHopfield"]}


@test("Import qa_toroid_sumproduct_batch")
def test_import_toroid():
    from qa_toroid_sumproduct_batch import classify_set, batch_classify
    return {"functions": ["classify_set", "batch_classify"]}


@test("Import qa_tidar_decoder")
def test_import_tidar():
    from qa_tidar_decoder import QATiDARDecoder
    return {"classes": ["QATiDARDecoder"]}


# ============ QA TUPLE CONSISTENCY TESTS ============

@test("QA tuple constraint: d = b + e")
def test_qa_constraint_d():
    from qa_star_agent import QATuple
    qa = QATuple(b=3.0, e=5.0)
    assert abs(qa.d - (qa.b + qa.e)) < 1e-9, f"d={qa.d}, b+e={qa.b + qa.e}"
    return {"b": 3.0, "e": 5.0, "d": qa.d}


@test("QA tuple constraint: a = e + d")
def test_qa_constraint_a():
    from qa_star_agent import QATuple
    qa = QATuple(b=3.0, e=5.0)
    assert abs(qa.a - (qa.e + qa.d)) < 1e-9, f"a={qa.a}, e+d={qa.e + qa.d}"
    return {"e": 5.0, "d": qa.d, "a": qa.a}


@test("QA invariants computed correctly")
def test_qa_invariants():
    from qa_star_agent import QATuple, QATriangle
    qa = QATuple(b=1.0, e=2.0)  # d=3, a=5
    tri = QATriangle(qa)

    # J = b*d = 1*3 = 3
    assert abs(tri.J - 3.0) < 1e-9, f"J={tri.J}"
    # K = d*a = 3*5 = 15
    assert abs(tri.K - 15.0) < 1e-9, f"K={tri.K}"
    # X = e*d = 2*3 = 6
    assert abs(tri.X - 6.0) < 1e-9, f"X={tri.X}"
    # C = 2*e*d = 2*2*3 = 12
    assert abs(tri.C - 12.0) < 1e-9, f"C={tri.C}"
    # F = b*a = 1*5 = 5
    assert abs(tri.F - 5.0) < 1e-9, f"F={tri.F}"
    # G = e² + d² = 4 + 9 = 13
    assert abs(tri.G - 13.0) < 1e-9, f"G={tri.G}"

    return {"J": 3, "K": 15, "X": 6, "C": 12, "F": 5, "G": 13}


# ============ CROSS-MODULE INTEGRATION TESTS ============

@test("Star Agent produces valid QA tuples")
def test_star_agent_integration():
    from qa_star_agent import QAStarAgent, QAStarConfig

    cfg = QAStarConfig(num_branches=2, max_depth=3, rng_seed=42)
    agent = QAStarAgent(config=cfg)
    result = agent.solve("test task")

    best = result["best_branch"]
    qa = best.qa

    # Verify constraints
    assert abs(qa.d - (qa.b + qa.e)) < 1e-9
    assert abs(qa.a - (qa.e + qa.d)) < 1e-9

    return {"branches": len(result["branches"]), "best_score": best.score}


@test("Raman memory computes metrics")
def test_raman_integration():
    from qa_raman_memory import QARamanMemory, simulate_hankel_rotor, QARamanConfig

    config = QARamanConfig(allowed_mod9=[1, 2, 3, 5, 8])
    memory = QARamanMemory(target_tuple=(1, 2, 3, 5), config=config)

    amps = simulate_hankel_rotor((1, 2, 3, 5), [0, 0], noise_level=0.1)
    metrics = memory.qa_metrics(amps)

    assert 0 <= metrics["eta"] <= 1
    assert 0 <= metrics["noise_frac"] <= 1

    return {"eta": round(metrics["eta"], 3), "noise": round(metrics["noise_frac"], 3)}


@test("Co-Scientist evolves hypotheses")
def test_coscientist_integration():
    from qa_co_scientist import QACoScientist

    scientist = QACoScientist(pool_size=20, rng_seed=42)
    scientist.seed_hypothesis("Test hypothesis", confidence=0.7)

    offspring = scientist.evolve(n_offspring=5)
    rankings = scientist.rank_hypotheses(top_n=3)

    assert len(rankings) > 0
    assert all("qa_tuple" in r for r in rankings)

    return {"offspring": len(offspring), "top_score": round(rankings[0]["total_score"], 3)}


@test("Neural RG tracks flow")
def test_neural_rg_integration():
    import numpy as np
    from qa_neural_rg import QARGTracker

    tracker = QARGTracker(b_scale=10.0, e_scale=5.0)

    for epoch in range(10):
        weights = np.random.randn(50, 50) * (1 - epoch * 0.05)
        loss = 2.0 * np.exp(-0.1 * epoch)
        tracker.record_state(epoch, weights, loss, loss * 0.5)

    summary = tracker.flow_summary()

    assert summary["n_steps"] == 10
    assert summary["final_loss"] < summary["initial_loss"]

    return {"steps": 10, "loss_ratio": round(summary["final_loss"] / summary["initial_loss"], 3)}


@test("Hopfield retrieves patterns")
def test_hopfield_integration():
    import numpy as np
    from qa_hopfield_qann import QAHopfieldNetwork

    np.random.seed(42)
    net = QAHopfieldNetwork(n_neurons=50, qa_weight=0.1)

    # Store patterns
    patterns = [np.sign(np.random.randn(50)) for _ in range(3)]
    for p in patterns:
        net.store_pattern(p)

    # Retrieve from corrupted probe
    probe = patterns[1].copy()
    probe[:10] *= -1

    retrieved, info = net.retrieve(probe, max_iters=20)
    idx, overlap = net.find_nearest_pattern(retrieved)

    assert idx == 1  # Should retrieve pattern 1

    return {"matched": idx, "overlap": round(overlap, 3)}


@test("Torus knot classification works")
def test_toroid_integration():
    from qa_toroid_sumproduct_batch import classify_set

    # AP should have high additive bias
    ap = [2, 4, 6, 8, 10]
    result = classify_set(ap)

    assert "knot" in result
    assert "bias" in result
    assert result["bias"]["add"] > 0.5

    return {"knot": result["knot"], "add_bias": round(result["bias"]["add"], 3)}


# ============ RUN ALL TESTS ============

def run_all_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("QA Lab Integration Tests")
    print("=" * 60)

    tests = [
        test_import_star_agent,
        test_import_wow_physics,
        test_import_raman,
        test_import_coscientist,
        test_import_neural_rg,
        test_import_maxent,
        test_import_hopfield,
        test_import_toroid,
        test_import_tidar,
        test_qa_constraint_d,
        test_qa_constraint_a,
        test_qa_invariants,
        test_star_agent_integration,
        test_raman_integration,
        test_coscientist_integration,
        test_neural_rg_integration,
        test_hopfield_integration,
        test_toroid_integration,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        success = test_fn()
        if success:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    for r in RESULTS:
        status = "✓" if r["status"] == "PASS" else "✗"
        print(f"  {status} {r['name']}")
        if r["status"] == "PASS" and "result" in r:
            print(f"      {r['result']}")
        elif r["status"] == "FAIL":
            print(f"      ERROR: {r.get('error', 'Unknown')}")

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    sys.exit(0 if failed == 0 else 1)
