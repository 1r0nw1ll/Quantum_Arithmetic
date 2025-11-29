#!/usr/bin/env python3
"""
Test dataset loading times
"""

from qa_training_pipeline import QADataset
import time

print("Testing QA dataset loading...")
start_time = time.time()
qa_dataset = QADataset("qa_data/qa_training_dataset.json", max_length=128)
qa_load_time = time.time() - start_time
print(".3f")
print(f"QA dataset: {len(qa_dataset)} samples")

print("\nTesting LM dataset loading...")
start_time = time.time()
lm_dataset = QADataset("wikitext_train_subset.json", max_length=128)
lm_load_time = time.time() - start_time
print(".3f")
print(f"LM dataset: {len(lm_dataset)} samples")

print("\nDataset loading test completed!")