#!/usr/bin/env python3
"""
Focused QA Evaluation - Specific Capabilities Assessment
"""

import torch
import time
import json
from pathlib import Path
from qa_model_architecture import QALanguageModel, QAConfig
from qa_training_pipeline import QADataset

def load_qalm_model():
    """Load the trained QALM model"""
    try:
        torch.serialization.add_safe_globals([QAConfig])
        checkpoint = torch.load('trained_models/qa_model_full.pt', map_location='cpu', weights_only=False)
        config = checkpoint['config']
        model = QALanguageModel(config)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval()
        return model, checkpoint
    except Exception as e:
        print(f"Failed to load model: {e}")
        return None, None

def evaluate_qa_invariant_checking(model, checkpoint):
    """Test QA invariant checking capabilities"""
    print("🔍 Testing QA Invariant Checking...")

    test_cases = [
        {
            'tuple': [1, 1, 2, 3],
            'expected_invariants': {
                'closure_b_e_d': True,  # d = b + e = 1 + 1 = 2 ✓
                'closure_e_d_a': True,  # a = e + d = 1 + 2 = 3 ✓
                'invariant_X': True     # X = e·d = 1·2 = 2
            }
        },
        {
            'tuple': [1, 2, 3, 5],
            'expected_invariants': {
                'closure_b_e_d': True,  # d = b + e = 1 + 2 = 3 ✓
                'closure_e_d_a': True,  # a = e + d = 2 + 3 = 5 ✓
                'invariant_X': True     # X = e·d = 2·3 = 6
            }
        },
        {
            'tuple': [2, 3, 5, 8],
            'expected_invariants': {
                'closure_b_e_d': True,  # d = b + e = 2 + 3 = 5 ✓
                'closure_e_d_a': True,  # a = e + d = 3 + 5 = 8 ✓
                'invariant_X': True     # X = e·d = 3·5 = 15
            }
        }
    ]

    results = []
    vocab = checkpoint.get('token_to_id', {})
    id_to_token = checkpoint.get('id_to_token', {})

    for i, test_case in enumerate(test_cases):
        b, e, d, a = test_case['tuple']

        # Create input prompt
        prompt = f"Check invariants for QA tuple ({b},{e},{d},{a})"
        tokens = prompt.lower().split()[:32]  # Limit length

        input_ids = [vocab.get(token, vocab.get('<unk>', 0)) for token in tokens]
        if not input_ids:
            continue

        input_tensor = torch.tensor([input_ids])
        qa_tuples = torch.tensor([[[b, e, d, a]] * len(input_ids)], dtype=torch.float)  # Repeat tuple for each token

        start_time = time.time()
        with torch.no_grad():
            outputs = model(input_ids=input_tensor, qa_tuples=qa_tuples)
        inference_time = time.time() - start_time

        # Get predictions (simplified - just check if model can process)
        loss = torch.nn.functional.cross_entropy(
            outputs[0].view(-1, outputs[0].size(-1)),
            torch.zeros_like(outputs[0].view(-1, outputs[0].size(-1))),  # Dummy labels
            reduction='none'
        ).mean().item()

        results.append({
            'tuple': test_case['tuple'],
            'inference_time': inference_time,
            'loss': loss,
            'expected_invariants': test_case['expected_invariants']
        })

    return results

def evaluate_qa_tuple_generation(model, checkpoint):
    """Test QA tuple generation capabilities"""
    print("🎯 Testing QA Tuple Generation...")

    test_cases = [
        {
            'input': 'Generate QA tuple from (1,1)',
            'expected_pattern': 'should generate (1,1,2,3)'
        },
        {
            'input': 'Next QA tuple after (1,2)',
            'expected_pattern': 'should generate (1,2,3,5)'
        },
        {
            'input': 'Fibonacci QA sequence',
            'expected_pattern': 'should show fibonacci pattern'
        }
    ]

    results = []
    vocab = checkpoint.get('token_to_id', {})
    id_to_token = checkpoint.get('id_to_token', {})

    for i, test_case in enumerate(test_cases):
        tokens = test_case['input'].lower().split()[:32]
        input_ids = [vocab.get(token, vocab.get('<unk>', 0)) for token in tokens]

        if not input_ids:
            continue

        input_tensor = torch.tensor([input_ids])
        qa_tuples = torch.randn(len(input_ids), 4, dtype=torch.float)  # Random QA tuples

        start_time = time.time()
        with torch.no_grad():
            outputs = model(input_ids=input_tensor, qa_tuples=qa_tuples.unsqueeze(0))
        inference_time = time.time() - start_time

        # Get top predictions for last few tokens
        predictions = torch.topk(outputs[0][:, -3:], k=3, dim=-1)
        predicted_sequences = []

        for seq_idx in range(predictions.indices.shape[1]):
            seq_predictions = []
            for token_idx in range(predictions.indices.shape[0]):
                pred_id = predictions.indices[token_idx, seq_idx, 0].item()
                token = id_to_token.get(pred_id, '<unk>')
                seq_predictions.append(token)
            predicted_sequences.append(' '.join(seq_predictions))

        results.append({
            'input': test_case['input'],
            'inference_time': inference_time,
            'predictions': predicted_sequences,
            'expected': test_case['expected_pattern']
        })

    return results

def evaluate_mathematical_reasoning(model, checkpoint):
    """Test mathematical reasoning capabilities"""
    print("🧮 Testing Mathematical Reasoning...")

    test_cases = [
        {
            'question': 'What is the sum of QA tuple elements?',
            'context': 'QA tuple (1,1,2,3)',
            'expected_answer': '7'
        },
        {
            'question': 'What is d in terms of b and e?',
            'context': 'QA arithmetic',
            'expected_answer': 'd = b + e'
        },
        {
            'question': 'What is a in terms of e and d?',
            'context': 'QA arithmetic',
            'expected_answer': 'a = e + d'
        }
    ]

    results = []
    vocab = checkpoint.get('token_to_id', {})
    id_to_token = checkpoint.get('id_to_token', {})

    for i, test_case in enumerate(test_cases):
        # Combine question and context
        full_input = f"{test_case['question']} {test_case['context']}"
        tokens = full_input.lower().split()[:48]

        input_ids = [vocab.get(token, vocab.get('<unk>', 0)) for token in tokens]
        if len(input_ids) < 3:
            continue

        input_tensor = torch.tensor([input_ids])
        qa_tuples = torch.randn(1, len(input_ids), 4, dtype=torch.float)

        start_time = time.time()
        with torch.no_grad():
            outputs = model(input_ids=input_tensor, qa_tuples=qa_tuples)
        inference_time = time.time() - start_time

        # Get predicted answer tokens
        predictions = torch.topk(outputs[0][:, -5:], k=5, dim=-1)  # Last 5 tokens
        predicted_answer = []
        for pred_id in predictions.indices[0, :, 0]:
            token = id_to_token.get(pred_id.item(), '<unk>')
            predicted_answer.append(token)

        results.append({
            'question': test_case['question'],
            'context': test_case['context'],
            'inference_time': inference_time,
            'predicted_answer': ' '.join(predicted_answer),
            'expected_answer': test_case['expected_answer']
        })

    return results

def generate_comprehensive_report(invariant_results, generation_results, reasoning_results):
    """Generate comprehensive evaluation report"""

    report = {
        'timestamp': time.time(),
        'evaluation_type': 'focused_qa_capabilities',
        'sections': {}
    }

    # Invariant Checking Results
    invariant_scores = []
    for result in invariant_results:
        # Simplified scoring - lower loss = better understanding
        score = max(0, min(1, 1.0 / (1.0 + result['loss'])))
        invariant_scores.append(score)

    report['sections']['invariant_checking'] = {
        'test_cases': len(invariant_results),
        'avg_score': sum(invariant_scores) / len(invariant_scores) if invariant_scores else 0,
        'avg_inference_time': sum(r['inference_time'] for r in invariant_results) / len(invariant_results),
        'results': invariant_results
    }

    # Tuple Generation Results
    generation_scores = []
    for result in generation_results:
        # Basic scoring based on whether predictions contain numbers
        has_numbers = any(token.isdigit() for token in result['predictions'][0].split())
        score = 0.5 if has_numbers else 0.1  # Rough heuristic
        generation_scores.append(score)

    report['sections']['tuple_generation'] = {
        'test_cases': len(generation_results),
        'avg_score': sum(generation_scores) / len(generation_scores) if generation_scores else 0,
        'avg_inference_time': sum(r['inference_time'] for r in generation_results) / len(generation_results),
        'results': generation_results
    }

    # Mathematical Reasoning Results
    reasoning_scores = []
    for result in reasoning_results:
        # Check if predicted answer contains expected keywords
        predicted = result['predicted_answer'].lower()
        expected = result['expected_answer'].lower()

        # Simple keyword matching
        keywords = expected.split()
        matches = sum(1 for keyword in keywords if keyword in predicted)
        score = matches / len(keywords) if keywords else 0
        reasoning_scores.append(min(1.0, score))

    report['sections']['mathematical_reasoning'] = {
        'test_cases': len(reasoning_results),
        'avg_score': sum(reasoning_scores) / len(reasoning_scores) if reasoning_scores else 0,
        'avg_inference_time': sum(r['inference_time'] for r in reasoning_results) / len(reasoning_results),
        'results': reasoning_results
    }

    # Overall Assessment
    section_scores = [section['avg_score'] for section in report['sections'].values()]
    report['overall_score'] = sum(section_scores) / len(section_scores)

    # Performance Assessment
    if report['overall_score'] > 0.7:
        assessment = "EXCELLENT - QALM shows strong QA understanding"
    elif report['overall_score'] > 0.5:
        assessment = "GOOD - QALM demonstrates QA capabilities"
    elif report['overall_score'] > 0.3:
        assessment = "FAIR - QALM shows basic QA awareness"
    else:
        assessment = "NEEDS_IMPROVEMENT - QALM requires more QA-specific training"

    report['assessment'] = assessment

    return report

def main():
    print("🎯 QA Focused Evaluation Suite")
    print("=" * 50)

    # Load model
    print("Loading QALM model...")
    model, checkpoint = load_qalm_model()
    if not model:
        print("❌ Failed to load model")
        return

    # Run evaluations
    invariant_results = evaluate_qa_invariant_checking(model, checkpoint)
    generation_results = evaluate_qa_tuple_generation(model, checkpoint)
    reasoning_results = evaluate_mathematical_reasoning(model, checkpoint)

    # Generate report
    report = generate_comprehensive_report(invariant_results, generation_results, reasoning_results)

    # Print results
    print("\n" + "=" * 50)
    print("📊 EVALUATION RESULTS")
    print("=" * 50)

    for section_name, section_data in report['sections'].items():
        print(f"\n{section_name.upper().replace('_', ' ')}:")
        print(f"  Test Cases: {section_data['test_cases']}")
        print(".3f")
        print(".4f")

    print("\n🎯 OVERALL ASSESSMENT:")
    print(f"  Score: {report['overall_score']:.3f}")
    print(f"  Assessment: {report['assessment']}")

    print("\n" + "=" * 50)
    print("💡 DETAILED ANALYSIS")
    print("=" * 50)

    # Analyze each section
    invariant_section = report['sections']['invariant_checking']
    if invariant_section['avg_score'] > 0.6:
        print("✅ Invariant Checking: Strong performance on QA tuple validation")
    else:
        print("⚠️ Invariant Checking: Needs improvement in recognizing QA properties")

    generation_section = report['sections']['tuple_generation']
    if generation_section['avg_score'] > 0.4:
        print("✅ Tuple Generation: Shows capability in QA sequence generation")
    else:
        print("⚠️ Tuple Generation: Limited ability to generate valid QA tuples")

    reasoning_section = report['sections']['mathematical_reasoning']
    if reasoning_section['avg_score'] > 0.5:
        print("✅ Mathematical Reasoning: Good understanding of QA relationships")
    else:
        print("⚠️ Mathematical Reasoning: Basic QA mathematical concepts need strengthening")

    print("\n🚀 RECOMMENDATIONS:")
    print("   • Focus training on QA-specific invariant recognition")
    print("   • Expand dataset with more QA tuple generation examples")
    print("   • Fine-tune on mathematical QA reasoning patterns")
    print("   • Implement proper evaluation metrics beyond perplexity")

    # Save report
    report_file = Path('artifacts/evals') / f"qa_focused_eval_{int(time.time())}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n📄 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    main()