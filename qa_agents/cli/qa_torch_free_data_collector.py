#!/usr/bin/env python3
"""
Torch-Free QALM Data Collector Agent
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
import time
import hashlib
from dataclasses import dataclass, field
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_agents.cli.cim_qalm_agent import CIMQALMAgent
from qa_rust_ml import RustMLHelper

@dataclass
class DataSource:
    url: str
    title: str
    description: str
    data_type: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)

@dataclass
class CollectedData:
    source: DataSource
    content: str
    qa_tuples: List[Tuple[float, float, float, float]] = field(default_factory=list)
    raw_data: Optional[bytes] = None
    processed_at: float = field(default_factory=time.time)

class TorchFreeDataCollector(CIMQALMAgent):
    """A torch-free data collector that uses the Rust backend."""

    def __init__(self, base_path: Path):
        super().__init__(base_path)
        self.rust_ml_helper = RustMLHelper()
        self.data_dir = base_path / "collected_data"
        self.data_dir.mkdir(exist_ok=True)

    def autonomous_data_collection(self, topics: List[str], max_sources: int = 10) -> Dict[str, Any]:
        """Perform autonomous data collection for given topics"""
        all_collected = []
        all_sources = []

        for topic in topics:
            print(f"Collecting data for topic: {topic}")
            sources = self._discover_data_sources(topic, max_sources // len(topics))
            all_sources.extend(sources)
            collected = self._collect_data(sources)
            all_collected.extend(collected)

        processed_data = self._process_data(all_collected)
        self._save_collected_data(processed_data)

        return {
            'topics': topics,
            'sources_discovered': len(all_sources),
            'data_collected': len(all_collected),
            'data_processed': len(processed_data),
            'data_file': str(self.data_dir / f"collection_{int(time.time())}.json")
        }

    def _discover_data_sources(self, query: str, max_sources: int = 10) -> List[DataSource]:
        """Discover relevant data sources for QALM training from local files"""
        sources = []
        base_path = self.base_path

        # Scan for relevant local files
        patterns = [
            "*.md", "*.txt", "*.py",  # Root level docs and code
            "vault/**/*.md", "vault/**/*.txt",  # Vault documents
            "tasks/**/*.yaml", "tasks/**/*.md",  # Task files
            "projects/**/*.md", "projects/**/*.py",  # Project files
        ]

        for pattern in patterns:
            for file_path in base_path.glob(pattern):
                if file_path.is_file():
                    try:
                        # Read first few lines for description
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            first_lines = f.read(500)  # First 500 chars

                        # Calculate relevance score based on query match
                        relevance = self._calculate_relevance(query, first_lines, str(file_path))

                        if relevance > 0.1:  # Only include somewhat relevant files
                            sources.append(DataSource(
                                url=str(file_path.relative_to(base_path)),
                                title=file_path.stem,
                                description=first_lines[:200] + "..." if len(first_lines) > 200 else first_lines,
                                data_type=file_path.suffix[1:] if file_path.suffix else 'text',
                                relevance_score=relevance,
                                metadata={
                                    'file_path': str(file_path),
                                    'size': file_path.stat().st_size,
                                    'modified': file_path.stat().st_mtime
                                }
                            ))
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
                        continue

        # Sort by relevance and limit
        sources.sort(key=lambda x: x.relevance_score, reverse=True)
        return sources[:max_sources]

    def _calculate_relevance(self, query: str, content: str, file_path: str) -> float:
        """Calculate relevance score for a file based on query"""
        query_lower = query.lower()
        content_lower = content.lower()
        path_lower = file_path.lower()

        score = 0.0

        # Exact query matches in content
        if query_lower in content_lower:
            score += 0.5

        # Query words in content
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())
        word_matches = len(query_words.intersection(content_words))
        score += min(word_matches * 0.1, 0.3)

        # File path relevance
        if query_lower in path_lower:
            score += 0.2

        # File type bonuses
        if file_path.endswith('.md'):
            score += 0.1  # Documentation often relevant
        elif file_path.endswith('.py'):
            score += 0.05  # Code files

        return min(score, 1.0)

    def _collect_data(self, sources: List[DataSource]) -> List[CollectedData]:
        """Collect data from discovered sources"""
        collected = []
        for source in sources:
            try:
                with open(source.metadata['file_path'], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                qa_tuples = self.rust_ml_helper.find_qa_in_text(content)
                collected.append(
                    CollectedData(
                        source=source,
                        content=content,
                        qa_tuples=qa_tuples
                    )
                )
            except Exception as e:
                print(f"Error collecting from {source.url}: {e}")
                continue
        return collected

    def _process_data(self, collected_data: List[CollectedData]) -> List[Dict[str, Any]]:
        """Preprocess data for QALM training"""
        processed_data = []
        for data in collected_data:
            processed = {
                'source': data.source.url,
                'content': data.content,
                'qa_tuples': data.qa_tuples,
                'processed_at': time.time()
            }
            processed_data.append(processed)
        return processed_data

    def _save_collected_data(self, processed_data: List[Dict[str, Any]]) -> None:
        """Save processed data to disk"""
        timestamp = int(time.time())
        filename = self.data_dir / f"collection_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': timestamp,
                'data': processed_data
            }, f, indent=2, ensure_ascii=False)

def create_torch_free_data_collector(base_path: Path) -> TorchFreeDataCollector:
    """Factory function to create data collector agent"""
    return TorchFreeDataCollector(base_path)
