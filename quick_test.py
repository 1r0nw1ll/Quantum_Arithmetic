#!/usr/bin/env python3
"""
Quick comparative test for QA vs General LM
"""

import torch
from qa_model_architecture import QALanguageModel, QAConfig
from qa_training_pipeline import QADataset, MathematicalValidationLoss
import torch.nn as nn

def run_quick_test():
    # Small config
    config = QAConfig(
        vocab_size=100,
        hidden_size=32,
        num_hidden_layers=1,
        num_attention_heads=1,
        intermediate_size=64,
        max_position_embeddings=32
    )

    # Test QA mode
    print("=== Testing QA Mode ===")
    qa_dataset = QADataset("test_dataset.json", max_length=16)
    qa_model = QALanguageModel(config)
    qa_optimizer = torch.optim.Adam(qa_model.parameters(), lr=1e-3)
    qa_criterion = nn.CrossEntropyLoss()
    qa_math_loss = MathematicalValidationLoss()

    # One batch
    qa_sample = qa_dataset[0]
    input_ids = qa_sample['input_ids'].unsqueeze(0)
    qa_tuples = qa_sample['qa_tuples'].unsqueeze(0)
    labels = qa_sample['labels'].unsqueeze(0)

    qa_optimizer.zero_grad()
    qa_outputs = qa_model(input_ids=input_ids, qa_tuples=qa_tuples)
    qa_lm_loss = qa_criterion(qa_outputs[0].view(-1, qa_outputs[0].size(-1)), labels.view(-1))
    qa_math_val_loss = qa_math_loss(qa_tuples)
    qa_total_loss = qa_lm_loss + 0.1 * qa_math_val_loss
    qa_total_loss.backward()
    qa_optimizer.step()

    print(".4f")
    print(".4f")

    # Test General LM mode
    print("\n=== Testing General LM Mode ===")
    lm_model = QALanguageModel(config)
    lm_optimizer = torch.optim.Adam(lm_model.parameters(), lr=1e-3)
    lm_criterion = nn.CrossEntropyLoss()

    lm_optimizer.zero_grad()
    lm_outputs = lm_model(input_ids=input_ids, qa_tuples=qa_tuples)
    lm_loss = lm_criterion(lm_outputs[0].view(-1, lm_outputs[0].size(-1)), labels.view(-1))
    lm_loss.backward()
    lm_optimizer.step()

    print(".4f")

    print("\nComparative test completed successfully!")

if __name__ == "__main__":
    run_quick_test()