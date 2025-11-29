#!/usr/bin/env python3
"""
Create a smaller subset of WikiText for faster training
"""

import json

# Load the full WikiText dataset
with open('wikitext_train.json', 'r') as f:
    data = json.load(f)

# Take only the first 100 texts
subset_data = {
    'texts': data['texts'][:100]
}

# Save the subset
with open('wikitext_train_subset.json', 'w') as f:
    json.dump(subset_data, f)

print(f"Created subset with {len(subset_data['texts'])} texts")