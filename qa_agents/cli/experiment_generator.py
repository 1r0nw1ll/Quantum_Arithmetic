#!/usr/bin/env python3
"""
Experiment Generator (AI Co-Scientist) v1.0

Autonomous experiment design agent that:
1. Reads the comprehensive roadmap
2. Reads ingestion papers (unprocessed ODT files)
3. Generates executable experiment tasks for the swarm
4. Prioritizes based on impact × feasibility
5. Adapts based on past experimental results

This is the meta-layer that enables the swarm to self-organize research.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

BASE = Path(__file__).parent.parent.parent
INBOX = BASE / "tasks" / "inbox"
ACTIVE = BASE / "tasks" / "active"
COMPLETED = BASE / "tasks" / "completed"
LOGS = BASE / "logs"
ROADMAP_PATH = BASE / "docs" / "QA_COMPREHENSIVE_ROADMAP.md"
INGESTION_CANDIDATES = BASE.parent / "ingestion candidates"

# Configuration
MAX_TASKS_PER_RUN = int(os.getenv("QA_EXPERIMENT_GEN_MAX_TASKS", "10"))
MIN_PRIORITY = int(os.getenv("QA_EXPERIMENT_GEN_MIN_PRIORITY", "3"))  # 1-5 scale


class ExperimentGenerator:
    """AI Co-Scientist: Autonomous experiment design and task generation"""

    def __init__(self):
        self.base_dir = BASE
        self.roadmap = self._load_roadmap()
        self.existing_titles = self._collect_existing_titles()
        self.ingestion_papers = self._find_unprocessed_papers()
        self.past_results = self._load_past_results()

    def _load_roadmap(self) -> str:
        """Load the comprehensive roadmap"""
        if ROADMAP_PATH.exists():
            return ROADMAP_PATH.read_text(encoding="utf-8")
        return ""

    def _collect_existing_titles(self) -> set:
        """Collect all existing task titles to avoid duplicates"""
        titles = set()
        for pool in [INBOX, ACTIVE, COMPLETED]:
            if not pool.exists():
                continue
            for tf in pool.glob("*.yaml"):
                try:
                    text = tf.read_text(encoding="utf-8")
                    data = yaml.safe_load(text) if _YAML_OK else json.loads(text)
                    title = (data or {}).get("title")
                    if title:
                        titles.add(title.lower())
                except Exception:
                    continue
        return titles

    def _find_unprocessed_papers(self) -> List[Path]:
        """Find ingestion papers that haven't been processed yet"""
        if not INGESTION_CANDIDATES.exists():
            return []

        # Papers already processed (from INGESTION_INDEX.md)
        processed = {
            "qa_jepa.odt", "arc_is_a_vision+problem.odt", "volk_grant_qa.odt",
            "sum_product_conjecture.pdf", "Toroids, Vortices, Knots, Topology and Quanta, Part 2.doc",
            "similar_right_triangles.odt", "wiki _right_triangle.odt"
        }

        unprocessed = []
        for odt in INGESTION_CANDIDATES.glob("*.odt"):
            if odt.name not in processed:
                unprocessed.append(odt)

        # Sort by priority (based on roadmap mentions)
        priority_keywords = {
            "sheafcohomology": 10,
            "qa_jit": 8,
            "ramen_quantum_memory": 7,
            "statistical_mechanics": 7,
            "ai_coscientist": 9,
            "alpharesearch": 5,
        }

        def priority_score(p: Path) -> int:
            name_lower = p.stem.lower()
            for kw, score in priority_keywords.items():
                if kw in name_lower:
                    return score
            return 3  # default

        unprocessed.sort(key=priority_score, reverse=True)
        return unprocessed

    def _load_past_results(self) -> Dict:
        """Load past experimental results from qa_paper.json"""
        json_path = BASE / "artifacts" / "overleaf" / "qa_paper.json"
        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _extract_roadmap_experiments(self) -> List[Dict]:
        """Parse roadmap to extract experiment definitions"""
        experiments = []

        # Extract experiments from roadmap markdown structure
        # Format: ### X.Y Title\n**Priority:** PRIORITY\n**Status:** STATUS\n**Description:** DESC
        pattern = r"###\s+(\d+\.\d+)\s+(.+?)\n\*\*Priority:\*\*\s+(\w+)\n.*?\*\*Description:\*\*\s+(.+?)(?=\n\*\*|$)"

        for match in re.finditer(pattern, self.roadmap, re.DOTALL):
            section_id, title, priority_str, description = match.groups()

            # Convert priority to numeric (HIGH=5, MEDIUM=3, LOW=1)
            priority_map = {"HIGH": 5, "MEDIUM": 3, "LOW": 1}
            priority = priority_map.get(priority_str.upper(), 3)

            # Extract implementation details if present
            impl_section = match.group(0)
            bin_match = re.search(r"\*\*Bin:\*\*\s+`([^`]+)`", impl_section)
            makefile_match = re.search(r"\*\*Makefile Target:\*\*\s+`([^`]+)`", impl_section)

            exp = {
                "id": section_id,
                "title": title.strip(),
                "description": description.strip()[:200],  # First 200 chars
                "priority": priority,
                "bin": bin_match.group(1) if bin_match else None,
                "makefile_target": makefile_match.group(1) if makefile_match else None,
            }
            experiments.append(exp)

        return experiments

    def _generate_experiment_task(self, exp: Dict) -> Dict:
        """Generate a task YAML for an experiment"""
        now = datetime.now()
        task_id = f"exp-{exp['id'].replace('.', '-')}-{now.strftime('%m%d%H%M')}"

        # Determine assignee based on experiment type
        title_lower = exp["title"].lower()
        if "ablation" in title_lower or "sweep" in title_lower:
            assignee = "qalm"  # QA analysis
        elif "rust" in title_lower or exp.get("bin"):
            assignee = "rust"  # Rust implementation
        elif "paper" in title_lower or "process" in title_lower:
            assignee = "gemini"  # Document analysis
        elif "theoretical" in title_lower or "proof" in title_lower:
            assignee = "qalm"  # Mathematical reasoning
        else:
            assignee = "qalm"  # Default

        task = {
            "id": task_id,
            "project": "qa_roadmap_execution",
            "title": f"Experiment: {exp['title']}",
            "description": exp["description"],
            "source": "experiment_generator",
            "priority": exp["priority"],
            "status": "pending",
            "lane": "green",
            "assignee": assignee,
            "created": now.isoformat(),
            "tags": ["experiment", "roadmap", f"priority-{exp['priority']}"],
            "metadata": {
                "roadmap_id": exp["id"],
                "bin": exp.get("bin"),
                "makefile_target": exp.get("makefile_target"),
            }
        }

        return task

    def _generate_ingestion_task(self, paper: Path) -> Dict:
        """Generate a task to process an ingestion paper"""
        now = datetime.now()
        paper_stem = paper.stem.replace(" ", "_")
        task_id = f"ingest-{paper_stem[:20]}-{now.strftime('%m%d%H%M')}"

        # Determine priority based on roadmap mentions
        priority = 5 if "sheaf" in paper_stem.lower() else 4
        if "jit" in paper_stem.lower():
            priority = 4
        if "quantum" in paper_stem.lower():
            priority = 4

        task = {
            "id": task_id,
            "project": "qa_ingestion",
            "title": f"Process ingestion paper: {paper.stem}",
            "description": f"Extract and analyze {paper.name} using Gemini/Claude. Map concepts to QA framework and identify experiment opportunities.",
            "source": "experiment_generator",
            "priority": priority,
            "status": "pending",
            "lane": "green",
            "assignee": "gemini",  # Gemini for document analysis
            "created": now.isoformat(),
            "tags": ["ingestion", "research", f"priority-{priority}"],
            "metadata": {
                "paper_path": str(paper),
                "paper_name": paper.name,
                "output_analysis": f"artifacts/ingestion/{paper.stem}_ANALYSIS.md",
            }
        }

        return task

    def _save_task(self, task: Dict) -> Path:
        """Save task to inbox"""
        INBOX.mkdir(parents=True, exist_ok=True)
        task_file = INBOX / f"{task['id']}.yaml"

        if _YAML_OK:
            with open(task_file, "w", encoding="utf-8") as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")

        return task_file

    def generate_tasks(self) -> List[Dict]:
        """Main generation loop: create experiment and ingestion tasks"""
        generated = []

        # 1. Generate ingestion tasks for unprocessed papers (highest priority)
        print(f"\n📚 Found {len(self.ingestion_papers)} unprocessed ingestion papers")
        for paper in self.ingestion_papers[:5]:  # Top 5 priority papers
            task_title = f"Process ingestion paper: {paper.stem}".lower()
            if task_title in self.existing_titles:
                print(f"  ⏭️  Skipping duplicate: {paper.stem}")
                continue

            task = self._generate_ingestion_task(paper)
            task_file = self._save_task(task)
            generated.append(task)
            print(f"  ✅ Created: {task_file.name} (priority={task['priority']})")

            if len(generated) >= MAX_TASKS_PER_RUN:
                break

        # 2. Generate experiment tasks from roadmap (if budget remains)
        if len(generated) < MAX_TASKS_PER_RUN:
            print(f"\n🧪 Parsing roadmap for experiment tasks...")
            roadmap_experiments = self._extract_roadmap_experiments()
            print(f"  Found {len(roadmap_experiments)} experiments in roadmap")

            # Filter by priority and deduplicate
            for exp in roadmap_experiments:
                if exp["priority"] < MIN_PRIORITY:
                    continue

                task_title = f"experiment: {exp['title']}".lower()
                if task_title in self.existing_titles:
                    continue

                task = self._generate_experiment_task(exp)
                task_file = self._save_task(task)
                generated.append(task)
                print(f"  ✅ Created: {task_file.name} (priority={task['priority']})")

                if len(generated) >= MAX_TASKS_PER_RUN:
                    break

        # 3. Log summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "tasks_generated": len(generated),
            "ingestion_tasks": sum(1 for t in generated if "ingestion" in t["tags"]),
            "experiment_tasks": sum(1 for t in generated if "experiment" in t["tags"]),
            "priorities": {
                "high": sum(1 for t in generated if t["priority"] >= 4),
                "medium": sum(1 for t in generated if t["priority"] == 3),
                "low": sum(1 for t in generated if t["priority"] <= 2),
            }
        }

        log_file = LOGS / f"experiment_generator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        print(f"\n📊 Summary: {len(generated)} tasks generated")
        print(f"  Ingestion: {summary['ingestion_tasks']}")
        print(f"  Experiments: {summary['experiment_tasks']}")
        print(f"  Log: {log_file.name}")

        return generated

    def adapt_from_results(self):
        """Adapt future experiments based on past results (future enhancement)"""
        # Analyze qa_paper.json to identify successful patterns
        # Generate follow-up experiments for promising directions
        # De-prioritize experiments similar to failed attempts
        pass


def main():
    print("=" * 60)
    print("AI Co-Scientist: Experiment Generator v1.0")
    print("=" * 60)

    generator = ExperimentGenerator()
    tasks = generator.generate_tasks()

    if tasks:
        print(f"\n✅ SUCCESS: {len(tasks)} tasks injected into inbox")
        print(f"   Next: Run 'make dispatch' to assign agents")
    else:
        print("\n⚠️  No new tasks generated (all experiments may already exist)")


if __name__ == "__main__":
    main()
