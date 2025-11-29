#!/usr/bin/env python3
"""
Train QA model only for testing
"""

import torch
import torch.nn as nn
from qa_model_architecture import QALanguageModel, QAConfig
from qa_training_pipeline import QADataset
import time
import os

def create_light_config(vocab_size: int) -> QAConfig:
    """Create lightweight config for faster training"""
    return QAConfig(
        vocab_size=vocab_size,
        hidden_size=64,  # Much smaller
        num_hidden_layers=2,  # Fewer layers
        num_attention_heads=2,
        intermediate_size=128,
        max_position_embeddings=256,
        light_mode=True,  # Enable light mode
        modular_bases=[24],  # Keep minimal
        geometric_dims=2,  # Reduce geometric complexity
    )

def train_qa_only():
    """Train QA model only"""

    print("=== QA Model Training Test ===\n")

    # Load QA dataset
    print("Loading QA dataset...")
    qa_dataset = QADataset("qa_data/qa_training_dataset.json", max_length=128)

    # Create model
    print("Creating QA model...")
    qa_config = create_light_config(len(qa_dataset.vocab))
    qa_model = QALanguageModel(qa_config)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    qa_model.to(device)

    optimizer = torch.optim.AdamW(qa_model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss(ignore_index=qa_dataset.token_to_id.get('<pad>', 0))

    # Training parameters
    num_epochs = 2
    batch_size = 2
    max_batches = 10

    print(f"Training on {device}")
    print(f"QA dataset: {len(qa_dataset)} samples, vocab: {len(qa_dataset.vocab)}")
    print(f"Max batches per epoch: {max_batches}\n")

    # Training loop
    print("=== Training QA Model ===")
    qa_model.train()

    for epoch in range(num_epochs):
        print(f"Epoch {epoch + 1}/{num_epochs}")
        epoch_start = time.time()
        epoch_loss = 0.0
        batch_count = 0

        for i in range(0, len(qa_dataset), batch_size):
            if batch_count >= max_batches:
                break

            batch_start = time.time()

            # Get batch
            batch_samples = [qa_dataset[i + j] for j in range(min(batch_size, len(qa_dataset) - i))]

            # Collate batch
            input_ids = torch.stack([s['input_ids'] for s in batch_samples])
            qa_tuples = torch.stack([s['qa_tuples'] for s in batch_samples])
            labels = torch.stack([s['labels'] for s in batch_samples])

            input_ids = input_ids.to(device)
            qa_tuples = qa_tuples.to(device)
            labels = labels.to(device)

            # Forward pass
            optimizer.zero_grad()
            outputs = qa_model(input_ids=input_ids, qa_tuples=qa_tuples)
            loss = criterion(outputs[0].view(-1, outputs[0].size(-1)), labels.view(-1))

            # Backward pass
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            batch_time = time.time() - batch_start
            batch_count += 1

            print(".3f")

        epoch_time = time.time() - epoch_start
        avg_loss = epoch_loss / batch_count if batch_count > 0 else 0
        print(".3f")

    # Save model
    print("\n=== Saving QA Model ===")
    os.makedirs("trained_models", exist_ok=True)
    qa_model_path = "trained_models/qa_model_full.pt"

    torch.save({
        'model_state_dict': qa_model.state_dict(),
        'config': qa_config,
        'vocab_size': len(qa_dataset.vocab),
        'token_to_id': qa_dataset.token_to_id,
        'id_to_token': qa_dataset.id_to_token
    }, qa_model_path)

    print(f"QA model saved to: {qa_model_path}")
    print("\n✅ QA training completed successfully!")

if __name__ == "__main__":
    train_qa_only()