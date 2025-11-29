#!/usr/bin/env python3
"""
Debug first batch processing
"""

from qa_training_pipeline import create_training_pipeline
import time

print("Creating QA trainer...")
qa_trainer = create_training_pipeline(
    data_path="qa_data/qa_training_dataset.json",
    num_epochs=1,
    batch_size=1,
    general_lm=False
)

print("Getting first batch...")
start_time = time.time()
batch_iter = iter(qa_trainer.train_loader)
first_batch = next(batch_iter)
batch_time = time.time() - start_time
print(".3f")

print("Processing first batch...")
start_time = time.time()
try:
    input_ids = first_batch['input_ids'].to(qa_trainer.device)
    attention_mask = first_batch['attention_mask'].to(qa_trainer.device)
    qa_tuples = first_batch['qa_tuples'].to(qa_trainer.device)
    labels = first_batch['labels'].to(qa_trainer.device)

    print("Forward pass...")
    forward_start = time.time()
    outputs = qa_trainer.model(
        input_ids=input_ids,
        qa_tuples=qa_tuples,
        attention_mask=attention_mask
    )
    forward_time = time.time() - forward_start
    print(".3f")

    print("Loss computation...")
    loss_start = time.time()
    lm_logits = outputs[0]
    lm_loss = qa_trainer.lm_criterion(
        lm_logits.view(-1, lm_logits.size(-1)),
        labels.view(-1)
    )
    loss_time = time.time() - loss_start
    print(".3f")

    print("First batch processed successfully!")
    print(f"LM Loss: {lm_loss.item():.4f}")

except Exception as e:
    print(f"Error processing batch: {e}")
    import traceback
    traceback.print_exc()