#!/usr/bin/env python3
"""
QA AlphaSynthesis - Cross-Paper Hypothesis Engine
Performs cross-paper reasoning and generates testable QA hypotheses.

This agent reads ingested papers and experiment results, identifies conceptual
connections, and generates hypothesis tasks linking multiple domains through
QA modular arithmetic framework.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set
from collections import defaultdict

# Add parent to path
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import yaml
    YAML_OK = True
except ImportError:
    YAML_OK = False
    yaml = None


class AlphaSynthesis:
    """Cross-paper reasoning and hypothesis generation"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.ingestion_dir = self.base_dir / "artifacts" / "ingestion"
        self.evals_dir = self.base_dir / "artifacts" / "evals"
        self.tasks_dir = self.base_dir / "tasks"
        self.inbox = self.tasks_dir / "inbox"
        self.logs_dir = self.base_dir / "logs"
        self.inbox.mkdir(parents=True, exist_ok=True)

        # QA-specific concepts to detect
        self.qa_concepts = {
            'modular_arithmetic': ['mod', 'modulo', 'modular', 'residue', 'congruence'],
            'tuples': ['tuple', 'quadruple', 'beda', '(b,e,d,a)', 'right triangle'],
            'e8': ['e8', 'exceptional', 'root system', 'lie algebra', 'e_8'],
            'harmonic': ['harmonic', 'resonance', 'frequency', 'oscillation'],
            'gradient_descent': ['gradient', 'descent', 'optimizer', 'sgd', 'hgd'],
            'quantum': ['quantum', 'entanglement', 'superposition', 'tunneling'],
            'vision': ['jepa', 'vision', 'image', 'convolutional', 'cnn'],
            'compilation': ['jit', 'compiler', 'optimization', 'compilation'],
            'statistical_physics': ['statistical mechanics', 'boltzmann', 'partition', 'entropy'],
            'memory': ['memory', 'raman', 'storage', 'retrieval'],
        }

    def load_ingestion_summaries(self) -> List[Dict[str, Any]]:
        """Load ingestion artifact analysis files"""
        summaries = []

        if not self.ingestion_dir.exists():
            return summaries

        # Load analysis markdown files
        for analysis_file in self.ingestion_dir.glob("*_ANALYSIS.md"):
            try:
                content = analysis_file.read_text(encoding='utf-8')

                # Extract paper name
                paper_name = analysis_file.stem.replace('_ANALYSIS', '')

                # Detect concepts in content
                concepts = self.detect_concepts(content.lower())

                summaries.append({
                    'id': paper_name,
                    'file': str(analysis_file),
                    'content_preview': content[:500],
                    'concepts': concepts,
                    'word_count': len(content.split()),
                })
            except Exception as e:
                print(f"  ⚠️  Error loading {analysis_file}: {e}")
                continue

        # Also check for extracted text files
        tmp_dir = self.base_dir / "tmp"
        if tmp_dir.exists():
            for txt_file in tmp_dir.glob("*.txt"):
                # Skip if we already have analysis for this paper
                paper_name = txt_file.stem
                if any(s['id'] == paper_name for s in summaries):
                    continue

                try:
                    content = txt_file.read_text(encoding='utf-8', errors='ignore')
                    concepts = self.detect_concepts(content.lower())

                    summaries.append({
                        'id': paper_name,
                        'file': str(txt_file),
                        'content_preview': content[:500],
                        'concepts': concepts,
                        'word_count': len(content.split()),
                    })
                except Exception:
                    continue

        return summaries

    def detect_concepts(self, text: str) -> Dict[str, int]:
        """Detect QA-related concepts in text"""
        concept_counts = defaultdict(int)

        for concept_name, keywords in self.qa_concepts.items():
            for keyword in keywords:
                # Count occurrences (case-insensitive)
                count = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE))
                if count > 0:
                    concept_counts[concept_name] += count

        return dict(concept_counts)

    def load_experiment_results(self) -> List[Dict[str, Any]]:
        """Load experiment evaluation results"""
        results = []

        if not self.evals_dir.exists():
            return results

        for eval_file in self.evals_dir.glob("*.json"):
            try:
                data = json.loads(eval_file.read_text())

                # Extract key metrics
                metrics = {}
                if isinstance(data, dict):
                    # Look for common metric fields
                    metrics['speedup'] = data.get('speedup_vs_baseline', data.get('speedup', 1.0))
                    metrics['time_sec'] = data.get('time_sec_pipeline', data.get('time_sec', 0))
                    metrics['e8_alignment'] = data.get('e8_alignment', data.get('hi_mean_sample', 0))

                results.append({
                    'id': eval_file.stem,
                    'file': str(eval_file),
                    'metrics': metrics,
                    'data': data,
                })
            except Exception:
                continue

        return results

    def find_cross_paper_links(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify conceptual connections between papers"""
        links = []

        # Find papers with overlapping concepts
        for i, paper_a in enumerate(papers):
            for paper_b in papers[i+1:]:
                # Calculate concept overlap
                concepts_a = set(paper_a['concepts'].keys())
                concepts_b = set(paper_b['concepts'].keys())

                overlap = concepts_a & concepts_b

                if len(overlap) >= 2:  # At least 2 shared concepts
                    # Calculate overlap strength
                    strength = sum(
                        min(paper_a['concepts'][c], paper_b['concepts'][c])
                        for c in overlap
                    )

                    links.append({
                        'paper_a': paper_a['id'],
                        'paper_b': paper_b['id'],
                        'shared_concepts': sorted(list(overlap)),
                        'overlap_strength': strength,
                    })

        # Sort by strength
        links.sort(key=lambda x: x['overlap_strength'], reverse=True)

        return links

    def find_concept_clusters(self, papers: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Group papers by dominant concepts"""
        clusters = defaultdict(list)

        for paper in papers:
            # Find dominant concept (most mentions)
            if paper['concepts']:
                dominant = max(paper['concepts'].items(), key=lambda x: x[1])
                concept, count = dominant
                if count >= 3:  # Significant presence
                    clusters[concept].append(paper['id'])

        return dict(clusters)

    def build_hypothesis_tasks(self, links: List[Dict[str, Any]],
                               clusters: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """Generate hypothesis tasks from cross-paper analysis"""
        tasks = []
        timestamp = datetime.now().strftime('%H%M%S')

        # Generate cross-paper hypotheses for top links
        for idx, link in enumerate(links[:5]):  # Top 5 strongest links
            paper_a = link['paper_a']
            paper_b = link['paper_b']
            concepts = ', '.join(link['shared_concepts'])

            task_id = f"hypothesis-{idx+1}-{paper_a[:10]}-{paper_b[:10]}-{timestamp}"

            # Generate hypothesis text based on shared concepts
            hypothesis = self.generate_hypothesis_text(link)

            tasks.append({
                'id': task_id,
                'project': 'hypothesis_validation',
                'title': f'Cross-domain QA hypothesis: {paper_a} ↔ {paper_b}',
                'description': f'''
Hypothesis connecting two research domains through QA framework.

**Papers:**
- A: {paper_a}
- B: {paper_b}

**Shared Concepts:** {concepts}
**Overlap Strength:** {link['overlap_strength']}

**Hypothesis:**
{hypothesis}

**Required Validation:**
1. Map concepts to QA tuples (b,e,d,a)
2. Identify shared QA invariants
3. Design cross-domain experiment
4. Run validation and measure QA metrics
                '''.strip(),
                'source': 'alpha_synthesis',
                'priority': 4.0,
                'status': 'pending',
                'lane': 'green',
                'assignee': 'qalm',
                'created': datetime.now().isoformat(),
                'tags': ['hypothesis', 'cross_domain', 'qa_theory'] + link['shared_concepts'],
                'metadata': {
                    'hypothesis_type': 'cross_paper',
                    'papers': [paper_a, paper_b],
                    'shared_concepts': link['shared_concepts'],
                    'overlap_strength': link['overlap_strength'],
                    'validation_domains': self.infer_domains(link['shared_concepts']),
                },
                'plan': {
                    'steps': [
                        {
                            'description': 'Extract QA-relevant concepts from both papers',
                            'acceptance': 'Concept mapping document with QA tuples',
                            'effort': 60,
                        },
                        {
                            'description': 'Identify shared QA invariants or patterns',
                            'acceptance': 'List of shared invariants with mathematical proof',
                            'effort': 90,
                        },
                        {
                            'description': 'Design cross-domain validation experiment',
                            'acceptance': 'Experiment design with metrics',
                            'effort': 60,
                        },
                        {
                            'description': 'Run experiment and analyze results',
                            'acceptance': 'Results showing QA invariant preservation',
                            'effort': 120,
                        },
                    ],
                    'risks': [
                        'Papers may use QA concepts differently',
                        'Cross-domain validation may be computationally expensive',
                    ],
                    'dependencies': ['Both papers ingested', 'QA framework stable'],
                }
            })

        # Generate synthesis tasks for concept clusters
        for concept, paper_list in clusters.items():
            if len(paper_list) >= 3:  # Cluster of 3+ papers
                task_id = f"synthesis-{concept}-{timestamp}"

                tasks.append({
                    'id': task_id,
                    'project': 'synthesis',
                    'title': f'Synthesize QA theory across {concept} domain ({len(paper_list)} papers)',
                    'description': f'''
Multiple papers share the concept: {concept}

Papers: {', '.join(paper_list)}

**Goal:** Synthesize a unified QA-based understanding across these papers.

**Expected Outputs:**
1. Unified QA formulation for {concept}
2. Common invariants or patterns
3. Potential new experiments bridging these works
4. Contribution to QA-{concept} integration theory
                    '''.strip(),
                    'source': 'alpha_synthesis',
                    'priority': 3.5,
                    'status': 'pending',
                    'lane': 'green',
                    'assignee': 'qalm',
                    'created': datetime.now().isoformat(),
                    'tags': ['synthesis', concept, 'theory'],
                    'metadata': {
                        'synthesis_type': 'concept_cluster',
                        'concept': concept,
                        'paper_count': len(paper_list),
                        'papers': paper_list,
                    },
                })

        return tasks

    def generate_hypothesis_text(self, link: Dict[str, Any]) -> str:
        """Generate hypothesis text based on shared concepts"""
        concepts = link['shared_concepts']

        # QA-specific hypothesis templates
        if 'modular_arithmetic' in concepts and 'gradient_descent' in concepts:
            return f"""
The modular arithmetic structures found in {link['paper_a']} may share
common descent dynamics with {link['paper_b']}, mediated through QA tuples (b,e,d,a).

Specifically, we hypothesize that HGD (Harmonic Gradient Descent) can accelerate
convergence in both domains by exploiting mod-24 and mod-9 residue patterns.
            """.strip()

        elif 'e8' in concepts or 'harmonic' in concepts:
            return f"""
Both {link['paper_a']} and {link['paper_b']} exhibit harmonic or E8-aligned structures.

We hypothesize that their shared QA invariants (particularly E8 alignment scores)
indicate a deeper geometric connection through the QA framework's 8D projection.
            """.strip()

        elif 'quantum' in concepts and any(c in concepts for c in ['modular_arithmetic', 'tuples']):
            return f"""
Quantum structures in {link['paper_a']} and modular arithmetic in {link['paper_b']}
may both be manifestations of QA tuple dynamics.

We hypothesize that quantum tunneling probabilities can be modeled using QA
mod-9 residue classes, with (b,e,d,a) tuples encoding energy transitions.
            """.strip()

        else:
            # Generic QA hypothesis
            shared = ', '.join(concepts[:2])
            return f"""
The shared concepts ({shared}) suggest a common underlying QA structure.

We hypothesize that both {link['paper_a']} and {link['paper_b']} can be unified
through QA modular arithmetic framework, with measurable QA invariants preserved
across both domains.
            """.strip()

    def infer_domains(self, concepts: List[str]) -> List[str]:
        """Infer research domains from concept list"""
        domain_map = {
            'vision': ['vision', 'image', 'cnn'],
            'quantum': ['quantum'],
            'compilation': ['compilation', 'jit'],
            'optimization': ['gradient_descent', 'optimizer'],
            'physics': ['statistical_physics', 'statistical_mechanics'],
        }

        domains = []
        for domain, domain_concepts in domain_map.items():
            if any(c in concepts for c in domain_concepts):
                domains.append(domain)

        return domains if domains else ['general_qa']

    def save_task(self, task: Dict[str, Any]):
        """Save task to inbox"""
        task_file = self.inbox / f"{task['id']}.yaml"
        if YAML_OK:
            with open(task_file, 'w') as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
        print(f"  ✅ Created: {task['id']}")

    def run(self):
        """Main alpha synthesis execution"""
        print("🧠 QA AlphaSynthesis: Cross-paper reasoning engine...")

        # Load data
        print("\n📚 Loading ingestion summaries...")
        papers = self.load_ingestion_summaries()
        print(f"  Found {len(papers)} ingested papers")

        if len(papers) < 2:
            print("  ⚠️  Need at least 2 papers for cross-analysis")
            return []

        print("\n🔬 Loading experiment results...")
        experiments = self.load_experiment_results()
        print(f"  Found {len(experiments)} experiment results")

        # Analyze connections
        print("\n🔗 Finding cross-paper conceptual links...")
        links = self.find_cross_paper_links(papers)
        print(f"  Found {len(links)} paper pairs with shared concepts")

        if links:
            print("  Top links:")
            for link in links[:3]:
                print(f"    • {link['paper_a']} ↔ {link['paper_b']}")
                print(f"      Shared: {', '.join(link['shared_concepts'])}")

        print("\n🌐 Identifying concept clusters...")
        clusters = self.find_concept_clusters(papers)
        print(f"  Found {len(clusters)} concept clusters")
        for concept, paper_list in list(clusters.items())[:3]:
            print(f"    • {concept}: {len(paper_list)} papers")

        if not links and not clusters:
            print("✨ No significant cross-paper patterns detected yet")
            return []

        # Generate hypotheses
        print("\n💡 Generating hypothesis tasks...")
        hypotheses = self.build_hypothesis_tasks(links, clusters)

        if not hypotheses:
            print("  No hypotheses generated")
            return []

        # Save tasks
        print(f"\n✅ Saving {len(hypotheses)} hypothesis tasks...")
        for task in hypotheses:
            self.save_task(task)

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "AlphaSynthesis",
            "action": "hypothesis_generation",
            "papers_analyzed": len(papers),
            "links_found": len(links),
            "clusters_found": len(clusters),
            "hypotheses_generated": len(hypotheses),
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"\n🧠 AlphaSynthesis complete: {len(hypotheses)} hypothesis tasks generated")
        return hypotheses


if __name__ == "__main__":
    synthesis = AlphaSynthesis()
    synthesis.run()
