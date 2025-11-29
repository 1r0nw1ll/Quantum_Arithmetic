#!/usr/bin/env python3
"""
Debug trainer initialization
"""

from qa_training_pipeline import create_training_pipeline

print("Creating QA trainer...")
try:
    qa_trainer = create_training_pipeline(
        data_path="qa_data/qa_training_dataset.json",
        num_epochs=1,
        batch_size=1,
        general_lm=False
    )
    print("QA trainer created successfully")
except Exception as e:
    print(f"QA trainer creation failed: {e}")
    import traceback
    traceback.print_exc()

print("\nCreating LM trainer...")
try:
    lm_trainer = create_training_pipeline(
        data_path="wikitext_train.json",
        num_epochs=1,
        batch_size=1,
        general_lm=True
    )
    print("LM trainer created successfully")
except Exception as e:
    print(f"LM trainer creation failed: {e}")
    import traceback
    traceback.print_exc()