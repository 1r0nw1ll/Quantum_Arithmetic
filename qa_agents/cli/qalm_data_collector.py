#!/usr/bin/env python3
"""
QALM Data Collector Agent v1.0
Autonomous data collection and retrieval agent for QALM training enhancement.

Capabilities:
- Academic paper and dataset discovery
- Web scraping for training data
- Data validation and preprocessing
- Integration with QALM training pipeline
- Autonomous data foraging operations

Integration with QA lab for enhanced QALM self-improvement.
"""

import torch
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Set
from urllib.parse import urljoin, urlparse
import time
import hashlib
from dataclasses import dataclass, field
import threading
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys

# Add the qa_lab directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_agents.cli.cim_qalm_agent import CIMQALMAgent


@dataclass
class DataSource:
    """Represents a discovered data source"""
    url: str
    title: str
    description: str
    data_type: str  # 'paper', 'dataset', 'code', 'tutorial'
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: float = field(default_factory=time.time)


@dataclass
class CollectedData:
    """Represents collected training data"""
    source: DataSource
    content: str
    qa_pairs: List[Tuple[str, str]] = field(default_factory=list)
    raw_data: Optional[bytes] = None
    processed_at: float = field(default_factory=time.time)


class DataForagingEngine:
    """Autonomous data discovery and collection"""

    def __init__(self, qalm_agent: CIMQALMAgent):
        self.qalm = qalm_agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'QALM-DataCollector/1.0 (Research Enhancement Agent)'
        })

        # Known data sources
        self.academic_sources = [
            'https://arxiv.org',
            'https://paperswithcode.com',
            'https://huggingface.co/datasets',
            'https://www.kaggle.com/datasets',
            'https://datasetsearch.research.google.com',
            'https://zenodo.org',
            'https://figshare.com'
        ]

        self.collected_data: List[CollectedData] = []
        self.visited_urls: Set[str] = set()

    def discover_data_sources(self, query: str, max_sources: int = 10) -> List[DataSource]:
        """Discover relevant data sources for QALM training"""
        sources = []

        # Search academic repositories
        for base_url in self.academic_sources:
            try:
                search_results = self._search_repository(base_url, query)
                sources.extend(search_results)
                if len(sources) >= max_sources:
                    break
            except Exception as e:
                print(f"Error searching {base_url}: {e}")
                continue

        # Rank by relevance
        sources.sort(key=lambda x: x.relevance_score, reverse=True)
        return sources[:max_sources]

    def _search_repository(self, base_url: str, query: str) -> List[DataSource]:
        """Search a specific repository for relevant content"""
        sources = []

        if 'arxiv.org' in base_url:
            return self._search_arxiv(query)
        elif 'paperswithcode.com' in base_url:
            return self._search_paperswithcode(query)
        elif 'huggingface.co' in base_url:
            return self._search_huggingface(query)
        elif 'kaggle.com' in base_url:
            return self._search_kaggle(query)

        return sources

    def _search_arxiv(self, query: str) -> List[DataSource]:
        """Search arXiv for relevant papers"""
        sources = []
        search_url = f"https://arxiv.org/search/?query={query}&searchtype=all"

        try:
            response = self.session.get(search_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            for result in soup.find_all('li', class_='arxiv-result')[:5]:
                title_elem = result.find('p', class_='title')
                abstract_elem = result.find('p', class_='abstract')

                if title_elem and abstract_elem:
                    title = title_elem.get_text().strip()
                    abstract = abstract_elem.get_text().strip()

                    # Calculate relevance
                    relevance = self._calculate_relevance(query, title + " " + abstract)

                    if relevance > 0.3:  # Minimum relevance threshold
                        link = result.find('a', href=True)
                        if link:
                            url = urljoin("https://arxiv.org", link['href'])

                            sources.append(DataSource(
                                url=url,
                                title=title,
                                description=abstract[:500],
                                data_type='paper',
                                relevance_score=relevance,
                                metadata={'abstract': abstract}
                            ))

        except Exception as e:
            print(f"ArXiv search error: {e}")

        return sources

    def _search_paperswithcode(self, query: str) -> List[DataSource]:
        """Search Papers with Code"""
        sources = []
        search_url = f"https://paperswithcode.com/search?q={query}"

        try:
            response = self.session.get(search_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')

            for paper in soup.find_all('div', class_='paper-card')[:3]:
                title_elem = paper.find('h1') or paper.find('h2')
                desc_elem = paper.find('p', class_='item-strip-abstract')

                if title_elem:
                    title = title_elem.get_text().strip()
                    description = desc_elem.get_text().strip() if desc_elem else ""

                    relevance = self._calculate_relevance(query, title + " " + description)

                    if relevance > 0.3:
                        link = paper.find('a', href=True)
                        if link:
                            url = urljoin("https://paperswithcode.com", link['href'])

                            sources.append(DataSource(
                                url=url,
                                title=title,
                                description=description[:500],
                                data_type='paper',
                                relevance_score=relevance
                            ))

        except Exception as e:
            print(f"PapersWithCode search error: {e}")

        return sources

    def _search_huggingface(self, query: str) -> List[DataSource]:
        """Search Hugging Face datasets"""
        sources = []
        search_url = f"https://huggingface.co/api/datasets?search={query}&limit=5"

        try:
            response = self.session.get(search_url, timeout=10)
            datasets = response.json()

            for dataset in datasets:
                title = dataset.get('id', '')
                description = dataset.get('description', '') or dataset.get('cardData', {}).get('description', '')

                relevance = self._calculate_relevance(query, title + " " + description)

                if relevance > 0.3:
                    url = f"https://huggingface.co/datasets/{title}"

                    sources.append(DataSource(
                        url=url,
                        title=title.replace('/', ' - '),
                        description=description[:500],
                        data_type='dataset',
                        relevance_score=relevance,
                        metadata={'downloads': dataset.get('downloads', 0)}
                    ))

        except Exception as e:
            print(f"HuggingFace search error: {e}")

        return sources

    def _search_kaggle(self, query: str) -> List[DataSource]:
        """Search Kaggle datasets"""
        sources = []
        search_url = f"https://www.kaggle.com/api/v1/datasets/list?search={query}&size=5"

        try:
            response = self.session.get(search_url, timeout=10)
            datasets = response.json()

            for dataset in datasets:
                title = dataset.get('title', '')
                description = dataset.get('description', '') or dataset.get('subtitle', '')

                relevance = self._calculate_relevance(query, title + " " + description)

                if relevance > 0.3:
                    url = dataset.get('url', '')

                    sources.append(DataSource(
                        url=url,
                        title=title,
                        description=description[:500],
                        data_type='dataset',
                        relevance_score=relevance,
                        metadata={'size': dataset.get('totalBytes', 0)}
                    ))

        except Exception as e:
            print(f"Kaggle search error: {e}")

        return sources

    def _calculate_relevance(self, query: str, text: str) -> float:
        """Calculate relevance score between query and text"""
        query_terms = set(query.lower().split())
        text_terms = set(text.lower().split())

        # Jaccard similarity
        intersection = len(query_terms & text_terms)
        union = len(query_terms | text_terms)

        if union == 0:
            return 0.0

        return intersection / union

    def collect_data(self, sources: List[DataSource]) -> List[CollectedData]:
        """Collect data from discovered sources"""
        collected = []

        for source in sources:
            if source.url in self.visited_urls:
                continue

            try:
                print(f"Collecting data from: {source.title}")
                data = self._collect_from_source(source)
                if data:
                    collected.append(data)
                    self.visited_urls.add(source.url)

            except Exception as e:
                print(f"Error collecting from {source.url}: {e}")
                continue

        return collected

    def _collect_from_source(self, source: DataSource) -> Optional[CollectedData]:
        """Collect data from a specific source"""
        try:
            response = self.session.get(source.url, timeout=15)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')

            if 'application/pdf' in content_type:
                # PDF content - would need pdf parsing library
                return CollectedData(
                    source=source,
                    content="PDF content detected - parsing not implemented",
                    raw_data=response.content
                )

            elif 'text/html' in content_type:
                # HTML content - parse and extract
                soup = BeautifulSoup(response.content, 'html.parser')

                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()

                text_content = soup.get_text(separator=' ', strip=True)

                # Extract QA pairs if possible
                qa_pairs = self._extract_qa_pairs(text_content)

                return CollectedData(
                    source=source,
                    content=text_content,
                    qa_pairs=qa_pairs
                )

            else:
                # Other content types
                return CollectedData(
                    source=source,
                    content=f"Content type: {content_type}",
                    raw_data=response.content
                )

        except Exception as e:
            print(f"Collection error for {source.url}: {e}")
            return None

    def _extract_qa_pairs(self, text: str) -> List[Tuple[str, str]]:
        """Extract potential Q&A pairs from text"""
        qa_pairs = []

        # Simple pattern matching for Q&A sections
        lines = text.split('\n')
        current_question = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for question patterns
            if re.match(r'^(Q|Question|What|How|Why|When|Where|Who):', line, re.IGNORECASE):
                current_question = line
            elif current_question and re.match(r'^(A|Answer):', line, re.IGNORECASE):
                qa_pairs.append((current_question, line))
                current_question = None

        return qa_pairs


class DataValidationEngine:
    """Validate and preprocess collected data"""

    def __init__(self, qalm_agent: CIMQALMAgent):
        self.qalm = qalm_agent

    def validate_data(self, collected_data: List[CollectedData]) -> List[CollectedData]:
        """Validate collected data quality"""
        validated = []

        for data in collected_data:
            if self._is_quality_data(data):
                validated.append(data)

        return validated

    def _is_quality_data(self, data: CollectedData) -> bool:
        """Check if data meets quality standards"""
        # Basic quality checks
        if len(data.content) < 100:  # Too short
            return False

        if len(data.qa_pairs) == 0 and data.source.data_type == 'paper':  # No Q&A for paper
            return False

        # Use QALM to assess relevance
        relevance_prompt = f"Assess if this content is relevant for QA learning: {data.content[:500]}"
        assessment = self.qalm.generate_response(relevance_prompt)

        return 'relevant' in assessment.lower() or 'useful' in assessment.lower()

    def preprocess_for_training(self, data: CollectedData) -> Dict[str, Any]:
        """Preprocess data for QALM training"""
        processed = {
            'source': data.source.url,
            'content': data.content,
            'qa_pairs': data.qa_pairs,
            'processed_at': time.time()
        }

        # Generate additional QA pairs using QALM
        if len(data.qa_pairs) < 5:
            generated_pairs = self._generate_qa_pairs(data.content)
            processed['generated_qa_pairs'] = generated_pairs

        return processed

    def _generate_qa_pairs(self, content: str) -> List[Tuple[str, str]]:
        """Generate QA pairs from content using QALM"""
        pairs = []

        # Split content into chunks
        chunks = [content[i:i+1000] for i in range(0, len(content), 800)]

        for chunk in chunks[:3]:  # Limit to first 3 chunks
            prompt = f"Generate 2-3 Q&A pairs from this text: {chunk[:500]}"
            response = self.qalm.generate_response(prompt)

            # Parse response into Q&A pairs (simplified)
            lines = response.split('\n')
            current_q = None
            for line in lines:
                if line.startswith('Q:') or line.startswith('Question:'):
                    current_q = line[2:].strip()
                elif current_q and (line.startswith('A:') or line.startswith('Answer:')):
                    pairs.append((current_q, line[2:].strip()))
                    current_q = None

        return pairs


class QALMDataCollectorAgent(CIMQALMAgent):
    """QALM Data Collector Agent for autonomous data foraging"""

    def __init__(self, base_path: Path):
        super().__init__(base_path)

        # Initialize data collection components
        self.foraging_engine = DataForagingEngine(self)
        self.validation_engine = DataValidationEngine(self)

        # Data storage
        self.data_dir = base_path / "collected_data"
        self.data_dir.mkdir(exist_ok=True)

        # Thread pool for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=4)

    def autonomous_data_collection(self, topics: List[str], max_sources: int = 10) -> Dict[str, Any]:
        """Perform autonomous data collection for given topics"""
        all_collected = []
        all_sources = []

        for topic in topics:
            print(f"Collecting data for topic: {topic}")

            # Discover sources
            sources = self.foraging_engine.discover_data_sources(topic, max_sources // len(topics))
            all_sources.extend(sources)

            # Collect data
            collected = self.foraging_engine.collect_data(sources)
            all_collected.extend(collected)

        # Validate and preprocess
        validated = self.validation_engine.validate_data(all_collected)
        processed_data = []

        for data in validated:
            processed = self.validation_engine.preprocess_for_training(data)
            processed_data.append(processed)

        # Save to disk
        self._save_collected_data(processed_data)

        return {
            'topics': topics,
            'sources_discovered': len(all_sources),
            'data_collected': len(all_collected),
            'data_validated': len(validated),
            'data_processed': len(processed_data),
            'data_file': str(self.data_dir / f"collection_{int(time.time())}.json")
        }

    def _save_collected_data(self, processed_data: List[Dict[str, Any]]) -> None:
        """Save processed data to disk"""
        timestamp = int(time.time())
        filename = self.data_dir / f"collection_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': timestamp,
                'data': processed_data
            }, f, indent=2, ensure_ascii=False)

    def enhance_qalm_training(self, data_file: Optional[str] = None) -> Dict[str, Any]:
        """Use collected data to enhance QALM training"""
        if not data_file:
            # Find latest collection
            collections = list(self.data_dir.glob("collection_*.json"))
            if not collections:
                return {"error": "No collected data found"}

            data_file = str(max(collections, key=lambda x: x.stat().st_mtime))

        # Load collected data
        with open(data_file, 'r', encoding='utf-8') as f:
            collection = json.load(f)

        # Process for training
        training_data = []
        for item in collection['data']:
            # Convert to training format
            qa_pairs = item.get('qa_pairs', []) + item.get('generated_qa_pairs', [])

            for question, answer in qa_pairs:
                training_data.append({
                    'input': question,
                    'output': answer,
                    'source': item['source']
                })

        return {
            'data_file': data_file,
            'training_samples': len(training_data),
            'training_data': training_data[:100]  # Limit for preview
        }

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected data"""
        collections = list(self.data_dir.glob("collection_*.json"))

        total_samples = 0
        sources = set()

        for collection_file in collections:
            try:
                with open(collection_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for item in data['data']:
                    total_samples += len(item.get('qa_pairs', []))
                    total_samples += len(item.get('generated_qa_pairs', []))
                    sources.add(item['source'])

            except Exception as e:
                print(f"Error reading {collection_file}: {e}")

        return {
            'total_collections': len(collections),
            'total_training_samples': total_samples,
            'unique_sources': len(sources),
            'data_directory': str(self.data_dir)
        }


def create_qalm_data_collector(base_path: Path) -> QALMDataCollectorAgent:
    """Factory function to create data collector agent"""
    return QALMDataCollectorAgent(base_path)


# CLI interface for QA lab integration
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='QALM Data Collector Agent v1.0')
    parser.add_argument('--base-path', type=str, default='.',
                        help='Base path for agent data')
    parser.add_argument('--command', choices=['collect', 'enhance', 'stats'],
                        default='stats', help='Command to execute')
    parser.add_argument('--topics', nargs='+', help='Topics to collect data for')
    parser.add_argument('--max-sources', type=int, default=10, help='Maximum sources to discover')

    args = parser.parse_args()

    base_path = Path(args.base_path)
    agent = create_qalm_data_collector(base_path)

    if args.command == 'collect' and args.topics:
        # Autonomous data collection
        result = agent.autonomous_data_collection(args.topics, args.max_sources)
        print(json.dumps(result, indent=2))

    elif args.command == 'enhance':
        # Enhance QALM training
        result = agent.enhance_qalm_training()
        print(json.dumps(result, indent=2))

    elif args.command == 'stats':
        # Show collection statistics
        stats = agent.get_collection_stats()
        print("QALM Data Collector Statistics:")
        print(json.dumps(stats, indent=2))

    else:
        print("QALM Data Collector Agent v1.0")
        print("Use --help for usage information")
