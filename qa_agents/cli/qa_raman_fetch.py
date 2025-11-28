#!/usr/bin/env python3
"""
QA Raman Fetch Wrapper — uses the torch-free data collector to discover spectral/Raman resources
from the local workspace and reports any local dataset paths for downstream agents.
"""
import json
from pathlib import Path
from qa_agents.cli.qa_torch_free_data_collector import create_torch_free_data_collector


def main():
    base = Path('.')
    agent = create_torch_free_data_collector(base)
    topics = [
        'raman', 'spectral', 'hyperspectral', 'spectrum', 'peaks',
        'Raman spectroscopy', 'materials', 'classification'
    ]
    result = agent.autonomous_data_collection(topics, max_sources=20)
    print(json.dumps(result, indent=2))

    # Check for local datasets
    paths = []
    for p in [Path('datasets/raman'), Path('multimodal_data')]:
        if p.exists():
            paths.append(str(p.resolve()))
    print(json.dumps({'dataset_paths': paths}, indent=2))


if __name__ == '__main__':
    main()

