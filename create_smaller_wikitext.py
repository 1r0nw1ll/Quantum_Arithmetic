#!/usr/bin/env python3
"""
Create a much smaller subset of WikiText for faster training
"""

import json

# Load the full WikiText dataset
with open('wikitext_train.json', 'r') as f:
    data = json.load(f)

# Take only the first 50 texts
subset_data = {
    'texts': data['texts'][:50]
}

# Save the subset
with open('wikitext_train_small.json', 'w') as f:
    json.dump(subset_data, f)

print(f"Created subset with {len(subset_data['texts'])} texts")