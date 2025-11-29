#!/usr/bin/env python3
"""
Quick test for QA training pipeline
"""

import torch
from qa_model_architecture import QALanguageModel, QAConfig
from qa_training_pipeline import QADataset

def test_model():
    # Create small config
    config = QAConfig(
        vocab_size=1000,
        hidden_size=64,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=128,
        max_position_embeddings=128
    )

    model = QALanguageModel(config)
    print(f"Model created: {model}")

    # Test forward pass
    batch_size = 2
    seq_len = 10
    vocab_size = 1000

    input_ids = torch.randint(0, vocab_size, (batch_size, seq_len))
    qa_tuples = torch.randn(batch_size, seq_len, 4)
    attention_mask = torch.ones(batch_size, seq_len)

    try:
        outputs = model(input_ids=input_ids, qa_tuples=qa_tuples, attention_mask=attention_mask)
        print(f"Forward pass successful: outputs shape {outputs[0].shape}")
    except Exception as e:
        print(f"Forward pass failed: {e}")
        return False

    return True

def test_dataset():
    try:
        dataset = QADataset("qa_data/qa_training_dataset.json", max_length=64)
        print(f"Dataset loaded: {len(dataset)} samples, vocab size {len(dataset.vocab)}")

        # Test one sample
        sample = dataset[0]
        print(f"Sample keys: {sample.keys()}")
        print(f"Input shape: {sample['input_ids'].shape}")
        return True
    except Exception as e:
        print(f"Dataset loading failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing model...")
    model_ok = test_model()

    print("\nTesting dataset...")
    dataset_ok = test_dataset()

    if model_ok and dataset_ok:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed!")